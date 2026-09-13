#!/usr/bin/env python3
"""
Measurement engine for construction-takeoff.

This is the "plumbing" half of the skill: deterministic geometry and text
extraction. All *judgement* — which tags to count, which region holds the
slab, which line style is the cable tray, what scale the sheet is — is
supplied by Claude on the command line. The script never guesses what
anything *means*; it only measures what it is told to measure.

That division is deliberate. The old version of this skill carried a
hardcoded dictionary of tag patterns (L\\d+ = light, F\\d+ = footing, ...),
which broke the moment a drawing office used a different convention. Here,
Claude reads the legend and schedules to learn this set's vocabulary, then
passes the exact tokens to `count`. The same token ("F1") can mean a footing
on one job and a fire damper on another — only the human-readable legend
knows, and Claude has read it.

Sub-commands:
    count       — count occurrences of exact text tokens in the vector text
                  layer (the reliable way to count tagged items). Supports
                  include/exclude regions so legend/title-block/schedule
                  definitions aren't counted as real instances.
    polygons    — closed polygons in a region + area (mm² and m² with scale).
                  For slabs, rooms, zones, hardstand — anything area-based.
    length      — open AND closed polylines in a region + length, with stroke
                  colour/width so a specific line style (a pipe run, a cable
                  tray, a kerb line) can be isolated and summed.
    dimensions  — text that looks like an annotated dimension in a region.
                  Prefer these over computed geometry when they exist.
    tables      — structured tables (schedules) via pdfplumber.
    text        — every text object in a region (exact characters + bbox).
    page-info   — page size + scale candidates from the title block.

All bbox arguments are PDF points (1pt = 1/72 inch), origin top-left — the
same coordinate system the per-sheet extraction JSON uses. Pass scale as a
ratio (`--scale 1:100`) or an explicit factor (`--mm-per-pt 4.233`).

Usage examples:
    # Count two light types in the drawing area, excluding the legend box
    python measure.py count "E-101.pdf" --tags L1 L2 \\
        --bbox 60 60 1500 980 --exclude-bbox 1500 980 1850 1180

    # Slab area
    python measure.py polygons "S-101.pdf" --bbox 80 50 1620 720 --scale 1:100

    # Length of the pipe runs in a region (then filter by stroke in the output)
    python measure.py length "H-201.pdf" --bbox 200 200 1400 900 --scale 1:100

    # Footing schedule contents
    python measure.py tables "S-101.pdf" --bbox 1180 730 1820 1100
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


MM_PER_POINT = 25.4 / 72.0  # 1 point = 1/72 inch


# ----------------------------------------------------------------------------
# Scale handling
# ----------------------------------------------------------------------------
def parse_scale(scale_str, mm_per_pt):
    """Resolve a scale spec into a single mm-per-point factor.

    Real-world mm = pdf_points x mm_per_pt. Returns mm_per_pt=None when no
    scale was supplied, which downstream code treats as "report points only".
    """
    if mm_per_pt is not None:
        return {"mm_per_pt": float(mm_per_pt), "scale_label": f"{mm_per_pt:.4f} mm/pt", "source": "explicit_mm_per_pt"}
    if not scale_str:
        return {"mm_per_pt": None, "scale_label": None, "source": None}
    # Imperial architectural / engineering scales, e.g. 1/8"=1'-0", 1/4"=1'0", 1"=20'.
    # Pass with quotes stripped is fine too (e.g. "1/8=1'-0"). Converts to a 1:N ratio.
    import fractions as _fr
    _imp = scale_str.strip().lower().replace('"', '').replace(' ', '')
    _m = re.match(r"^(\d+(?:/\d+)?)=(\d+)'(?:-?(\d+))?$", _imp)
    if _m:
        paper_in = float(_fr.Fraction(_m.group(1)))
        real_in = float(_m.group(2)) * 12 + (float(_m.group(3)) if _m.group(3) else 0.0)
        ratio = real_in / paper_in
        return {"mm_per_pt": ratio * MM_PER_POINT,
                "scale_label": f"{scale_str} (1:{int(round(ratio))})", "source": "imperial"}
    match = re.match(r"^\s*1?\s*[:/]?\s*(\d+(?:\.\d+)?)\s*$", scale_str)
    if not match:
        raise ValueError(f"Could not parse scale {scale_str!r}. Use '1:100' or '--mm-per-pt'.")
    denominator = float(match.group(1))
    return {
        "mm_per_pt": denominator * MM_PER_POINT,
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
    get_drawings() actually return. page.rect is the rotated/display rect, so on
    a rotated sheet (very common for CAD A0/A1 exports) the two differ — and
    clipping text against page.rect silently drops everything past the rotated
    edge. Always clip against this instead."""
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
    """PyMuPDF stroke colour is a 0-1 RGB tuple (or None)."""
    if not c:
        return None
    try:
        return "#" + "".join(f"{int(round(v * 255)):02X}" for v in c[:3])
    except Exception:
        return None


