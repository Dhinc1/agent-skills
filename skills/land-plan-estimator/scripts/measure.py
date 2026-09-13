#!/usr/bin/env python3
"""
Measurement engine for land-plan-estimator (v2).

This is the "plumbing" half of the skill: deterministic geometry and text
extraction. All *judgement* — which tags to count, which region holds the
pond, what scale the sheet is, which line style is the storm pipe — is
supplied by Claude on the command line. The script never guesses what
anything *means*; it only measures what it is told to measure.

Ported from ContractorOS's construction-takeoff/scripts/measure.py, with one
material change: this business works exclusively in US customary units
(feet, SY, CY, acres — never metric), so every output is in FEET, not
millimetres/metres. Everything else — the words-mode text extraction, the
imperial+metric scale parser, rotated-sheet handling, the count segmentation
logic, the Bluebeam-safe render/markup commands — is unchanged from a
design already validated on real US civil sets.

Sub-commands:
    count       — count occurrences of exact text tokens in the vector text
                  layer (the reliable way to count tagged items: structure
                  numbers, curb inlet marks, plant-schedule tags). Supports
                  include/exclude regions so schedule/legend definitions
                  aren't counted as real plan instances.
    polygons    — closed polygons in a region + area (SF, and acres with
                  scale). For basins, pavement zones, clearing limits,
                  buffer areas — anything area-based.
    length      — open AND closed polylines in a region + length in feet,
                  with stroke colour/width so a specific line style (a storm
                  run, a curb line, a sewer main) can be isolated and summed.
    dimensions  — text that looks like an annotated dimension in a region.
                  Prefer a stated dimension over computed geometry when both
                  exist — a called-out "125.00'" beats a scaled polyline.
    tables      — structured tables (pipe schedules, structure schedules,
                  plant schedules) via pdfplumber.
    text        — every text object in a region (exact characters + bbox).
    page-info   — page size + scale candidates from the title block.
    render      — rasterise a page/region to PNG, optional coordinate grid
                  overlay (for reading off a bbox to pass back in).
    markup      — apply a markup spec (translucent boxes/outlines) to a PDF.

All bbox arguments are PDF points (1pt = 1/72 inch), origin top-left — the
same coordinate system split_extract.py's per-sheet JSON uses. Pass scale as
a ratio (`--scale 1:100`), an engineering/architectural imperial notation
(`--scale "1\"=20'"` or `--scale "1/8=1'-0"`), or an explicit factor
(`--ft-per-pt`).

Usage examples:
    # Count storm structure tags in the drawing area, excluding the schedule box
    python measure.py count "sheet_015.pdf" --tags "1A-1" "1A-2" "1A-3" \\
        --bbox 60 60 1500 980 --exclude-bbox 1500 980 1850 1180

    # Pond/basin area (feet + acres)
    python measure.py polygons "sheet_022.pdf" --bbox 80 50 1620 720 --scale "1\"=50'"

    # Length of a storm run (then filter by stroke in the output)
    python measure.py length "sheet_015.pdf" --bbox 200 200 1400 900 --scale "1\"=50'"

    # Pipe schedule contents
    python measure.py tables "sheet_015.pdf" --bbox 1180 730 1820 1100
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


FT_PER_POINT = (1.0 / 72.0) / 12.0  # 1 pdf point = 1/72 inch = 1/864 ft
SF_PER_ACRE = 43560.0


# ----------------------------------------------------------------------------
# Scale handling — imperial-first. A ratio N means "1 drawing unit = N
# real-world units", so real_ft = points * (1/72 in/pt) * (1/12 ft/in) * N
#                                = points * N / 864 = points * N * FT_PER_POINT
# ----------------------------------------------------------------------------
def parse_scale(scale_str, ft_per_pt_override):
    """Resolve a scale spec into a single ft-per-point factor.

    Real-world feet = pdf_points x ft_per_pt. Returns ft_per_pt=None when no
    scale was supplied, which downstream code treats as "report points only"
    — never silently assume a scale.
    """
    if ft_per_pt_override is not None:
        return {"ft_per_pt": float(ft_per_pt_override),
                "scale_label": f"{ft_per_pt_override:.6f} ft/pt", "source": "explicit_ft_per_pt"}
    if not scale_str:
        return {"ft_per_pt": None, "scale_label": None, "source": None}

    # Engineering/architectural imperial, e.g. 1"=20', 1"=50', 1/8"=1'-0".
    import fractions as _fr
    _imp = scale_str.strip().lower().replace('"', '').replace(' ', '')
    _m = re.match(r"^(\d+(?:/\d+)?)=(\d+)'(?:-?(\d+))?$", _imp)
    if _m:
        paper_in = float(_fr.Fraction(_m.group(1)))
        real_in = float(_m.group(2)) * 12 + (float(_m.group(3)) if _m.group(3) else 0.0)
        ratio = real_in / paper_in  # 1:N factor
        return {"ft_per_pt": ratio * FT_PER_POINT,
                "scale_label": f"{scale_str} (1:{int(round(ratio))})", "source": "imperial"}

    # Bare ratio, e.g. "1:240" or "240" (also accepts a metric-style "1:100" —
    # the ratio is unitless, it just means real_ft = N x drawing_ft).
    match = re.match(r"^\s*1?\s*[:/]?\s*(\d+(?:\.\d+)?)\s*$", scale_str)
    if not match:
        raise ValueError(f"Could not parse scale {scale_str!r}. Use '1:240', '1\"=20\\'', or --ft-per-pt.")
    denominator = float(match.group(1))
    return {
        "ft_per_pt": denominator * FT_PER_POINT,
        "scale_label": f"1:{int(denominator) if denominator.is_integer() else denominator}",
        "source": "ratio",
    }


# ----------------------------------------------------------------------------
# Geometry helpers
# ----------------------------------------------------------------------------
def bbox_clip(bbox, page_w, page_h):
    x0, y0, x1, y1 = bbox
    x0 = max(0.0, min(x0, page_w)); x1 = max(0.0, min(x1, page_w))
    y0 = max(0.0, min(y0, page_h)); y1 = max(0.0, min(y1, page_h))
    if x1 < x0: x0, x1 = x1, x0
    if y1 < y0: y0, y1 = y1, y0
    return (x0, y0, x1, y1)


def native_bounds(page):
    """The page rect in the UN-rotated coordinate system that get_text() and
    get_drawings() actually return. page.rect is the rotated/display rect, so
    on a rotated sheet (common for large-format civil exports) the two
    differ — clipping text against page.rect silently drops everything past
    the rotated edge. Always clip against this instead."""
    r = page.rect * page.derotation_matrix
    return (min(r.x0, r.x1), min(r.y0, r.y1), max(r.x0, r.x1), max(r.y0, r.y1))


def to_native_bbox(bbox, page):
    """Convert a bbox read off a (rotated/display) render into the native
    coordinate space used by the text/vector layers, so region include/exclude
    boxes line up. Identity on un-rotated pages."""
    r = fitz.Rect(*bbox) * page.derotation_matrix
    return (min(r.x0, r.x1), min(r.y0, r.y1), max(r.x0, r.x1), max(r.y0, r.y1))


def shoelace_area_pts2(points):
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def polyline_length_pts(points, closed):
    n = len(points)
    if n < 2:
        return 0.0
    total = 0.0
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def in_bbox(x, y, bbox):
    x0, y0, x1, y1 = bbox
    return (x0 <= x <= x1) and (y0 <= y <= y1)


def in_any_bbox(x, y, bboxes):
    return any(in_bbox(x, y, b) for b in bboxes)


def color_to_hex(c):
    if not c:
        return None
    try:
        return "#" + "".join(f"{int(round(v * 255)):02X}" for v in c[:3])
    except Exception:
        return None


def hex_to_rgb(h):
    if not h:
        return None
    h = h.lstrip("#")
    if len(h) != 6:
        return None
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# ----------------------------------------------------------------------------
# count — the reliable way to count tagged items
# ----------------------------------------------------------------------------
def _normalise(s, case_insensitive):
    s = s.strip()
    return s.upper() if case_insensitive else s


def _tokenise(s):
    # Split on whitespace and the punctuation that typically frames a tag on
    # a drawing (commas, slashes, brackets, dashes, leader dots, apostrophes).
    # NOT a semantic pattern — just word boundaries, so "1A-1,1A-2" and
    # "(FES)" both yield their tags. NOTE: civil tags are usually hyphenated
    # (structure "1A-11", pipe class "CL III") — the segmenter below keeps
    # hyphens INSIDE a matched vocabulary tag; only the tokeniser splits on
    # bare stray hyphens between unrelated tokens.
    return [t for t in re.split(r"[\s,/()\[\]{}.']+", s) if t]


def _segment(piece, vocab_sorted):
    """Greedily split a delimiter-free text run into a sequence of known tags.

    CAD exports often jam adjacent tags into one text span with no separator.
    This walks the run left-to-right, matching the LONGEST vocabulary tag at
    each position, and returns the list of tags if the whole run is consumed
    cleanly. Returns None if anything is left over — which is what keeps
    unrelated runs from being mistaken for tags. The vocabulary is the exact
    set of strings Claude supplied; this is not pattern inference.
    """
    i, n, out = 0, len(piece), []
    while i < n:
        m = next((v for v in vocab_sorted if piece.startswith(v, i)), None)
        if m is None:
            return None
        out.append(m)
        i += len(m)
    return out or None


def count_tags(pdf_path, tags, bbox, exclude_bboxes, mode, case_insensitive, exclude_bboxes_native=None):
    """Count occurrences of each tag string in the vector text layer.

    mode:
      token    — default. Split each text object on word boundaries, then
                 segment each piece against the supplied tag vocabulary
                 (longest-match). A piece that doesn't fully segment into
                 known tags counts nothing.
      exact    — match only if the whole (trimmed) text object equals the tag.
      contains — substring count (use sparingly — "1A-1" hides inside "1A-11").
    """
    out = {
        "pdf": pdf_path, "mode": mode, "case_insensitive": case_insensitive,
        "bbox_pts": list(bbox) if bbox else None,
        "exclude_bbox_pts": [list(b) for b in exclude_bboxes] if exclude_bboxes else [],
        "counts": {},
    }
    targets = {t: _normalise(t, case_insensitive) for t in tags}
    norm_to_tag = {}
    for t, nt in targets.items():
        norm_to_tag.setdefault(nt, t)
    vocab_sorted = sorted(norm_to_tag.keys(), key=len, reverse=True)
    results = {t: {"count": 0, "locations": []} for t in tags}

    def add(tag, x, y, box, raw):
        results[tag]["count"] += 1
        results[tag]["locations"].append({
            "x": round(x, 1), "y": round(y, 1),
            "box": [round(v, 1) for v in box], "text": raw,
        })

    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        nb = native_bounds(page)
        clip = to_native_bbox(bbox, page) if bbox else nb
        excl = [to_native_bbox(b, page) for b in exclude_bboxes] if exclude_bboxes else []
        if exclude_bboxes_native:
            excl = excl + [tuple(b) for b in exclude_bboxes_native]

        # "words" extraction (not dict spans) — dict-mode can silently drop
        # text held in form XObjects on many CAD exports, undercounting badly.
        for w in page.get_text("words"):
            x0, y0, x1, y1, raw = w[0], w[1], w[2], w[3], w[4]
            if not raw.strip():
                continue
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            if not in_bbox(cx, cy, clip):
                continue
            if excl and in_any_bbox(cx, cy, excl):
                continue
            norm = _normalise(raw, case_insensitive)

            if mode == "exact":
                if norm in norm_to_tag:
                    add(norm_to_tag[norm], cx, cy, (x0, y0, x1, y1), raw.strip())
                continue
            if mode == "contains":
                for nt in vocab_sorted:
                    for _ in range(norm.count(nt)):
                        add(norm_to_tag[nt], cx, cy, (x0, y0, x1, y1), raw.strip())
                continue

            for piece in _tokenise(norm):
                seg = _segment(piece, vocab_sorted)
                if not seg:
                    continue
                k = len(seg)
                for j, nt in enumerate(seg):
                    sx0 = x0 + j / k * (x1 - x0)
                    sx1 = x0 + (j + 1) / k * (x1 - x0)
                    add(norm_to_tag[nt], (sx0 + sx1) / 2, cy, (sx0, y0, sx1, y1), raw.strip())
        out["counts"] = results
        out["total"] = sum(r["count"] for r in results.values())
    finally:
        doc.close()
    return out


MARKUP_PALETTE = [
    "#E53935", "#8E24AA", "#3949AB", "#039BE5", "#00897B", "#7CB342", "#FDD835",
    "#FB8C00", "#6D4C41", "#546E7A", "#D81B60", "#00ACC1", "#C0CA33", "#5E35B1",
    "#43A047", "#F4511E", "#1E88E5", "#8D6E63", "#EC407A", "#26A69A",
]


def build_markup_spec(count_result, page=1, opacity=0.35):
    """Turn a count result into a markup spec — one translucent box per
    COUNTED location. Returns (spec, legend). No text stamps — they'd render
    rotated on rotated sheets; the colour<->tag<->count legend goes in the
    workbook notes instead."""
    counts = count_result.get("counts", {})
    ops, legend = [], []
    for i, (tag, data) in enumerate(counts.items()):
        if not data["count"]:
            continue
        color = MARKUP_PALETTE[i % len(MARKUP_PALETTE)]
        legend.append({"tag": tag, "color": color, "count": data["count"]})
        for loc in data["locations"]:
            x0, y0, x1, y1 = loc["box"]
            pad = 2.0
            ops.append({
                "type": "box", "page": page,
                "rect": [x0 - pad, y0 - pad, x1 + pad, y1 + pad],
                "color": color, "fill": color, "opacity": opacity, "width": 0,
            })
    return {"page": page, "ops": ops}, legend


# ----------------------------------------------------------------------------
# polygons — area (SF + acres)
# ----------------------------------------------------------------------------
def _stitch_paths(page, bbox):
    clip = to_native_bbox(bbox, page) if bbox else native_bounds(page)
    paths = []
    for d in page.get_drawings():
        items = d.get("items", []) or []
        if not items:
            continue
        stroke_hex = color_to_hex(d.get("color"))
        width = d.get("width")
        current = []
        for it in items:
            op = it[0]
            if op == "l" and len(it) >= 3:
                p0, p1 = it[1], it[2]
                if not current:
                    current.append((p0.x, p0.y))
                current.append((p1.x, p1.y))
            elif op == "c" and len(it) >= 5:
                p3 = it[4]
                if not current:
                    p0 = it[1]; current.append((p0.x, p0.y))
                current.append((p3.x, p3.y))
            elif op == "re" and len(it) >= 2:
                r = it[1]
                paths.append({
                    "points": [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)],
                    "closed": True, "stroke_hex": stroke_hex,
                    "width": round(width, 2) if width else None,
                })
        if len(current) >= 2:
            first, last = current[0], current[-1]
            closed = abs(first[0] - last[0]) < 0.5 and abs(first[1] - last[1]) < 0.5
            paths.append({
                "points": current, "closed": closed, "stroke_hex": stroke_hex,
                "width": round(width, 2) if width else None,
            })
    kept = []
    for p in paths:
        if bbox is None or any(in_bbox(x, y, clip) for x, y in p["points"]):
            kept.append(p)
    return kept


def extract_polygons(pdf_path, bbox, scale, min_area_pts2=100.0):
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "scale": scale, "polygons": []}
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        ft = scale.get("ft_per_pt")
        kept = []
        for p in _stitch_paths(page, bbox):
            if not p["closed"] or len(p["points"]) < 3:
                continue
            a = shoelace_area_pts2(p["points"])
            if a < min_area_pts2:
                continue
            entry = {
                "vertex_count": len(p["points"]),
                "vertices_pts": [[round(x, 2), round(y, 2)] for x, y in p["points"]],
                "area_pts2": round(a, 2),
                "perimeter_pts": round(polyline_length_pts(p["points"], True), 2),
                "stroke_hex": p["stroke_hex"], "width": p["width"],
            }
            if ft is not None:
                area_sf = a * (ft ** 2)
                entry["area_sf"] = round(area_sf, 1)
                entry["area_ac"] = round(area_sf / SF_PER_ACRE, 4)
                entry["area_sy"] = round(area_sf / 9.0, 1)
                entry["perimeter_ft"] = round(polyline_length_pts(p["points"], True) * ft, 1)
            kept.append(entry)
        kept.sort(key=lambda e: -e["area_pts2"])
        out["polygons"] = kept
        out["polygon_count"] = len(kept)
        if ft is not None:
            out["total_area_sf"] = round(sum(p.get("area_sf", 0) for p in kept), 1)
            out["total_area_ac"] = round(sum(p.get("area_ac", 0) for p in kept), 4)
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# length — linear measurement (feet)
# ----------------------------------------------------------------------------
def extract_lengths(pdf_path, bbox, scale, min_len_pts=5.0):
    """Return polylines (open and closed) in a region with length + stroke.

    Claude isolates the item being measured by stroke colour/width (read off
    the line-type legend) and by region, then sums the matching polylines.
    Annotated length labels (via `dimensions`) are preferred when present —
    a called-out "125.00'" beats a computed polyline every time.
    """
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "scale": scale, "polylines": []}
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        ft = scale.get("ft_per_pt")
        kept = []
        for p in _stitch_paths(page, bbox):
            L = polyline_length_pts(p["points"], p["closed"])
            if L < min_len_pts:
                continue
            entry = {
                "vertex_count": len(p["points"]),
                "closed": p["closed"],
                "length_pts": round(L, 2),
                "stroke_hex": p["stroke_hex"], "width": p["width"],
                "start_pts": [round(p["points"][0][0], 1), round(p["points"][0][1], 1)],
                "end_pts": [round(p["points"][-1][0], 1), round(p["points"][-1][1], 1)],
            }
            if ft is not None:
                entry["length_ft"] = round(L * ft, 1)
            kept.append(entry)
        kept.sort(key=lambda e: -e["length_pts"])
        out["polylines"] = kept
        out["polyline_count"] = len(kept)
        if ft is not None:
            out["total_length_ft"] = round(sum(p.get("length_ft", 0) for p in kept), 1)
        by_stroke = {}
        for p in kept:
            key = f"{p['stroke_hex']}|{p['width']}"
            g = by_stroke.setdefault(key, {"stroke_hex": p["stroke_hex"], "width": p["width"], "count": 0, "length_pts": 0.0})
            g["count"] += 1
            g["length_pts"] += p["length_pts"]
        if ft is not None:
            for g in by_stroke.values():
                g["length_ft"] = round(g["length_pts"] * ft, 1)
        out["by_stroke"] = sorted(by_stroke.values(), key=lambda g: -g["length_pts"])
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# text / dimensions / tables / page-info
# ----------------------------------------------------------------------------
def extract_text_in_region(pdf_path, bbox):
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "text_blocks": [], "concatenated": ""}
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        clip = to_native_bbox(bbox, page) if bbox else native_bounds(page)
        all_text = []
        for w in page.get_text("words"):
            x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4].strip()
            if not text:
                continue
            cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            if not in_bbox(cx, cy, clip):
                continue
            out["text_blocks"].append({"text": text, "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]})
            all_text.append(text)
        out["concatenated"] = " ".join(all_text)
        out["count"] = len(out["text_blocks"])
    finally:
        doc.close()
    return out


# Matches a bare number + optional unit (ft/in/'/"), AND a feet-inches
# callout like 125'-6" or 45'. Civil callouts are overwhelmingly feet.
DIMENSION_REGEX = re.compile(
    r"^\s*(?P<feet>\d{1,6}(?:\.\d+)?)\s*'(?:\s*-?\s*(?P<inches>\d{1,2}(?:\.\d+)?)\s*\")?\s*$"
    r"|^\s*(?P<value>\d{1,7}(?:[.,]\d+)?)\s*(?P<unit>mm|m|cm|ft|in|\"|'|)\s*$",
    re.IGNORECASE)


def extract_dimensions(pdf_path, bbox):
    """Find dimension-shaped text (a bare number, a feet-inches callout like
    125'-6", or a number+unit). Heuristic on SHAPE only, not meaning — Claude
    reads what each dimension refers to from its position and verifies
    against the visual. Bearings/curve data (N45*12'33"E, curve tables) are
    NOT parsed here — read those off the render."""
    td = extract_text_in_region(pdf_path, bbox)
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "dimensions": []}
    for tb in td.get("text_blocks", []):
        raw = tb["text"]
        m = DIMENSION_REGEX.match(raw.replace(" ", ""))
        if not m:
            continue
        gd = m.groupdict()
        if gd.get("feet") is not None:
            try:
                value_ft = float(gd["feet"]) + (float(gd["inches"]) / 12.0 if gd.get("inches") else 0.0)
            except ValueError:
                continue
            out["dimensions"].append({"raw_text": raw, "value_ft": round(value_ft, 3), "unit": "ft-in", "bbox": tb["bbox"]})
            continue
        try:
            value = float(gd["value"].replace(",", "."))
        except (ValueError, TypeError):
            continue
        unit = (gd.get("unit") or "").lower() or None
        entry = {"raw_text": raw, "value": value, "unit": unit, "bbox": tb["bbox"]}
        if unit in ("ft", "'", None):
            entry["value_ft"] = value
        out["dimensions"].append(entry)
    out["count"] = len(out["dimensions"])
    return out


def extract_tables(pdf_path, bbox):
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "tables": []}
    if not HAVE_PDFPLUMBER:
        out["error"] = "pdfplumber not installed (pip install pdfplumber --break-system-packages)"
        return out
    # Don't rely on table auto-detection to LOCATE a schedule on a busy sheet
    # — pdfplumber latches onto sheet gridlines and returns a page-spanning
    # "table". Crop to the schedule region (pass --bbox) to read its rows
    # reliably.
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            target = page.crop(bbox) if bbox else page
            for idx, t in enumerate(target.extract_tables() or []):
                rows = [[(c.strip() if isinstance(c, str) else None) for c in row] for row in t]
                while rows and not any(c for c in rows[-1]):
                    rows.pop()
                if rows:
                    out["tables"].append({"index": idx, "row_count": len(rows),
                                          "col_count": max(len(r) for r in rows), "rows": rows})
            out["count"] = len(out["tables"])
    except Exception as e:
        out["error"] = f"pdfplumber failed: {e}"
    return out


# ----------------------------------------------------------------------------
# render + markup — self-contained
# ----------------------------------------------------------------------------
def _auto_step(region):
    span = max(region[2] - region[0], region[3] - region[1])
    for s in (25, 50, 100, 200, 500, 1000):
        if span / s <= 40:
            return s
    return 1000


def _draw_grid(img, region, scale, step):
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(10, int(8 * scale)))
    except Exception:
        font = ImageFont.load_default()
    x0, y0, x1, y1 = region
    minor, major = (160, 160, 160, 90), (90, 90, 220, 150)
    xx = int(x0 // step) * step
    while xx <= x1:
        if xx >= x0:
            px = (xx - x0) * scale
            mj = (xx % (step * 5) == 0)
            draw.line([(px, 0), (px, img.height)], fill=major if mj else minor, width=1)
            if mj:
                draw.text((px + 2, 2), str(int(xx)), fill=(20, 20, 160, 255), font=font)
        xx += step
    yy = int(y0 // step) * step
    while yy <= y1:
        if yy >= y0:
            py = (yy - y0) * scale
            mj = (yy % (step * 5) == 0)
            draw.line([(0, py), (img.width, py)], fill=major if mj else minor, width=1)
            if mj:
                draw.text((2, py + 2), str(int(yy)), fill=(20, 20, 160, 255), font=font)
        yy += step
    return img


def render_page(pdf_path, page_no, dpi, region, grid, grid_step, out):
    doc = fitz.open(pdf_path)
    try:
        p = doc[page_no - 1]
        clip = fitz.Rect(*region) if region else None
        regbox = region if region else (0, 0, p.rect.width, p.rect.height)
        scale = dpi / 72.0
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        if grid:
            from PIL import Image
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            _draw_grid(img, regbox, scale, grid_step or _auto_step(regbox))
            img.save(out)
        else:
            pix.save(out)
        return {"out": out, "px": [pix.width, pix.height], "dpi": dpi, "region": [round(v, 1) for v in regbox]}
    finally:
        doc.close()


def apply_markup(pdf_path, spec, out):
    """Quick-look markup via PyMuPDF annotations. NOTE: this is for quick
    on-screen checks only. The FINAL deliverable markup must go through the
    pikepdf overlay method in SKILL.md Step 6 — a PyMuPDF-saved PDF does not
    open in Bluebeam Revu (it rewrites the document structure)."""
    doc = fitz.open(pdf_path)
    try:
        applied = 0
        for op in spec.get("ops", []):
            page = doc[op.get("page", 1) - 1]
            t = op.get("type", "box")
            color = hex_to_rgb(op.get("color", "#E53935"))
            fill = hex_to_rgb(op.get("fill"))
            if t in ("box", "rect"):
                an = page.add_rect_annot(fitz.Rect(*op["rect"]))
                an.set_colors(stroke=color, fill=fill)
                an.set_border(width=op.get("width", 0))
            elif t == "line":
                pts = op.get("points") or [op["start"], op["end"]]
                an = page.add_line_annot(fitz.Point(*pts[0]), fitz.Point(*pts[-1]))
                an.set_colors(stroke=color)
                an.set_border(width=op.get("width", 2))
            elif t in ("cloud", "polygon"):
                an = page.add_polygon_annot([fitz.Point(*p) for p in op["points"]])
                an.set_colors(stroke=color, fill=fill)
                an.set_border(width=op.get("width", 2))
            elif t == "polyline":
                an = page.add_polyline_annot([fitz.Point(*p) for p in op["points"]])
                an.set_colors(stroke=color)
                an.set_border(width=op.get("width", 2))
            else:
                continue
            if op.get("opacity") is not None:
                an.set_opacity(op["opacity"])
            an.update()
            applied += 1
        doc.save(out)
        return {"out": out, "applied": applied}
    finally:
        doc.close()


def page_info(pdf_path):
    out = {"pdf": pdf_path}
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        out["width_pts"] = round(page.rect.width, 2); out["height_pts"] = round(page.rect.height, 2)
        out["width_ft"] = round(page.rect.width * FT_PER_POINT, 2)
        out["height_ft"] = round(page.rect.height * FT_PER_POINT, 2)
        cands = []
        scale_re = re.compile(
            r"(\b1\s*[:/]\s*\d+\b)"
            r"|(\d+(?:/\d+)?\s*\"?\s*=\s*\d+'\s*-?\s*\d*\s*\"?)"
            r"|(\bN\.?T\.?S\.?\b|AS\s+INDICATED|\bSCALE\b)",
            re.IGNORECASE)
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text and scale_re.search(text):
                        cands.append({"text": text, "bbox": [round(b, 1) for b in span.get("bbox", [])]})
        out["scale_candidates"] = cands
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def add_bbox(p):
    p.add_argument("--bbox", nargs=4, type=float, default=None, metavar=("X0", "Y0", "X1", "Y1"),
                   help="Region in PDF points (origin top-left). Omit for full page.")


def add_scale(p):
    p.add_argument("--scale", default=None,
                   help="Drawing scale: '1:240', or engineering/architectural imperial "
                        "like '1\"=20\\'' or '1/8=1\\'-0'. Required for real-world units.")
    p.add_argument("--ft-per-pt", type=float, default=None, help="Override scale with explicit ft-per-point factor.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("count", help="Count exact text tokens (tagged-item counting)")
    pc.add_argument("pdf_path")
    pc.add_argument("--tags", nargs="+", required=True, help="Exact tag strings to count, learned from the legend/schedules.")
    add_bbox(pc)
    pc.add_argument("--exclude-bbox", nargs=4, type=float, action="append", default=None, metavar=("X0", "Y0", "X1", "Y1"),
                    help="Region to exclude in RENDER/display coords (converted to native). Repeatable.")
    pc.add_argument("--exclude-bbox-native", nargs=4, type=float, action="append", default=None, metavar=("X0", "Y0", "X1", "Y1"),
                    help="Region to exclude in NATIVE coords (the same space count REPORTS hit x/y). Repeatable.")
    pc.add_argument("--mode", choices=["token", "exact", "contains"], default="token")
    pc.add_argument("--case-insensitive", action="store_true")
    pc.add_argument("--markup-out", default=None, help="Write a markup spec (translucent boxes for the COUNTED hits only) to this path.")
    pc.add_argument("--markup-page", type=int, default=1, help="Page number to stamp on the markup ops. Default 1.")

    pp = sub.add_parser("polygons", help="Closed polygons + area (SF, acres)")
    pp.add_argument("pdf_path"); add_bbox(pp); add_scale(pp)
    pp.add_argument("--min-area-pts2", type=float, default=100.0)

    pl = sub.add_parser("length", help="Open + closed polylines + length in feet, with stroke")
    pl.add_argument("pdf_path"); add_bbox(pl); add_scale(pl)
    pl.add_argument("--min-len-pts", type=float, default=5.0)

    pt = sub.add_parser("text", help="Every text object in a region")
    pt.add_argument("pdf_path"); add_bbox(pt)

    pd = sub.add_parser("dimensions", help="Dimension-shaped text in a region")
    pd.add_argument("pdf_path"); add_bbox(pd)

    pb = sub.add_parser("tables", help="Structured tables (full sheet or region)")
    pb.add_argument("pdf_path"); add_bbox(pb)

    pi = sub.add_parser("page-info", help="Page size + scale candidates")
    pi.add_argument("pdf_path")

    prn = sub.add_parser("render", help="Rasterise a page/region to PNG (display coords; optional grid)")
    prn.add_argument("pdf_path")
    prn.add_argument("--page", type=int, default=1)
    prn.add_argument("--dpi", type=int, default=110)
    prn.add_argument("--region", nargs=4, type=float, default=None, metavar=("X0", "Y0", "X1", "Y1"))
    prn.add_argument("--grid", action="store_true")
    prn.add_argument("--grid-step", type=float, default=None)
    prn.add_argument("--out", required=True)

    pm = sub.add_parser("markup", help="Quick-look markup only — see docstring. Final markup uses the pikepdf method in SKILL.md.")
    pm.add_argument("pdf_path")
    pm.add_argument("--spec", required=True, help="Path to a markup spec JSON (e.g. from count --markup-out)")
    pm.add_argument("--out", required=True)

    args = ap.parse_args()
    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    if args.cmd == "count":
        excl = [tuple(b) for b in args.exclude_bbox] if args.exclude_bbox else []
        excl_n = [tuple(b) for b in args.exclude_bbox_native] if args.exclude_bbox_native else []
        result = count_tags(args.pdf_path, args.tags,
                            tuple(args.bbox) if args.bbox else None,
                            excl, args.mode, args.case_insensitive,
                            exclude_bboxes_native=excl_n)
        if args.markup_out:
            spec, legend = build_markup_spec(result, page=args.markup_page)
            with open(args.markup_out, "w") as fh:
                json.dump(spec, fh, indent=2)
            result["markup_out"] = args.markup_out
            result["legend"] = legend
        print(json.dumps(result, indent=2))

    elif args.cmd == "polygons":
        scale = parse_scale(args.scale, args.ft_per_pt)
        result = extract_polygons(args.pdf_path, tuple(args.bbox) if args.bbox else None,
                                  scale, args.min_area_pts2)
        print(json.dumps(result, indent=2))

    elif args.cmd == "length":
        scale = parse_scale(args.scale, args.ft_per_pt)
        result = extract_lengths(args.pdf_path, tuple(args.bbox) if args.bbox else None,
                                 scale, args.min_len_pts)
        print(json.dumps(result, indent=2))

    elif args.cmd == "text":
        result = extract_text_in_region(args.pdf_path, tuple(args.bbox) if args.bbox else None)
        print(json.dumps(result, indent=2))

    elif args.cmd == "dimensions":
        result = extract_dimensions(args.pdf_path, tuple(args.bbox) if args.bbox else None)
        print(json.dumps(result, indent=2))

    elif args.cmd == "tables":
        result = extract_tables(args.pdf_path, tuple(args.bbox) if args.bbox else None)
        print(json.dumps(result, indent=2))

    elif args.cmd == "page-info":
        print(json.dumps(page_info(args.pdf_path), indent=2))

    elif args.cmd == "render":
        result = render_page(args.pdf_path, args.page, args.dpi, args.region,
                             args.grid, args.grid_step, args.out)
        print(json.dumps(result, indent=2))

    elif args.cmd == "markup":
        with open(args.spec) as fh:
            spec = json.load(fh)
        result = apply_markup(args.pdf_path, spec, args.out)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
