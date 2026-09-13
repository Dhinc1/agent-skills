#!/usr/bin/env python3
"""
split_extract.py — Turn a land-development plan set (PDF or folder of PDFs)
into cheap, queryable per-sheet inputs: a single-sheet PDF, a rasterized PNG,
a rich vector-extraction JSON (text with coordinates, title-block hint, scale
candidates — metric AND imperial/engineering, geometry counts), and a
manifest.json indexing the whole set.

This is the DETERMINISTIC prep step (v2). It does NOT summarize or measure —
it only extracts. The agent reads the outputs (text + image + JSON) and
writes the per-sheet .md summaries, then uses measure.py for anything that
needs real quantities.

v2 changes from v1 (preprocess_plans.py):
  - Per-sheet JSON now carries word-level bboxes (not just a text dump), a
    scale detector (metric 1:N AND imperial/engineering A"=B'-C" or 1"=N'),
    a title-block zone flag per text block, and vector geometry counts
    (lines/rects/curves/drawings) via pdfplumber + PyMuPDF. This is what lets
    measure.py and extract_instances.py work without re-parsing the PDF.
  - Scale detection rejects a bare "1:N" sitting next to FALL/SLOPE/GRADE/
    BANK/BATTER — civil sheets are full of these and a naive regex reads a
    slope callout as the sheet scale.
  - Sheet numbering stays SEQUENTIAL across the whole merged set
    (sheet_001, sheet_002, ...) regardless of source PDF, matching how this
    business already talks about sheets ("sheet_053 / C9.08").

Usage:
    python split_extract.py INPUT [--out DIR] [--long-edge PX] [--split-pdf]
                             [--check-only] [--sqlite]

    INPUT        A merged plan-set PDF, or a directory of PDFs.
    --out DIR    Output directory (default: <input_stem>_sheets next to input).
    --long-edge  Target long-edge pixels for the raster (default 2200).
                 Large-format civil sheets (24x36) need this to keep
                 title-block and dimension text legible. Raise to ~2800 for
                 dense sheets, lower to ~1600 to save tokens on simple ones.
    --split-pdf  Also write a single-page PDF per sheet — required for
                 measure.py and for the Bluebeam-safe markup overlay, which
                 must start from the ORIGINAL single-sheet PDF, not a
                 PyMuPDF re-save of the merged set.
    --check-only Run the preflight report (vector vs scanned) and stop.
    --sqlite     Also write the manifest into a local SQLite db (plans.db).
                 Optional; the .md index is enough for a single set.

Dependency: PyMuPDF (fitz), pdfplumber.
    pip install --break-system-packages pymupdf pdfplumber
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: pip install --break-system-packages pymupdf pdfplumber")

try:
    import pdfplumber
    HAVE_PDFPLUMBER = True
except ImportError:
    HAVE_PDFPLUMBER = False

# A page with fewer than this many extracted characters is treated as
# scanned/raster-only (no useful text layer) -> vision pass is required.
TEXT_LAYER_MIN_CHARS = 40

# ----------------------------------------------------------------------------
# Scale detection — metric ratio AND imperial/engineering notation.
# Civil sets are almost always imperial (1"=20', 1"=50', 1"=100' site plans;
# 1/8"=1'-0" architectural detail sheets), so this must not be metric-only.
# ----------------------------------------------------------------------------
SCALE_PATTERNS = [
    r'SCALE\s*[:=]?\s*1\s*:\s*(\d+)',      # SCALE: 1:100 (explicit, most reliable)
    r'(?<![\d.])1\s*:\s*(\d+)(?![\d.])',   # bare 1:100 ratio (could also be a slope; guarded below)
]
# Engineering/architectural imperial:  A" = B'-C"   or   1"=20'   or  1/8"=1'-0"
IMPERIAL_PATTERN = r'(\d+(?:/\d+)?)\s*"?\s*=\s*(\d+)\s*\'(?:\s*-?\s*(\d+)\s*")?'
# A bare "1:N" next to any of these is a SLOPE/FALL/GRADE, not a drawing scale.
# Civil sheets are full of "MIN 1:50 FALL", "1:2 BANK", "1:3 SIDE SLOPE".
NON_SCALE_NEAR = re.compile(
    r'\b(FALL|SLOPE|GRADE|GRADIENT|BATTER|BANK|PITCH|CROSSFALL|CROSS\s*FALL|SIDE\s*SLOPE)\b',
    re.IGNORECASE)
# Valid 1:N factors, GENERATED from the scales civil/site plans actually use
# (rather than a hand-maintained literal list, which is exactly how a real
# scale — "SCALE:1" = 60'" on this business's own Cottages at Back Creek
# sheets — got silently missed in an earlier draft of this script; caught by
# testing against the real plan text before shipping this skill).
def _generate_valid_scale_factors():
    # Common engineering (site/civil) scales, inches-to-feet.
    engineering_ft = [1, 2, 3, 4, 5, 6, 8, 10, 15, 16, 20, 24, 25, 30, 32, 40,
                      50, 60, 80, 100, 150, 160, 200, 250, 300, 320, 400, 500,
                      600, 800, 1000, 1600, 2000]
    # Common architectural fraction scales, e.g. 1/8" = 1'-0", 3/4" = 1'-0".
    architectural_fracs = [1/16, 3/32, 1/8, 3/16, 1/4, 3/8, 1/2, 3/4, 1, 1.5, 3]
    factors = {1}  # full scale
    for ft in engineering_ft:
        factors.add(ft * 12)
    for frac in architectural_fracs:
        factors.add(round(12 / frac))
    return factors


VALID_SCALE_FACTORS = _generate_valid_scale_factors()


def _imperial_to_factor(a, b, c):
    """A" = B'-C"  ->  real_inches / drawing_inches, rounded to an int factor."""
    try:
        if '/' in a:
            num, den = a.split('/')
            draw = float(num) / float(den)
        else:
            draw = float(a)
        if draw <= 0:
            return None
        real_in = float(b) * 12 + (float(c) if c else 0)
        return round(real_in / draw)
    except Exception:
        return None


def detect_scale(text_blocks: list) -> dict:
    """Detect the sheet's scale from its text blocks.

    Returns {"detected": False} if nothing matches — the agent must then read
    the plan's own scale note off the render, or ask, before trusting any
    length/area. NEVER fabricate a scale.
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
                continue
            candidates.append({"factor": factor, "text": text.strip(), "in_title_zone": in_tz,
                               "explicit": explicit, "system": "metric"})
            break

    if not candidates:
        return {"detected": False}

    candidates.sort(key=lambda c: (c.get("explicit") and c["in_title_zone"],
                                   c["in_title_zone"], bool(c.get("explicit"))), reverse=True)
    best = candidates[0]
    high = best["in_title_zone"] or best.get("explicit")
    return {
        "detected": True,
        "factor": best["factor"],
        "system": best.get("system", "imperial"),
        "method": "title_block" if best["in_title_zone"] else ("scale_label" if best.get("explicit") else "bare_ratio"),
        "confidence": "high" if high else "medium",  # bare ratio downgraded — may be a slope
        "source_text": best["text"],
        "all_factors": sorted({c["factor"] for c in candidates if c["factor"]}),
        "candidate_count": len(candidates),
    }


