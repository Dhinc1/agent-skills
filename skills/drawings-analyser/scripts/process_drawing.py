#!/usr/bin/env python3
"""
Process a single drawing PDF for project-indexer.

For every page of the input PDF, produces three artefacts in the output dir:
  1. A single-sheet PDF (durable — saved alongside the project for later use)
  2. A PNG render of the page (sized to Claude's native max — see --long-edge-px)
  3. A JSON file with comprehensive vector extraction:
     - All selectable text + bounding boxes (PyMuPDF + pdfplumber as fallback)
     - All lines, rectangles, curves with coordinates (pdfplumber)
     - Title-block hints (positional heuristic, NOT a hard classifier)
     - Vector drawing count (sanity check)

The vector JSON is the foundation for downstream AI analysis. Vision passes
read it alongside the PNG so the model never has to guess what the title
block says — it's already extracted at 100% accuracy.

The split single-sheet PDFs are the persisted output. The PNGs and JSON are
inputs to the per-sheet analysis step.

Usage:
    python process_drawing.py drawing.pdf -o "<project>/0. AI Context/drawings_split/<source_stem>"

Defaults match Claude Opus 4.7's native image resolution (2576px long edge,
~3.75MP). This is the model's internal max — anything larger gets downscaled
server-side, so rendering bigger just wastes tokens.
Source: https://platform.claude.com/docs/en/build-with-claude/vision
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF required. Install with: pip install pymupdf --break-system-packages", file=sys.stderr)
    sys.exit(1)

try:
    import pdfplumber
    HAVE_PDFPLUMBER = True
except ImportError:
    HAVE_PDFPLUMBER = False


# Claude Opus 4.7 supports up to 2576px on the long edge before internal
# downscaling. Going bigger costs tokens for no accuracy gain.
DEFAULT_LONG_EDGE_PX = 2576


# Scale patterns commonly found on construction drawings. Borrowed from the
# construction-takeoff skill — drawings carry their scale in the title block,
# and downstream per-sheet analysis + coordination passes need to know it.
# Order matters: more specific patterns first so we attribute correctly.
SCALE_PATTERNS = [
    r'SCALE\s*[:=]?\s*1\s*:\s*(\d+)',        # SCALE: 1:100 (explicit, most reliable)
    r'(?<![\d.])1\s*:\s*(\d+)(?![\d.])',     # 1:100 — bare ratio (could also be a slope; see guard)
]

# Imperial architectural/engineering/civil scales:  A" = B'-C"   or   1" = 20'
IMPERIAL_PATTERN = r'(\d+(?:/\d+)?)\s*"?\s*=\s*(\d+)\s*\'(?:\s*-?\s*(\d+)\s*")?'

# A bare "1:N" sitting next to any of these is a SLOPE/FALL/GRADE, NOT a drawing scale.
# (Civil sheets are full of "MINIMUM 1:50 FALL", "1:2 BANK" etc.) — both critics hit this.
NON_SCALE_NEAR = re.compile(r'\b(FALL|SLOPE|GRADE|GRADIENT|BATTER|BANK|PITCH|CROSSFALL|CROSS\s*FALL)\b',
                            re.IGNORECASE)

# Real metric + imperial-derived scale factors (1:N). Imperial common: 1/8"=1'=>96, 1/4"=>48,
# 3/8"=>32, 1/2"=>24, 1"=20'=>240, 1"=10'=>120, 1"=30'=>360.
VALID_SCALE_FACTORS = {1, 2, 5, 10, 20, 24, 25, 32, 40, 48, 50, 96, 100, 120, 125, 192, 200,
                       240, 250, 360, 480, 500, 1000, 1250, 2000, 2500, 5000}


def _imperial_to_factor(a, b, c):
    """A" = B'-C"  ->  real_inches / drawing_inches."""
    try:
        if '/' in a:
            num, den = a.split('/'); draw = float(num) / float(den)
        else:
            draw = float(a)
        if draw <= 0:
            return None
        real_in = float(b) * 12 + (float(c) if c else 0)
        return round(real_in / draw)
    except Exception:
        return None


def detect_scale(text_blocks: list) -> dict:
    """
    Detect the drawing's scale (metric 1:N, imperial A"=B'-C", or NTS) from text blocks.

    Guards added (from independent HVAC + civil stress tests):
      - parses imperial scales (North American sets), not just 1:N;
      - rejects a bare "1:N" adjacent to FALL/SLOPE/GRADE/BANK/BATTER (it's a slope, not a scale);
      - a bare ratio (no "SCALE" prefix, not in title block) is only MEDIUM confidence;
      - returns all distinct factors found (multi-scale sheets: 1:100/1:10/1:5).
    Returns {"detected": False} if nothing matches — per-sheet analysis falls back to vision.
    """
    candidates = []
    for block in text_blocks:
        text = block.get("text", "") or ""
        in_tz = block.get("in_title_zone", False)
        is_slope = bool(NON_SCALE_NEAR.search(text))

        im = re.search(IMPERIAL_PATTERN, text)
        if im and not is_slope:
            f = _imperial_to_factor(im.group(1), im.group(2), im.group(3))
            if f and f in VALID_SCALE_FACTORS:
                candidates.append({"factor": f, "text": text.strip(), "in_title_zone": in_tz,
                                   "explicit": True, "system": "imperial"})
                continue

        if re.search(r'\bN\.?\s*T\.?\s*S\.?\b', text, re.IGNORECASE):
            candidates.append({"factor": None, "text": "NTS", "in_title_zone": in_tz,
                               "explicit": True, "system": "nts"})
            continue

        for i, pattern in enumerate(SCALE_PATTERNS):
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            try:
                factor = int(match.group(1))
            except (ValueError, IndexError):
                continue
            if factor not in VALID_SCALE_FACTORS:
                continue
            explicit = (i == 0)  # had a "SCALE" prefix
            if is_slope and not explicit:
                continue  # "1:50 FALL" with no SCALE prefix -> reject
            candidates.append({"factor": factor, "text": text.strip(), "in_title_zone": in_tz,
                               "explicit": explicit, "system": "metric"})
            break

    if not candidates:
        return {"detected": False}

    # Prefer: explicit SCALE-label in the title zone > title zone > explicit label > first.
    candidates.sort(key=lambda c: (c.get("explicit") and c["in_title_zone"],
                                   c["in_title_zone"], bool(c.get("explicit"))), reverse=True)
    best = candidates[0]
    high = best["in_title_zone"] or best.get("explicit")
    return {
        "detected": True,
        "factor": best["factor"],
        "system": best.get("system", "metric"),
        "method": "title_block" if best["in_title_zone"] else ("scale_label" if best.get("explicit") else "bare_ratio"),
        "confidence": "high" if high else "medium",  # bare ratio downgraded — it may be a slope
        "source_text": best["text"],
        "all_factors": sorted({c["factor"] for c in candidates if c["factor"]}),
        "candidate_count": len(candidates),
    }


def render_page_to_png(page, output_path: str, long_edge_px: int) -> dict:
    """Render a PDF page to PNG sized so the long edge equals long_edge_px."""
    page_w = page.rect.width
    page_h = page.rect.height
    long_edge_pts = max(page_w, page_h)
    if long_edge_pts <= 0:
        zoom = 1.0
    else:
        zoom = long_edge_px / long_edge_pts
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    pix.save(output_path)
    return {"width": pix.width, "height": pix.height, "zoom": round(zoom, 3)}


def extract_with_pymupdf(page) -> dict:
    """Fallback text extraction using PyMuPDF — works even when pdfplumber doesn't."""
    info = {
        "text_blocks": [],
        "title_block_candidates": [],
    }
    try:
        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
    except Exception:
        return info

    page_w = page.rect.width
    page_h = page.rect.height

    for block in blocks:
        if block.get("type") != 0:  # 0 = text
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text:
                    continue
                bbox = span.get("bbox", [0, 0, 0, 0])

                # Title blocks are typically bottom-right or right edge.
                # This is a HINT for downstream AI, not a classifier.
                x_frac = (bbox[0] / page_w) if page_w else 0
                y_frac = (bbox[1] / page_h) if page_h else 0
                in_title_zone = (x_frac > 0.65) and (y_frac > 0.55)

                entry = {
                    "text": text,
                    "size": round(span.get("size", 0), 1),
                    "bbox": [round(b, 1) for b in bbox],
                    "in_title_zone": in_title_zone,
                }
                info["text_blocks"].append(entry)
                if in_title_zone:
                    info["title_block_candidates"].append(entry)

    return info


def extract_with_pdfplumber(pdf_path: str, page_index: int) -> dict:
    """
    Rich vector extraction using pdfplumber — chars, lines, rects, curves
    with exact coordinates. This is the data that lets downstream AI work
    from structured text instead of having to OCR the title block from pixels.
    """
    if not HAVE_PDFPLUMBER:
        return {"available": False}

    out = {
        "available": True,
        "chars_count": 0,
        "lines_count": 0,
        "rects_count": 0,
        "curves_count": 0,
        # Sample of geometric primitives — capped to keep JSON manageable.
        # Full data is in the source PDF if a downstream skill needs more.
        "lines_sample": [],
        "rects_sample": [],
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_index >= len(pdf.pages):
                return out
            p = pdf.pages[page_index]
            out["chars_count"] = len(p.chars or [])
            lines = p.lines or []
            rects = p.rects or []
            curves = p.curves or []
            out["lines_count"] = len(lines)
            out["rects_count"] = len(rects)
            out["curves_count"] = len(curves)
            # Include a small sample of lines/rects so AI can reason about the
            # presence of grids, schedules, frames etc. without us shipping
            # tens of thousands of primitives.
            for ln in lines[:200]:
                out["lines_sample"].append({
                    "x0": round(ln.get("x0", 0), 1),
                    "y0": round(ln.get("y0", 0), 1),
                    "x1": round(ln.get("x1", 0), 1),
                    "y1": round(ln.get("y1", 0), 1),
                })
            for rc in rects[:100]:
                out["rects_sample"].append({
                    "x0": round(rc.get("x0", 0), 1),
                    "y0": round(rc.get("y0", 0), 1),
                    "x1": round(rc.get("x1", 0), 1),
                    "y1": round(rc.get("y1", 0), 1),
                    "width": round(rc.get("width", 0), 1),
                    "height": round(rc.get("height", 0), 1),
                })
    except Exception as e:
        out["error"] = f"pdfplumber failed: {e}"

    return out


def extract_page_info(pdf_path: str, page, page_index: int) -> dict:
    """Combine PyMuPDF text extraction with pdfplumber geometry extraction."""
    info = {
        "page_number": page.number + 1,
        "width_pts": round(page.rect.width, 1),
        "height_pts": round(page.rect.height, 1),
        "all_text": "",
    }

    pymupdf_info = extract_with_pymupdf(page)
    info["text_blocks"] = pymupdf_info["text_blocks"]
    info["title_block_candidates"] = pymupdf_info["title_block_candidates"]
    info["all_text"] = "\n".join(b["text"] for b in pymupdf_info["text_blocks"])

    # Scale detection — runs against the already-extracted text blocks. Cheap.
    info["scale"] = detect_scale(pymupdf_info["text_blocks"])

    info["pdfplumber"] = extract_with_pdfplumber(pdf_path, page_index)

    try:
        info["vector_drawing_count"] = len(page.get_drawings())
    except Exception:
        info["vector_drawing_count"] = None

    return info


def process(pdf_path: str, output_dir: str, long_edge_px: int = DEFAULT_LONG_EDGE_PX) -> dict:
    doc = fitz.open(pdf_path)
    os.makedirs(output_dir, exist_ok=True)
    source_name = Path(pdf_path).stem

    manifest = {
        "source_file": Path(pdf_path).name,
        "source_path": str(pdf_path),
        "total_pages": len(doc),
        "render_long_edge_px": long_edge_px,
        "pdfplumber_available": HAVE_PDFPLUMBER,
        "output_dir": output_dir,
        "sheets": [],
    }

    try:
        for idx in range(len(doc)):
            page = doc[idx]
            sheet_num = idx + 1
            stem = f"{source_name}_sheet{sheet_num}"

            # 1. Persisted single-sheet PDF (durable artefact)
            pdf_out_path = os.path.join(output_dir, f"{stem}.pdf")
            single = fitz.open()
            single.insert_pdf(doc, from_page=idx, to_page=idx)
            single.save(pdf_out_path)
            single.close()

            # 2. PNG render at Claude's native max
            img_path = os.path.join(output_dir, f"{stem}.png")
            render_info = render_page_to_png(page, img_path, long_edge_px)

            # 3. Comprehensive vector extraction JSON
            page_info = extract_page_info(pdf_path, page, idx)
            json_path = os.path.join(output_dir, f"{stem}.json")
            with open(json_path, "w") as f:
                json.dump(page_info, f, indent=2)

            manifest["sheets"].append({
                "sheet_number": sheet_num,
                "pdf_path": pdf_out_path,
                "image_path": img_path,
                "image_size": {"width": render_info["width"], "height": render_info["height"]},
                "extraction_path": json_path,
                "title_block_candidates": page_info["title_block_candidates"][:20],
                "text_sample": page_info["all_text"][:500],
                "vector_summary": {
                    "lines": page_info["pdfplumber"].get("lines_count"),
                    "rects": page_info["pdfplumber"].get("rects_count"),
                    "chars": page_info["pdfplumber"].get("chars_count"),
                    "drawings": page_info.get("vector_drawing_count"),
                },
            })
    finally:
        doc.close()

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def main():
    ap = argparse.ArgumentParser(
        description="Split a drawing PDF into per-sheet PDFs + per-sheet PNG + per-sheet vector JSON."
    )
    ap.add_argument("pdf_path")
    ap.add_argument("-o", "--output-dir", required=True)
    ap.add_argument(
        "--long-edge-px",
        type=int,
        default=DEFAULT_LONG_EDGE_PX,
        help=(
            f"Long edge of rendered PNG in pixels (default {DEFAULT_LONG_EDGE_PX}). "
            "Matches Claude Opus 4.7's native image resolution. Larger values waste tokens."
        ),
    )
    args = ap.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    if not HAVE_PDFPLUMBER:
        print(
            "WARNING: pdfplumber not installed — vector geometry extraction will be limited. "
            "Install with: pip install pdfplumber --break-system-packages",
            file=sys.stderr,
        )

    manifest = process(args.pdf_path, args.output_dir, args.long_edge_px)
    print(
        f"Split {manifest['total_pages']} sheets from {manifest['source_file']} -> {args.output_dir}",
        file=sys.stderr,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
