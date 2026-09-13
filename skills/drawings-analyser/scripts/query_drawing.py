#!/usr/bin/env python3
"""
Query-time vector extraction tools for drawings-analyser.

Claude calls these on demand when answering a precise question about a
specific drawing. The split + render + index-time extraction has already
happened in process_drawing.py; this script reaches back into the durable
single-sheet PDF in drawings_split/ to pull exact numbers.

Sub-commands:
    polygons      — find closed polygons in a region; report area in mm² and m²
    text          — every text object in a region (exact characters + bbox)
    dimensions    — text that looks like a dimension (numeric + units) in a region
    tables        — structured tables from the sheet (full sheet or a region)
    page-info     — page size, scale hints, and whatever the title block holds

All bbox arguments are in PDF points (1pt = 1/72 inch). The same coordinate
system as the per-sheet vector JSON (PyMuPDF / pdfplumber). Origin = top-left.
Use the per-sheet markdown's "Coordinate hints for query-time extraction"
section for known regions; otherwise estimate from the rendered PNG and
zoom in iteratively.

Drawing scale is always required for area / length conversion. Pass it
either as a real-world ratio (`--scale 1:100`) or as a `mm-per-point`
factor (`--mm-per-pt 4.233`). When the per-sheet JSON has a confident
scale detection, prefer that.

Usage examples:
    # Slab polygon area
    python query_drawing.py polygons "S101.pdf" \\
        --bbox 80 50 1620 720 --scale 1:100

    # Every text object inside a footing schedule
    python query_drawing.py text "S101.pdf" \\
        --bbox 1180 730 1820 1100

    # Structured tables (lets pdfplumber decide row/column structure)
    python query_drawing.py tables "S101.pdf"

    # Quick scale + page metadata sanity check
    python query_drawing.py page-info "S101.pdf"
"""

import argparse
import json
import math
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


# 1 point = 1/72 inch = 25.4/72 mm
MM_PER_POINT = 25.4 / 72.0


# ----------------------------------------------------------------------------
# Scale handling
# ----------------------------------------------------------------------------
def parse_scale(scale_str: str | None, mm_per_pt: float | None) -> dict:
    """
    Resolve a scale spec into a single mm-per-point factor.

    Returns a dict with `mm_per_pt`, `scale_label`, `source` (or `None` if no
    scale was provided). Real-world mm = pdf_points × mm_per_pt.
    """
    if mm_per_pt is not None:
        return {
            "mm_per_pt": float(mm_per_pt),
            "scale_label": f"{mm_per_pt:.4f} mm/pt",
            "source": "explicit_mm_per_pt",
        }

    if not scale_str:
        return {"mm_per_pt": None, "scale_label": None, "source": None}

    # Accept "1:100", "1:50", "1/100", "1 : 100", or "100"
    match = re.match(r"^\s*1?\s*[:/]?\s*(\d+(?:\.\d+)?)\s*$", scale_str)
    if not match:
        raise ValueError(
            f"Could not parse scale {scale_str!r}. Use '1:100' or '--mm-per-pt' instead."
        )

    denominator = float(match.group(1))
    # 1 PDF point on a 1:N drawing = N points of real world = N × MM_PER_POINT mm
    real_mm_per_pt = denominator * MM_PER_POINT
    return {
        "mm_per_pt": real_mm_per_pt,
        "scale_label": f"1:{int(denominator) if denominator.is_integer() else denominator}",
        "source": "ratio",
    }


def pts_to_mm(value_pts: float, mm_per_pt: float | None) -> float | None:
    if mm_per_pt is None:
        return None
    return value_pts * mm_per_pt


# ----------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------
def bbox_clip(bbox: tuple, page_w: float, page_h: float) -> tuple:
    x0, y0, x1, y1 = bbox
    x0 = max(0.0, min(x0, page_w))
    x1 = max(0.0, min(x1, page_w))
    y0 = max(0.0, min(y0, page_h))
    y1 = max(0.0, min(y1, page_h))
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def shoelace_area_pts2(points: list[tuple[float, float]]) -> float:
    """Polygon area in pdf-points² using the shoelace formula."""
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def polygon_perimeter_pts(points: list[tuple[float, float]]) -> float:
    n = len(points)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def in_bbox(x: float, y: float, bbox: tuple) -> bool:
    x0, y0, x1, y1 = bbox
    return (x0 <= x <= x1) and (y0 <= y <= y1)