def titleblock_hint(page):
    """Grab text from the bottom-right region where civil title blocks live.
    Helps guess sheet number + title without reading the whole sheet.
    Note: title-block text is sometimes rotated 90 degrees on large-format
    sheets — if this comes back empty/garbled, read the sheet ID off the
    render instead."""
    r = page.rect
    clip = fitz.Rect(r.x0 + r.width * 0.68, r.y0 + r.height * 0.80, r.x1, r.y1)
    txt = page.get_text("text", clip=clip).strip()
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    return " | ".join(lines[:12])


def text_blocks_with_zones(page):
    """Word-level text extraction with bbox + title-zone flag. Uses 'words'
    mode (not dict/span mode) — span mode silently drops text held in form
    XObjects on many CAD exports, which can undercount tag text by 3-5x."""
    r = page.rect
    page_w, page_h = r.width, r.height
    out = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        text = text.strip()
        if not text:
            continue
        x_frac = (x0 / page_w) if page_w else 0
        y_frac = (y0 / page_h) if page_h else 0
        in_title_zone = (x_frac > 0.65) and (y_frac > 0.55)
        out.append({
            "text": text,
            "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
            "in_title_zone": in_title_zone,
        })
    return out


def pdfplumber_geometry(pdf_path: str, page_index: int) -> dict:
    """Vector geometry counts + a small sample, via pdfplumber. Full geometry
    for measurement comes from measure.py at query time — this is a cheap
    per-sheet summary so the index can flag "this sheet is geometry-dense" or
    "this sheet is a raster/outlined-text export" (high vector count, ~0 words)."""
    out = {"available": HAVE_PDFPLUMBER, "lines_count": 0, "rects_count": 0, "curves_count": 0}
    if not HAVE_PDFPLUMBER:
        return out
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_index >= len(pdf.pages):
                return out
            p = pdf.pages[page_index]
            out["lines_count"] = len(p.lines or [])
            out["rects_count"] = len(p.rects or [])
            out["curves_count"] = len(p.curves or [])
    except Exception as e:
        out["error"] = f"pdfplumber failed: {e}"
    return out


