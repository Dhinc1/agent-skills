#!/usr/bin/env python3
"""
Split a multi-page drawing PDF into single-sheet PDFs and pull the raw vector
text layer for each, with coordinates. Optionally render a PNG per sheet for
the vision passes.

This is pure plumbing. Unlike the old version of this skill, it does NOT try
to classify tags, dimensions, or disciplines with regex — that judgement
belongs to Claude, who reads the legend and schedules to learn what this
particular set's tokens mean. The script's only job is to make the text and
geometry cheaply available with exact coordinates so the measurement engine
(measure.py) and Claude can work on one sheet at a time.

Why split first: analysing one sheet at a time is dramatically more reliable
than reasoning over a merged 20-page bundle, and the single-sheet PDFs become
durable artefacts the measurement engine reads directly.

Why text-first: PyMuPDF reads every selectable character with exact
coordinates at 100% accuracy. Vision then only does what vision is good at —
interpreting geometry and symbols. If a sheet has little or no selectable text
it is almost certainly a raster scan; the per-sheet JSON flags that so the
workflow knows to lean on the PNG and on schedules instead.

Usage:
    python split_extract.py drawings.pdf -o out_dir              # text only
    python split_extract.py drawings.pdf -o out_dir --render     # + PNGs
    python split_extract.py drawings.pdf -o out_dir --pages 1,3,5
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

MM_PER_POINT = 25.4 / 72.0


def extract_text_objects(page):
    # "words" extraction, not "dict" spans: on CAD exports the span tree can
    # silently drop text that lives in form XObjects, under-reporting the sheet.
    # words returns every word with its own bbox.
    objs = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4].strip()
        if not text:
            continue
        objs.append({
            "text": text,
            "bbox": [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)],
            "cx": round((x0 + x1) / 2, 1),
            "cy": round((y0 + y1) / 2, 1),
        })
    return objs


def scale_candidates(text_objects, page_w, page_h):
    """Surface every 1:N string with a flag for whether it sits in the
    bottom-right title-block zone. The workflow picks the right one — the
    script does not decide."""
    cands = []
    for o in text_objects:
        if re.search(r"\b1\s*[:/]\s*\d+\b", o["text"]):
            cands.append({
                "text": o["text"],
                "cx": o["cx"], "cy": o["cy"],
                "in_title_zone": o["cy"] > page_h * 0.7 and o["cx"] > page_w * 0.5,
            })
    return cands


def title_block_zone(text_objects, page_w, page_h):
    """Raw text from the bottom-right zone — likely drawing number, title,
    revision, scale. Returned verbatim for Claude to interpret."""
    tb = [o for o in text_objects if o["cy"] > page_h * 0.72 and o["cx"] > page_w * 0.55]
    tb.sort(key=lambda o: (o["cy"], o["cx"]))
    return [o["text"] for o in tb[:40]]


def classify_source(text_objects, page):
    """vector / raster heuristic. Selectable text + vector geometry => vector.
    No text and no geometry => raster (a scan); query mode will be useless and
    the PNG is the source of truth."""
    drawings = page.get_drawings()
    has_text = len(text_objects) >= 5
    has_geom = len(drawings) >= 20
    if has_text and has_geom:
        st = "vector"
    elif not has_text and not has_geom:
        st = "raster"
    else:
        st = "mixed"
    return {"source_type": st, "text_objects": len(text_objects), "vector_paths": len(drawings)}


def process_page(page, page_num):
    rect = page.rect
    objs = extract_text_objects(page)
    src = classify_source(objs, page)
    return {
        "page_number": page_num,
        "page_size": {
            "width_pts": round(rect.width, 1), "height_pts": round(rect.height, 1),
            "width_mm": round(rect.width * MM_PER_POINT, 1), "height_mm": round(rect.height * MM_PER_POINT, 1),
        },
        "source_type": src["source_type"],
        "source_metrics": src,
        "title_block_zone_text": title_block_zone(objs, rect.width, rect.height),
        "scale_candidates": scale_candidates(objs, rect.width, rect.height),
        "text_objects": objs,
        "stats": {"text_objects": len(objs)},
    }


def main():
    ap = argparse.ArgumentParser(description="Split a drawing PDF and extract its raw vector text layer.")
    ap.add_argument("pdf_path")
    ap.add_argument("-o", "--output-dir", required=True)
    ap.add_argument("--pages", default=None, help="Comma-separated 1-based page numbers (default: all)")
    ap.add_argument("--render", action="store_true", help="Also render a PNG per sheet for vision passes")
    ap.add_argument("--dpi", type=int, default=200, help="PNG resolution when --render (default 200)")
    args = ap.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(args.pdf_path)
    total = len(doc)
    stem = Path(args.pdf_path).stem
    os.makedirs(args.output_dir, exist_ok=True)

    if args.pages:
        idxs = [p - 1 for p in (int(x) for x in args.pages.split(",")) if 0 < p <= total]
    else:
        idxs = list(range(total))

    manifest = {"source_file": Path(args.pdf_path).name, "total_pages": total, "pages_processed": len(idxs), "pages": []}

    for idx in idxs:
        n = idx + 1
        page = doc[idx]

        single_pdf = os.path.join(args.output_dir, f"{stem}_sheet{n}.pdf")
        sd = fitz.open(); sd.insert_pdf(doc, from_page=idx, to_page=idx); sd.save(single_pdf); sd.close()

        info = process_page(page, n)
        info["files"] = {"pdf": single_pdf}

        if args.render:
            png = os.path.join(args.output_dir, f"{stem}_sheet{n}.png")
            zoom = args.dpi / 72
            page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(png)
            info["files"]["png"] = png

        json_path = os.path.join(args.output_dir, f"{stem}_sheet{n}.json")
        with open(json_path, "w") as f:
            json.dump(info, f, indent=2)
        info["files"]["json"] = json_path

        manifest["pages"].append({
            "page_number": n, "source_type": info["source_type"],
            "scale_candidates": info["scale_candidates"],
            "title_block_zone_text": info["title_block_zone_text"][:12],
            "stats": info["stats"], "files": info["files"],
        })
        print(f"  sheet {n}/{total}: {info['source_type']}, {info['stats']['text_objects']} text objects", file=sys.stderr)

    doc.close()
    mpath = os.path.join(args.output_dir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nDone. {len(idxs)} sheets -> {args.output_dir}", file=sys.stderr)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