def hex_to_rgb(h):
    """'#RRGGBB' -> (r,g,b) in 0-1, or None."""
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
    # Split on whitespace and the punctuation that typically frames a tag on a
    # drawing (commas, slashes, brackets, dashes, leader dots, apostrophes).
    # NOT a semantic pattern — just word boundaries, so "GPO,L1" and "(L1)"
    # both yield "L1".
    return [t for t in re.split(r"[\s,/()\[\]{}.']+", s) if t]


def _segment(piece, vocab_sorted):
    """Greedily split a delimiter-free text run into a sequence of known tags.

    CAD exports often jam adjacent tags into one text span with no separator —
    "F4F7", "F11F11F11F11", "F9F6F9F6". This walks the run left-to-right,
    matching the LONGEST vocabulary tag at each position (so "F11" wins over
    "F1"), and returns the list of tags if the whole run is consumed cleanly.
    Returns None if anything is left over — which is what keeps unrelated runs
    like "SL81" or "F'C" from being mistaken for tags. The vocabulary is the
    exact set of strings Claude supplied; this is not pattern inference.
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
                 (longest-match), counting every occurrence — so a standalone
                 "F6" counts once and a jammed "F4F7" counts F4 and F7. A piece
                 that doesn't fully segment into known tags counts nothing,
                 which rejects unrelated runs like "SL81".
      exact    — match only if the whole (trimmed) text object equals the tag.
      contains — substring count (use sparingly; "F1" hides inside "F11").
    """
    out = {
        "pdf": pdf_path, "mode": mode, "case_insensitive": case_insensitive,
        "bbox_pts": list(bbox) if bbox else None,
        "exclude_bbox_pts": [list(b) for b in exclude_bboxes] if exclude_bboxes else [],
        "counts": {},
    }
    targets = {t: _normalise(t, case_insensitive) for t in tags}
    # reverse map normalised -> original; vocab sorted longest-first for greedy match
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
        # get_text("words") returns native (un-rotated) coords; clip in that space.
        nb = native_bounds(page)
        clip = to_native_bbox(bbox, page) if bbox else nb
        excl = [to_native_bbox(b, page) for b in exclude_bboxes] if exclude_bboxes else []
        if exclude_bboxes_native:
            excl = excl + [tuple(b) for b in exclude_bboxes_native]

        # Use "words" extraction, not "dict" spans. On many CAD exports the span
        # tree silently drops text that lives in form XObjects, so dict-mode can
        # under-count badly; "words" returns every word with its own bbox, and
        # already separates tags that dict-mode would merge ("F2 F6" not "F2F6").
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

            # token mode (default): segment each delimiter-split piece against
            # the vocabulary, so a standalone "F6" and a jammed "F4F7" both work
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


# Distinct, print-safe fills — cycled one-per-tag so each item type reads as its
# own colour, like takeoff software. Used for the count markup spec.
MARKUP_PALETTE = [
    "#E53935", "#8E24AA", "#3949AB", "#039BE5", "#00897B", "#7CB342", "#FDD835",
    "#FB8C00", "#6D4C41", "#546E7A", "#D81B60", "#00ACC1", "#C0CA33", "#5E35B1",
    "#43A047", "#F4511E", "#1E88E5", "#8D6E63", "#EC407A", "#26A69A",
]