# ----------------------------------------------------------------------------
# Polygon extraction
# ----------------------------------------------------------------------------
def extract_polygons(
    pdf_path: str,
    bbox: tuple | None,
    scale: dict,
    min_area_pts2: float = 100.0,
) -> dict:
    """
    Find closed polygons (drawn paths whose start and end points coincide)
    inside the given bbox. Reports each polygon's vertices, area, and
    perimeter, in points and — when scale is known — in mm and m².

    Uses PyMuPDF's get_drawings() because it gives us full path data
    including bezier curves and closure flags. pdfplumber's lines/rects only
    give us atomic primitives.
    """
    out = {
        "pdf": pdf_path,
        "bbox_pts": list(bbox) if bbox else None,
        "scale": scale,
        "polygons": [],
    }

    doc = fitz.open(pdf_path)
    try:
        if len(doc) == 0:
            out["error"] = "PDF has no pages"
            return out
        page = doc[0]
        pw, ph = page.rect.width, page.rect.height
        clipped = bbox_clip(bbox, pw, ph) if bbox else (0, 0, pw, ph)

        try:
            drawings = page.get_drawings()
        except Exception as e:
            out["error"] = f"get_drawings failed: {e}"
            return out

        polygons = []
        for d in drawings:
            # Each drawing can have multiple sub-items; we walk all line/curve
            # segments and stitch them into a polyline. If start == end, treat
            # as closed.
            items = d.get("items", []) or []
            if not items:
                continue

            current = []
            for it in items:
                op = it[0]
                if op == "l" and len(it) >= 3:
                    p0, p1 = it[1], it[2]
                    if not current:
                        current.append((p0.x, p0.y))
                    current.append((p1.x, p1.y))
                elif op == "c" and len(it) >= 5:
                    # Cubic bezier — approximate with end point. Good enough
                    # for area estimation on architectural geometry; for very
                    # curved paths, increase the sample later.
                    p3 = it[4]
                    if not current:
                        p0 = it[1]
                        current.append((p0.x, p0.y))
                    current.append((p3.x, p3.y))
                elif op == "re" and len(it) >= 2:
                    # Rectangle — emit four corners as a closed polygon
                    rect = it[1]
                    rect_pts = [
                        (rect.x0, rect.y0),
                        (rect.x1, rect.y0),
                        (rect.x1, rect.y1),
                        (rect.x0, rect.y1),
                    ]
                    polygons.append({
                        "kind": "rect",
                        "points_pts": rect_pts,
                        "closed": True,
                    })

            # If the stitched polyline closes (or nearly closes), keep it
            if len(current) >= 3:
                first = current[0]
                last = current[-1]
                closed = (
                    abs(first[0] - last[0]) < 0.5
                    and abs(first[1] - last[1]) < 0.5
                )
                if closed:
                    polygons.append({
                        "kind": "path",
                        "points_pts": current,
                        "closed": True,
                    })

        # Filter polygons: must overlap the bbox, must exceed min_area_pts2
        kept = []
        for poly in polygons:
            pts = poly["points_pts"]
            if bbox is not None:
                # Keep if any vertex is inside the clipped bbox, OR if any
                # vertex is within a small tolerance of it
                if not any(in_bbox(x, y, clipped) for x, y in pts):
                    continue
            area_pts2 = shoelace_area_pts2(pts)
            if area_pts2 < min_area_pts2:
                continue

            entry = {
                "kind": poly["kind"],
                "vertex_count": len(pts),
                "vertices_pts": [[round(x, 2), round(y, 2)] for x, y in pts],
                "area_pts2": round(area_pts2, 2),
                "perimeter_pts": round(polygon_perimeter_pts(pts), 2),
            }
            mm_per_pt = scale.get("mm_per_pt")
            if mm_per_pt is not None:
                area_mm2 = area_pts2 * (mm_per_pt ** 2)
                entry["area_mm2"] = round(area_mm2, 1)
                entry["area_m2"] = round(area_mm2 / 1_000_000.0, 3)
                entry["perimeter_m"] = round(
                    polygon_perimeter_pts(pts) * mm_per_pt / 1000.0, 3
                )
            kept.append(entry)

        # Sort largest first — most queries care about the dominant shape
        kept.sort(key=lambda e: -e["area_pts2"])
        out["polygons"] = kept
        out["polygon_count"] = len(kept)
        if scale.get("mm_per_pt") is not None:
            out["total_area_m2"] = round(
                sum(p.get("area_m2", 0) for p in kept), 3
            )
    finally:
        doc.close()

    return out