def preflight(pdfs):
    """Classify the set before heavy work: how many sheets carry a usable
    text layer (CAD vector) vs none (scanned/raster, or outlined-text —
    see the outlined-text gotcha in SKILL.md). Returns (total, vector, scanned)."""
    total = vector = 0
    scanned_pages = []
    for pdf in pdfs:
        doc = fitz.open(pdf)
        for i, page in enumerate(doc):
            total += 1
            if len(page.get_text("text").strip()) >= TEXT_LAYER_MIN_CHARS:
                vector += 1
            else:
                scanned_pages.append(f"{pdf.name} p{i+1}")
        doc.close()
    pct = (vector / total * 100) if total else 0
    print(f"Preflight: {total} sheet(s), {vector} with text layer ({pct:.0f}%), "
          f"{len(scanned_pages)} scanned/raster.")
    if scanned_pages:
        print("  Scanned/no-text (image pass required): " + ", ".join(scanned_pages))
    if pct == 100:
        print("  All vector. Text path is primary; image pass is the exception.")
    elif pct == 0:
        print("  No text layer anywhere. This set is scanned; rely on images/OCR.")
    else:
        print("  Mixed set. Vector sheets use text; flagged sheets need images.")
    print("  Note: a page CAN show high vector-path count with ~0 words — that is an")
    print("  OUTLINED-TEXT export (text flattened to curves), not raster. It will pass")
    print("  this preflight as 'vector' but count/text extraction will still return")
    print("  nothing on it. See the outlined-text gotcha in SKILL.md.")
    return total, vector, scanned_pages


