#!/usr/bin/env python3
"""
preprocess_plans.py — Turn a land-development plan set (PDF) into cheap,
queryable per-sheet inputs: split single-sheet PDFs, extracted text layer,
rasterized page image, and a manifest.json.

This is the DETERMINISTIC prep step. It does NOT summarize. The agent reads
the outputs (text + image) and writes the per-sheet .md summaries.

Usage:
    python preprocess_plans.py INPUT [--out DIR] [--long-edge PX] [--split-pdf]

    INPUT        A merged plan-set PDF, or a directory of PDFs.
    --out DIR    Output directory (default: <input_stem>_sheets next to input).
    --long-edge  Target long-edge pixels for the raster (default 2200).
                 Large-format civil sheets (24x36) need this to keep title-block
                 and dimension text legible. Raise to ~2800 for dense sheets,
                 lower to ~1600 to save tokens on simple sheets.
    --split-pdf  Also write a single-page PDF per sheet (useful for re-querying
                 the original vector when a .md summary is insufficient).
    --check-only Run the preflight report (vector vs scanned) and stop. No output
                 files written. Use this first to confirm the set is CAD vector.
    --sqlite     Also write the manifest into a local SQLite db (plans.db) in the
                 output dir. Optional; the .md index is enough for a single set.
                 The db earns its place for cross-project queries.

Dependency: PyMuPDF (fitz).  pip install --break-system-packages pymupdf
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: pip install --break-system-packages pymupdf")

# A page with fewer than this many extracted characters is treated as
# scanned/raster-only (no useful text layer) -> vision pass is required.
TEXT_LAYER_MIN_CHARS = 40


def titleblock_hint(page):
    """Grab text from the bottom-right region where civil title blocks live.
    Helps guess sheet number + title without reading the whole sheet."""
    r = page.rect
    clip = fitz.Rect(r.x0 + r.width * 0.68, r.y0 + r.height * 0.80, r.x1, r.y1)
    txt = page.get_text("text", clip=clip).strip()
    # collapse whitespace, keep it short
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    return " | ".join(lines[:12])


def preflight(pdfs):
    """Classify the set before heavy work: how many sheets carry a usable text
    layer (CAD vector) vs none (scanned/raster). Returns (total, vector, scanned)."""
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
        print("  Scanned (image pass required): " + ", ".join(scanned_pages))
    if pct == 100:
        print("  All vector. Text path is primary; image pass is the exception.")
    elif pct == 0:
        print("  No text layer anywhere. This set is scanned; rely on images/OCR.")
    else:
        print("  Mixed set. Vector sheets use text; flagged sheets need images.")
    return total, vector, scanned_pages


def write_sqlite(out_dir: Path, records):
    """Optional local store for cross-project SQL queries. One row per sheet."""
    import sqlite3
    db = out_dir / "plans.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE IF NOT EXISTS sheets(
        source_pdf TEXT, sheet INT, source_page INT, png TEXT, txt TEXT,
        sheet_pdf TEXT, has_text_layer INT, text_chars INT,
        titleblock_hint TEXT, summary_md TEXT,
        PRIMARY KEY(source_pdf, sheet))""")
    con.executemany(
        """INSERT OR REPLACE INTO sheets VALUES
           (:source_pdf,:sheet,:source_page,:png,:txt,:sheet_pdf,
            :has_text_layer,:text_chars,:titleblock_hint,:summary_md)""",
        [{**r, "has_text_layer": int(r["has_text_layer"])} for r in records])
    con.commit(); con.close()
    print(f"SQLite: {db}")


def process_pdf(pdf_path: Path, out_dir: Path, long_edge: int, split_pdf: bool,
                sheet_offset: int, source_label: str):
    doc = fitz.open(pdf_path)
    records = []
    for i, page in enumerate(doc):
        n = sheet_offset + i + 1
        stem = f"sheet_{n:03d}"

        # --- text layer ---
        text = page.get_text("text")
        char_count = len(text.strip())
        has_text_layer = char_count >= TEXT_LAYER_MIN_CHARS
        (out_dir / f"{stem}.txt").write_text(text, encoding="utf-8")

        # --- raster (scale so the long edge hits target px) ---
        r = page.rect
        page_long = max(r.width, r.height) or 1
        zoom = long_edge / page_long
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_path = out_dir / f"{stem}.png"
        pix.save(img_path)

        # --- optional single-sheet PDF ---
        sheet_pdf_rel = None
        if split_pdf:
            one = fitz.open()
            one.insert_pdf(doc, from_page=i, to_page=i)
            sheet_pdf_path = out_dir / f"{stem}.pdf"
            one.save(sheet_pdf_path)
            one.close()
            sheet_pdf_rel = sheet_pdf_path.name

        records.append({
            "sheet": n,
            "source_pdf": source_label,
            "source_page": i + 1,
            "png": img_path.name,
            "txt": (out_dir / f"{stem}.txt").name,
            "sheet_pdf": sheet_pdf_rel,
            "has_text_layer": has_text_layer,
            "text_chars": char_count,
            "page_size_pt": [round(r.width, 1), round(r.height, 1)],
            "raster_px": [pix.width, pix.height],
            "titleblock_hint": titleblock_hint(page),
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

    # Preflight gate: classify the set before any heavy work.
    preflight(pdfs)
    if args.check_only:
        return

    out_dir = Path(args.out).expanduser().resolve() if args.out else default_out
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records = []
    offset = 0
    for pdf in pdfs:
        recs = process_pdf(pdf, out_dir, args.long_edge, args.split_pdf,
                           offset, pdf.name)
        all_records.extend(recs)
        offset += len(recs)
        print(f"  {pdf.name}: {len(recs)} sheet(s)")

    scanned = [r["sheet"] for r in all_records if not r["has_text_layer"]]
    manifest = {
        "source": str(in_path),
        "sheet_count": len(all_records),
        "long_edge_px": args.long_edge,
        "scanned_sheets_no_text_layer": scanned,
        "sheets": all_records,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                           encoding="utf-8")

    print(f"\nDone. {len(all_records)} sheet(s) -> {out_dir}")
    if scanned:
        print(f"Note: {len(scanned)} sheet(s) have no text layer (scanned/raster): "
              f"{scanned}. These need the image (vision) pass; text extraction is empty.")
    print(f"Manifest: {out_dir / 'manifest.json'}")
    if args.sqlite:
        write_sqlite(out_dir, all_records)


if __name__ == "__main__":
    main()