def build_markup_spec(count_result, page=1, opacity=0.35):
    """Turn a count result into a pdf-markup spec — one translucent box per
    COUNTED location, so the markup shows exactly what's in the QTO and nothing
    else (excluded schedule/legend definitions are already gone from the count).
    Boxes are native-coord (what pdf-markup `apply` expects); colour cycles per
    tag. Returns (spec, legend). No text stamps — they'd render rotated on
    rotated sheets; the colour↔tag↔count legend goes in the BOQ instead."""
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
# polygons — area
# ----------------------------------------------------------------------------
def _stitch_paths(page, bbox):
    """Walk get_drawings() into polylines, carrying stroke metadata.

    Returns list of dicts: points, closed, stroke_hex, width. The same raw
    material feeds both area (closed) and length (open + closed) queries.
    """
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
    # Keep only paths with a vertex inside the clip region
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
        mm = scale.get("mm_per_pt")
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
            if mm is not None:
                entry["area_m2"] = round(a * (mm ** 2) / 1_000_000.0, 3)
                entry["perimeter_m"] = round(polyline_length_pts(p["points"], True) * mm / 1000.0, 3)
            kept.append(entry)
        kept.sort(key=lambda e: -e["area_pts2"])
        out["polygons"] = kept
        out["polygon_count"] = len(kept)
        if mm is not None:
            out["total_area_m2"] = round(sum(p.get("area_m2", 0) for p in kept), 3)
    finally:
        doc.close()
    return out


# ----------------------------------------------------------------------------
# length — linear measurement
# ----------------------------------------------------------------------------
def extract_lengths(pdf_path, bbox, scale, min_len_pts=5.0):
    """Return polylines (open and closed) in a region with length + stroke.

    Claude isolates the item being measured by stroke colour/width (read off
    the line-type legend) and by region, then sums the matching polylines.
    Annotated length labels (via `dimensions`) are preferred when present.
    """
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "scale": scale, "polylines": []}
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        mm = scale.get("mm_per_pt")
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
            if mm is not None:
                entry["length_m"] = round(L * mm / 1000.0, 3)
            kept.append(entry)
        kept.sort(key=lambda e: -e["length_pts"])
        out["polylines"] = kept
        out["polyline_count"] = len(kept)
        if mm is not None:
            out["total_length_m"] = round(sum(p.get("length_m", 0) for p in kept), 3)
        # Group totals by stroke so Claude can read off "all red lines = X m"
        by_stroke = {}
        for p in kept:
            key = f"{p['stroke_hex']}|{p['width']}"
            g = by_stroke.setdefault(key, {"stroke_hex": p["stroke_hex"], "width": p["width"], "count": 0, "length_pts": 0.0})
            g["count"] += 1
            g["length_pts"] += p["length_pts"]
        if mm is not None:
            for g in by_stroke.values():
                g["length_m"] = round(g["length_pts"] * mm / 1000.0, 3)
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
        # "words" extraction (not dict spans) — see note in count_tags: dict mode
        # can silently miss XObject text on CAD exports.
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


DIMENSION_REGEX = re.compile(r"^\s*(?P<value>\d{1,7}(?:[.,]\d+)?)\s*(?P<unit>mm|m|cm|ft|in|\"|'|)\s*$", re.IGNORECASE)


def extract_dimensions(pdf_path, bbox):
    """Find dimension-shaped text (a number, optional unit). Heuristic on
    SHAPE only, not on meaning — Claude reads what each dimension refers to
    from its position and verifies against the visual."""
    td = extract_text_in_region(pdf_path, bbox)
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "dimensions": []}
    for tb in td.get("text_blocks", []):
        m = DIMENSION_REGEX.match(tb["text"].replace(" ", ""))
        if not m:
            continue
        try:
            value = float(m.group("value").replace(",", "."))
        except ValueError:
            continue
        out["dimensions"].append({"raw_text": tb["text"], "value": value, "unit": (m.group("unit") or "").lower() or None, "bbox": tb["bbox"]})
    out["count"] = len(out["dimensions"])
    return out