# ----------------------------------------------------------------------------
# Text extraction in a region
# ----------------------------------------------------------------------------
def extract_text_in_region(pdf_path: str, bbox: tuple | None) -> dict:
    out = {
        "pdf": pdf_path,
        "bbox_pts": list(bbox) if bbox else None,
        "text_blocks": [],
        "concatenated": "",
    }
    doc = fitz.open(pdf_path)
    try:
        if len(doc) == 0:
            out["error"] = "PDF has no pages"
            return out
        page = doc[0]
        pw, ph = page.rect.width, page.rect.height
        clipped = bbox_clip(bbox, pw, ph) if bbox else (0, 0, pw, ph)

        page_dict = page.get_text("dict")
        blocks = page_dict.get("blocks", [])
        all_text = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    bx = span.get("bbox", [0, 0, 0, 0])
                    cx = (bx[0] + bx[2]) / 2.0
                    cy = (bx[1] + bx[3]) / 2.0
                    if not in_bbox(cx, cy, clipped):
                        continue
                    out["text_blocks"].append({
                        "text": text,
                        "bbox": [round(b, 1) for b in bx],
                        "size": round(span.get("size", 0), 1),
                    })
                    all_text.append(text)
        out["concatenated"] = "\n".join(all_text)
        out["count"] = len(out["text_blocks"])
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# Dimensions
# ----------------------------------------------------------------------------
DIMENSION_REGEX = re.compile(
    r"""
    ^\s*
    (?P<value>\d{1,7}(?:[.,]\d+)?)
    \s*
    (?P<unit>mm|m|cm|ft|in|"|'|)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def extract_dimensions(pdf_path: str, bbox: tuple | None) -> dict:
    """
    Find text objects that look like dimensions (a number, optionally with
    a unit) inside the given bbox. This is heuristic — Claude verifies
    against the visual.
    """
    text_data = extract_text_in_region(pdf_path, bbox)
    out = {
        "pdf": pdf_path,
        "bbox_pts": list(bbox) if bbox else None,
        "dimensions": [],
    }
    for tb in text_data.get("text_blocks", []):
        text = tb["text"]
        m = DIMENSION_REGEX.match(text.replace(" ", ""))
        if not m:
            continue
        try:
            value = float(m.group("value").replace(",", "."))
        except ValueError:
            continue
        out["dimensions"].append({
            "raw_text": text,
            "value": value,
            "unit": (m.group("unit") or "").lower() or None,
            "bbox": tb["bbox"],
        })
    out["count"] = len(out["dimensions"])
    return out


# ----------------------------------------------------------------------------
# Tables
# ----------------------------------------------------------------------------
def extract_tables(pdf_path: str, bbox: tuple | None) -> dict:
    out = {
        "pdf": pdf_path,
        "bbox_pts": list(bbox) if bbox else None,
        "tables": [],
    }
    if not HAVE_PDFPLUMBER:
        out["error"] = "pdfplumber not installed"
        return out

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                out["error"] = "PDF has no pages"
                return out
            page = pdf.pages[0]
            target = page.crop(bbox) if bbox else page
            raw_tables = target.extract_tables()
            for idx, t in enumerate(raw_tables or []):
                # Normalise: pdfplumber returns list[list[str|None]]
                rows = [
                    [(cell.strip() if isinstance(cell, str) else None) for cell in row]
                    for row in t
                ]
                # Drop empty trailing rows / cols
                while rows and not any(c for c in rows[-1]):
                    rows.pop()
                if not rows:
                    continue
                out["tables"].append({
                    "index": idx,
                    "row_count": len(rows),
                    "col_count": max(len(r) for r in rows) if rows else 0,
                    "rows": rows,
                })
            out["count"] = len(out["tables"])
    except Exception as e:
        out["error"] = f"pdfplumber failed: {e}"
    return out


# ----------------------------------------------------------------------------
# Page info
# ----------------------------------------------------------------------------
def page_info(pdf_path: str) -> dict:
    out = {"pdf": pdf_path}
    doc = fitz.open(pdf_path)
    try:
        if len(doc) == 0:
            out["error"] = "PDF has no pages"
            return out
        page = doc[0]
        out["width_pts"] = round(page.rect.width, 2)
        out["height_pts"] = round(page.rect.height, 2)
        out["width_mm"] = round(page.rect.width * MM_PER_POINT, 1)
        out["height_mm"] = round(page.rect.height * MM_PER_POINT, 1)

        # Look for likely scale strings in the title-block zone
        page_dict = page.get_text("dict")
        scale_candidates = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    if re.search(r"\b1\s*[:/]\s*\d+\b", text):
                        scale_candidates.append({
                            "text": text,
                            "bbox": [round(b, 1) for b in span.get("bbox", [])],
                        })
        out["scale_candidates"] = scale_candidates
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def add_bbox_arg(p):
    p.add_argument(
        "--bbox", nargs=4, type=float, default=None,
        metavar=("X0", "Y0", "X1", "Y1"),
        help="Region in PDF points. Origin top-left. Omit for full page.",
    )


def add_scale_args(p):
    p.add_argument("--scale", default=None,
                   help="Drawing scale, e.g. '1:100'. Required for area/length conversion.")
    p.add_argument("--mm-per-pt", type=float, default=None,
                   help="Override scale with explicit mm-per-point factor.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_poly = sub.add_parser("polygons", help="Closed polygons + areas")
    p_poly.add_argument("pdf_path")
    add_bbox_arg(p_poly)
    add_scale_args(p_poly)
    p_poly.add_argument("--min-area-pts2", type=float, default=100.0,
                        help="Filter out polygons smaller than this (default 100 pts²)")

    p_text = sub.add_parser("text", help="Every text object in a region")
    p_text.add_argument("pdf_path")
    add_bbox_arg(p_text)

    p_dim = sub.add_parser("dimensions", help="Text that looks like a dimension")
    p_dim.add_argument("pdf_path")
    add_bbox_arg(p_dim)

    p_tab = sub.add_parser("tables", help="Structured tables (full sheet or region)")
    p_tab.add_argument("pdf_path")
    add_bbox_arg(p_tab)

    p_info = sub.add_parser("page-info", help="Page size + scale candidates")
    p_info.add_argument("pdf_path")

    args = ap.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "polygons":
        scale = parse_scale(args.scale, args.mm_per_pt)
        result = extract_polygons(
            args.pdf_path, tuple(args.bbox) if args.bbox else None, scale,
            min_area_pts2=args.min_area_pts2,
        )
    elif args.cmd == "text":
        result = extract_text_in_region(
            args.pdf_path, tuple(args.bbox) if args.bbox else None
        )
    elif args.cmd == "dimensions":
        result = extract_dimensions(
            args.pdf_path, tuple(args.bbox) if args.bbox else None
        )
    elif args.cmd == "tables":
        result = extract_tables(
            args.pdf_path, tuple(args.bbox) if args.bbox else None
        )
    elif args.cmd == "page-info":
        result = page_info(args.pdf_path)
    else:
        ap.error(f"Unknown command {args.cmd}")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
