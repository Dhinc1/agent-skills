#!/usr/bin/env python3
"""
Aggregate per-sheet vector JSONs into a single bundle for AI classification.

This is pure file I/O. No judgement, no pattern matching. Walks the
drawings_split/ directory, finds every <stem>.json + <stem>.png pair, and
emits a single index that the AI classification step (run by Claude itself,
not a script) iterates over.

Why this exists as a separate step: the AI classification is the expensive
part. Having a deterministic "what sheets are there" file means we can
resume mid-run, check progress, and reason about the set as a whole before
spending tokens.

Usage:
    python build_sheet_index.py "<project>/0. AI Context/drawings_split" \\
        -o "<project>/0. AI Context/sheet_index.json"
"""

import argparse
import json
import os
import sys
from pathlib import Path


def build_index(drawings_split_root: str) -> dict:
    """Walk drawings_split/ and return a flat list of every sheet found."""
    root = Path(drawings_split_root)
    if not root.exists():
        return {"sheets": [], "error": f"not found: {drawings_split_root}"}

    sheets = []

    # Each sub-directory of drawings_split/ corresponds to a source PDF.
    for source_dir in sorted(root.iterdir()):
        if not source_dir.is_dir():
            continue
        manifest_path = source_dir / "manifest.json"
        manifest = None
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
            except Exception:
                manifest = None

        # Find every JSON that has a matching PDF (and ideally a matching PNG).
        for json_path in sorted(source_dir.glob("*.json")):
            if json_path.name == "manifest.json":
                continue
            stem = json_path.stem
            pdf_path = source_dir / f"{stem}.pdf"
            png_path = source_dir / f"{stem}.png"
            if not pdf_path.exists():
                continue

            sheets.append({
                "stem": stem,
                "source_pdf": manifest.get("source_file") if manifest else source_dir.name,
                "single_sheet_pdf": str(pdf_path),
                "image_path": str(png_path) if png_path.exists() else None,
                "extraction_path": str(json_path),
            })

    return {
        "drawings_split_root": str(root),
        "total_sheets": len(sheets),
        "sheets": sheets,
    }


def main():
    ap = argparse.ArgumentParser(
        description="Aggregate per-sheet artefacts into a single index for AI classification."
    )
    ap.add_argument("drawings_split_root", help="Path to <project>/0. AI Context/drawings_split/")
    ap.add_argument("-o", "--output", required=True, help="Where to write sheet_index.json")
    args = ap.parse_args()

    index = build_index(args.drawings_split_root)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(index, f, indent=2)

    print(f"Indexed {index['total_sheets']} sheets -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
