#!/usr/bin/env python3
"""
Crop a region from a sheet PDF for the symbol library.

Pure geometry — given a PDF and a bounding box in PDF points (the same
coordinate system as pdfplumber/PyMuPDF), produces a PNG crop. The decision
about WHERE to crop is made by Claude (based on legend extraction); this
script just executes the cut.

Usage:
    python crop_region.py sheet.pdf --bbox 100 200 400 350 -o symbol_crops/E-GPO-D.png

Bounding box is x0 y0 x1 y1 in PDF points (origin = top-left for most CAD
exports; pdfplumber uses top-left origin, PyMuPDF accepts both).
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF required. Install with: pip install pymupdf --break-system-packages", file=sys.stderr)
    sys.exit(1)


def crop(pdf_path: str, bbox: tuple, output_path: str, long_edge_px: int = 512) -> dict:
    """Crop the given bbox out of page 1 of pdf_path and save as PNG."""
    doc = fitz.open(pdf_path)
    try:
        if len(doc) == 0:
            raise ValueError("PDF has no pages")
        page = doc[0]
        x0, y0, x1, y1 = bbox
        # Clamp to page bounds
        page_w = page.rect.width
        page_h = page.rect.height
        x0 = max(0.0, min(x0, page_w))
        x1 = max(0.0, min(x1, page_w))
        y0 = max(0.0, min(y0, page_h))
        y1 = max(0.0, min(y1, page_h))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"Invalid bbox after clamping: {(x0, y0, x1, y1)}")

        clip = fitz.Rect(x0, y0, x1, y1)
        # Size the output so the long edge equals long_edge_px.
        clip_long = max(clip.width, clip.height)
        zoom = (long_edge_px / clip_long) if clip_long > 0 else 1.0
        mat = fitz.Matrix(zoom, zoom)

        pix = page.get_pixmap(matrix=mat, clip=clip)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        pix.save(output_path)
        return {
            "output_path": output_path,
            "width": pix.width,
            "height": pix.height,
            "bbox_used": [x0, y0, x1, y1],
        }
    finally:
        doc.close()


def main():
    ap = argparse.ArgumentParser(description="Crop a bounding box from a sheet PDF to a PNG.")
    ap.add_argument("pdf_path")
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("X0", "Y0", "X1", "Y1"),
                    help="Bounding box in PDF points")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--long-edge-px", type=int, default=512,
                    help="Long edge of output PNG in pixels (default 512)")
    args = ap.parse_args()

    if not Path(args.pdf_path).exists():
        print(f"ERROR: File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    info = crop(args.pdf_path, tuple(args.bbox), args.output, args.long_edge_px)
    print(f"Cropped {args.pdf_path} -> {info['output_path']} ({info['width']}x{info['height']})",
          file=sys.stderr)


if __name__ == "__main__":
    main()