def extract_tables(pdf_path, bbox):
    out = {"pdf": pdf_path, "bbox_pts": list(bbox) if bbox else None, "tables": []}
    if not HAVE_PDFPLUMBER:
        out["error"] = "pdfplumber not installed (pip install pdfplumber --break-system-packages)"
        return out
    # NOTE: don't rely on table auto-detection to LOCATE a schedule on a busy
    # drawing — pdfplumber latches onto the sheet's gridlines and returns a
    # page-spanning "table". Crop to the schedule region (pass --bbox) to read
    # its rows reliably; separate QTO instances from definitions with an
    # exclude-bbox + the vision check, not by trusting a detected table bbox.
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
# render + markup — self-contained (no external markup skill needed)
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
    """Rasterise a page (or a display-space region) to PNG. Region/grid are in
    the rotated/display coordinate system — i.e. what you see — so coordinates
    read off the render feed straight back into --bbox/--exclude-bbox."""
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
    """Apply a markup spec (the kind `count --markup-out` writes, plus line /
    polyline / cloud outlines for areas and lengths) to a PDF, writing a new
    file. Annotation coords are native — the same space count/polygons/length
    emit — so on a rotated sheet the marks render in the right place. `box`
    honours `opacity` for the translucent takeoff-software look."""
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
        out["width_mm"] = round(page.rect.width * MM_PER_POINT, 1); out["height_mm"] = round(page.rect.height * MM_PER_POINT, 1)
        cands = []
        # Match BOTH metric ratios (1:100, 1/100) AND imperial architectural
        # notation (1/8"=1'-0", 1/4" = 1'0", 1"=20'). The old version only
        # caught 1:N and silently missed imperial sets — a real miss on US/MEP
        # drawings whose title block reads "As indicated". Also surface NTS /
        # SCALE / AS INDICATED text so Claude knows to read the plan's own note.
        scale_re = re.compile(
            r"(\b1\s*[:/]\s*\d+\b)"                           # 1:100 / 1/100
            r"|(\d+(?:/\d+)?\s*\"?\s*=\s*\d+'\s*-?\s*\d*\s*\"?)"  # 1/8"=1'-0"
            r"|(\bN\.?T\.?S\.?\b|AS\s+INDICATED|\bSCALE\b)",  # NTS / scale notes
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
    p.add_argument("--scale", default=None, help="Drawing scale, e.g. '1:100'. Required for real-world units.")
    p.add_argument("--mm-per-pt", type=float, default=None, help="Override scale with explicit mm-per-point factor.")


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
                    help="Region to exclude in NATIVE coords (the same space count REPORTS hit x/y). "
                         "Use this when building an exclude box from the locations count just printed. Repeatable.")
    pc.add_argument("--mode", choices=["token", "exact", "contains"], default="token")
    pc.add_argument("--case-insensitive", action="store_true")
    pc.add_argument("--markup-out", default=None,
                    help="Write a pdf-markup spec (translucent boxes for the COUNTED hits only) to this path.")
    pc.add_argument("--markup-page", type=int, default=1,
                    help="Page number to stamp on the markup ops (the sheet's index in the merged PDF). Default 1.")

    pp = sub.add_parser("polygons", help="Closed polygons + area")
    pp.add_argument("pdf_path"); add_bbox(pp); add_scale(pp)
    pp.add_argument("--min-area-pts2", type=float, default=100.0)

    pl = sub.add_parser("length", help="Open + closed polylines + length, with stroke")
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

    pm = sub.add_parser("markup", help="Apply a markup spec (boxes/lines/outlines) to a PDF -> new PDF")
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
        scale = parse_scale(args.scale, args.mm_per_pt)
        result = extract_polygons(args.pdf_path, tuple(args.bbox) if args.bbox else None,
                                  scale, args.min_area_pts2)
        print(json.dumps(result, indent=2))

    elif args.cmd == "length":
        scale = parse_scale(args.scale, args.mm_per_pt)
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