def write_sqlite(out_dir: Path, records):
    import sqlite3
    db = out_dir / "plans.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE IF NOT EXISTS sheets(
        source_pdf TEXT, sheet INT, source_page INT, png TEXT, txt TEXT, json TEXT,
        sheet_pdf TEXT, has_text_layer INT, text_chars INT,
        titleblock_hint TEXT, scale_detected INT, scale_factor INT, scale_confidence TEXT,
        summary_md TEXT,
        PRIMARY KEY(source_pdf, sheet))""")
    con.executemany(
        """INSERT OR REPLACE INTO sheets VALUES
           (:source_pdf,:sheet,:source_page,:png,:txt,:json,:sheet_pdf,
            :has_text_layer,:text_chars,:titleblock_hint,
            :scale_detected,:scale_factor,:scale_confidence,:summary_md)""",
        [{**r, "has_text_layer": int(r["has_text_layer"]),
          "scale_detected": int(r["scale"]["detected"]),
          "scale_factor": r["scale"].get("factor"),
          "scale_confidence": r["scale"].get("confidence")}
         for r in records])
    con.commit(); con.close()
    print(f"SQLite: {db}")


def process_pdf(pdf_path: Path, out_dir: Path, long_edge: int, split_pdf: bool,
                sheet_offset: int, source_label: str):
    doc = fitz.open(pdf_path)
    records = []
    for i, page in enumerate(doc):
        n = sheet_offset + i + 1
        stem = f"sheet_{n:03d}"

        # --- text layer (plain dump, for cheap reading) ---
        text = page.get_text("text")
        char_count = len(text.strip())
        has_text_layer = char_count >= TEXT_LAYER_MIN_CHARS
        (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")

        # --- word-level text with bbox + title-zone (for JSON / measure.py) ---
        blocks = text_blocks_with_zones(page)
        scale = detect_scale(blocks)

        try:
            vector_drawing_count = len(page.get_drawings())
        except Exception:
            vector_drawing_count = None

        # --- raster (scale so the long edge hits target px) ---
        r = page.rect
        page_long = max(r.width, r.height) or 1
        zoom = long_edge / page_long
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_path = out_dir / f"{stem}.png"
        pix.save(img_path)

        # --- optional single-sheet PDF (required for measure.py + Bluebeam-safe markup) ---
        sheet_pdf_rel = None
        if split_pdf:
            one = fitz.open()
            one.insert_pdf(doc, from_page=i, to_page=i)
            sheet_pdf_path = out_dir / f"{stem}.pdf"
            one.save(sheet_pdf_path)
            one.close()
            sheet_pdf_rel = sheet_pdf_path.name

        # --- per-sheet JSON (text_blocks + scale + geometry counts) ---
        page_json = {
            "sheet": n,
            "source_pdf": source_label,
            "source_page": i + 1,
            "width_pts": round(r.width, 1),
            "height_pts": round(r.height, 1),
            "titleblock_hint": titleblock_hint(page),
            "text_blocks": blocks,
            "scale": scale,
            "vector_drawing_count": vector_drawing_count,
            "pdfplumber": pdfplumber_geometry(str(pdf_path), i),
        }
        json_path = out_dir / f"{stem}.json"
        json_path.write_text(json.dumps(page_json, indent=2), encoding="utf-8")

        records.append({
            "sheet": n,
            "source_pdf": source_label,
            "source_page": i + 1,
            "png": img_path.name,
            "txt": (out_dir / f"{stem}.txt").name,
            "json": json_path.name,
            "sheet_pdf": sheet_pdf_rel,
            "has_text_layer": has_text_layer,
            "text_chars": char_count,
            "page_size_pt": [round(r.width, 1), round(r.height, 1)],
            "raster_px": [pix.width, pix.height],
            "titleblock_hint": page_json["titleblock_hint"],
            "scale": scale,
            "vector_drawing_count": vector_drawing_count,
            "summary_md": f"{stem}.md",  # to be written by the agent
        })
    doc.close()
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out")
    ap.add_argument("--long-edge", type=int, default=2200)
    ap.add_argument("--split-pdf", action="store_true")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--sqlite", action="store_true")
    args = ap.parse_args()

    in_path = Path(args.input).expanduser().resolve()
    if not in_path.exists():
        sys.exit(f"Input not found: {in_path}")

    if in_path.is_dir():
        pdfs = sorted(p for p in in_path.iterdir() if p.suffix.lower() == ".pdf")
        if not pdfs:
            sys.exit(f"No PDFs in {in_path}")
        default_out = in_path / "_sheets"
    else:
        pdfs = [in_path]
        default_out = in_path.with_name(in_path.stem + "_sheets")

    preflight(pdfs)
    if args.check_only:
        return

    out_dir = Path(args.out).expanduser().resolve() if args.out else default_out
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    offset = 0
    for pdf in pdfs:
        recs = process_pdf(pdf, out_dir, args.long_edge, args.split_pdf, offset, pdf.name)
        all_records.extend(recs)
        offset += len(recs)
        print(f"  {pdf.name}: {len(recs)} sheet(s)")

    scanned = [r["sheet"] for r in all_records if not r["has_text_layer"]]
    no_scale = [r["sheet"] for r in all_records if not r["scale"]["detected"]]
    manifest = {
        "source": str(in_path),
        "sheet_count": len(all_records),
        "long_edge_px": args.long_edge,
        "scanned_sheets_no_text_layer": scanned,
        "sheets_no_scale_detected": no_scale,
        "sheets": all_records,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nDone. {len(all_records)} sheet(s) -> {out_dir}")
    if scanned:
        print(f"Note: {len(scanned)} sheet(s) have no text layer (scanned/raster or "
              f"outlined-text — verify which): {scanned}.")
    if no_scale:
        print(f"Note: {len(no_scale)} sheet(s) had no scale detected: {no_scale}. "
              f"Read the plan's own scale note off the render before measuring these.")
    print(f"Manifest: {out_dir / 'manifest.json'}")
    if args.sqlite:
        write_sqlite(out_dir, all_records)


if __name__ == "__main__":
    main()
