#!/usr/bin/env python3
"""
pdf_markup.py — render and annotate PDF documents.

The workflow this script is built for:
  1. RENDER a page (or a zoomed region) to a PNG so Claude can SEE it.
     Optionally overlay a coordinate grid labelled in PDF points, so Claude
     can read off the coordinates of anything it wants to mark up.
  2. APPLY markups (highlights, boxes, clouds, callouts, lines, stamps,
     redactions) from a JSON spec whose coordinates are in PDF points.
  3. RENDER the result again to confirm the markups landed correctly.

Coordinate system (important):
  - All coordinates are PDF *points* (72 points = 1 inch).
  - Origin is the TOP-LEFT of the page; x increases right, y increases DOWN.
  - This matches what the grid overlay shows, so a point you read off the
    grid can be dropped straight into a markup op.

Subcommands:
  info    <pdf>                         page count + per-page size (points)
  text    <pdf> [--page N] [--words]    extract text (optionally word boxes)
  render  <pdf> --page N [...]          render page/region to PNG
  list    <pdf> [--page N]              list existing annotations
  apply   <pdf> --spec S --out O        apply markups from a JSON spec

Run `python pdf_markup.py <subcommand> -h` for per-command options.
"""
import argparse, json, sys, os
import fitz  # PyMuPDF


# ---------- helpers ----------

def hex_to_rgb(h):
    """'#RRGGBB' or '#RGB' -> (r,g,b) floats in 0..1. None passes through."""
    if h is None:
        return None
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"bad colour {h!r}; want #RRGGBB")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def open_doc(path):
    if not os.path.exists(path):
        sys.exit(f"error: file not found: {path}")
    return fitz.open(path)


def page_or_die(doc, n):
    """n is 1-based for the user; convert to 0-based and bounds-check."""
    if n < 1 or n > doc.page_count:
        sys.exit(f"error: page {n} out of range (1..{doc.page_count})")
    return doc[n - 1]


# ---------- info ----------

def cmd_info(a):
    doc = open_doc(a.pdf)
    print(f"file: {a.pdf}")
    print(f"pages: {doc.page_count}")
    for i in range(doc.page_count):
        p = doc[i]
        r = p.rect
        rot = p.rotation
        print(f"  page {i+1}: {r.width:.0f} x {r.height:.0f} pt "
              f"({r.width/72:.1f} x {r.height/72:.1f} in)  rotation={rot}")


# ---------- text ----------

def cmd_text(a):
    doc = open_doc(a.pdf)
    pages = [a.page] if a.page else range(1, doc.page_count + 1)
    for n in pages:
        p = page_or_die(doc, n)
        if a.words:
            words = p.get_text("words")  # x0,y0,x1,y1,word,block,line,word_no
            print(f"--- page {n}: {len(words)} words ---")
            for w in words:
                x0, y0, x1, y1, word = w[0], w[1], w[2], w[3], w[4]
                print(f"  [{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}] {word}")
        else:
            print(f"--- page {n} ---")
            print(p.get_text() or "(no extractable text)")


# ---------- render ----------

def _draw_grid(pil_img, region, scale, step):
    """Overlay a point-labelled grid on a PIL image.
    region = (x0,y0,x1,y1) in points (the area that was rendered).
    scale  = pixels per point. step = grid spacing in points."""
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(pil_img, "RGBA")
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(10, int(8 * scale)))
    except Exception:
        font = ImageFont.load_default()
    x0, y0, x1, y1 = region
    minor = (160, 160, 160, 90)
    major = (90, 90, 220, 150)
    # vertical lines
    start = int(x0 // step) * step
    xx = start
    while xx <= x1:
        if xx >= x0:
            px = (xx - x0) * scale
            is_major = (xx % (step * 5) == 0)
            draw.line([(px, 0), (px, pil_img.height)],
                      fill=major if is_major else minor, width=1)
            if is_major:
                draw.text((px + 2, 2), str(int(xx)), fill=(20, 20, 160, 255), font=font)
        xx += step
    # horizontal lines
    start = int(y0 // step) * step
    yy = start
    while yy <= y1:
        if yy >= y0:
            py = (yy - y0) * scale
            is_major = (yy % (step * 5) == 0)
            draw.line([(0, py), (pil_img.width, py)],
                      fill=major if is_major else minor, width=1)
            if is_major:
                draw.text((2, py + 2), str(int(yy)), fill=(20, 20, 160, 255), font=font)
        yy += step
    return pil_img


def cmd_render(a):
    doc = open_doc(a.pdf)
    p = page_or_die(doc, a.page)
    clip = None
    region = (0, 0, p.rect.width, p.rect.height)
    if a.region:
        try:
            x0, y0, x1, y1 = [float(v) for v in a.region.split(",")]
        except Exception:
            sys.exit("error: --region wants 'x0,y0,x1,y1' in points")
        clip = fitz.Rect(x0, y0, x1, y1)
        region = (x0, y0, x1, y1)
    scale = a.dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    pix = p.get_pixmap(matrix=mat, clip=clip, alpha=False)
    out = a.out or f"page{a.page}.png"
    if a.grid:
        from PIL import Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        step = a.grid_step or _auto_step(region)
        _draw_grid(img, region, scale, step)
        img.save(out)
        print(f"wrote {out}  ({pix.width}x{pix.height}px, {a.dpi} dpi, "
              f"grid step {step}pt)")
    else:
        pix.save(out)
        print(f"wrote {out}  ({pix.width}x{pix.height}px, {a.dpi} dpi)")
    print(f"rendered region (points): {region}")


def _auto_step(region):
    """Pick a sensible grid spacing so ~15-25 lines span the rendered width."""
    w = region[2] - region[0]
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if w / step <= 25:
            return step
    return 1000


# ---------- list existing annotations ----------

def cmd_list(a):
    doc = open_doc(a.pdf)
    pages = [a.page] if a.page else range(1, doc.page_count + 1)
    total = 0
    for n in pages:
        p = page_or_die(doc, n)
        annots = list(p.annots() or [])
        if annots:
            print(f"--- page {n}: {len(annots)} annotation(s) ---")
        for an in annots:
            total += 1
            r = an.rect
            info = an.info
            print(f"  {an.type[1]:<10} rect=[{r.x0:.0f},{r.y0:.0f},"
                  f"{r.x1:.0f},{r.y1:.0f}] "
                  f"subject={info.get('subject','')!r} "
                  f"content={info.get('content','')!r}")
    print(f"total annotations: {total}")


# ---------- apply markups ----------

def _rect(v):
    return fitz.Rect(*v)


def _op_highlight(page, op):
    text = op["text"]
    color = hex_to_rgb(op.get("color", "#FFEB00"))
    hits = page.search_for(text)
    if not hits:
        return f"highlight: '{text}' not found"
    for q in hits:
        an = page.add_highlight_annot(q)
        an.set_colors(stroke=color)
        if op.get("comment"):
            an.set_info(content=op["comment"])
        an.set_info(subject=op.get("subject", "Highlight"))
        an.update()
    return f"highlight: '{text}' x{len(hits)}"


def _op_rect(page, op):
    color = hex_to_rgb(op.get("color", "#FF0000"))
    fill = hex_to_rgb(op.get("fill"))
    an = page.add_rect_annot(_rect(op["rect"]))
    an.set_colors(stroke=color, fill=fill)
    an.set_border(width=op.get("width", 2))
    if op.get("opacity") is not None:
        an.set_opacity(op["opacity"])
    if op.get("comment"):
        an.set_info(content=op["comment"])
    an.set_info(subject=op.get("subject", "Box"))
    an.update()
    return f"rect: {op['rect']}"


def _op_circle(page, op):
    color = hex_to_rgb(op.get("color", "#FF0000"))
    fill = hex_to_rgb(op.get("fill"))
    an = page.add_circle_annot(_rect(op["rect"]))
    an.set_colors(stroke=color, fill=fill)
    an.set_border(width=op.get("width", 2))
    if op.get("comment"):
        an.set_info(content=op["comment"])
    an.update()
    return f"circle: {op['rect']}"


def _op_cloud(page, op):
    """Revision cloud. Try a native cloudy polygon border; fall back to a
    scalloped vector outline that looks like a cloud on any viewer."""
    color = hex_to_rgb(op.get("color", "#FF0000"))
    x0, y0, x1, y1 = op["rect"]
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    try:
        an = page.add_polygon_annot([fitz.Point(*p) for p in pts])
        an.set_colors(stroke=color)
        an.set_border(width=op.get("width", 2), clouds=1)  # PyMuPDF >=1.22
        if op.get("comment"):
            an.set_info(content=op["comment"])
        an.set_info(subject=op.get("subject", "Cloud"))
        an.update()
        return f"cloud(native): {op['rect']}"
    except Exception:
        # fallback: draw scallops as vector graphics
        shape = page.new_shape()
        radius = op.get("scallop", 8)
        def scallop_edge(ax, ay, bx, by):
            import math
            dx, dy = bx - ax, by - ay
            length = max(1e-6, math.hypot(dx, dy))
            n = max(1, int(length / (radius * 2)))
            ux, uy = dx / length, dy / length
            for i in range(n):
                cx = ax + ux * (i + 0.5) * (length / n)
                cy = ay + uy * (i + 0.5) * (length / n)
                shape.draw_circle(fitz.Point(cx, cy), radius)
        scallop_edge(*pts[0], *pts[1])
        scallop_edge(*pts[1], *pts[2])
        scallop_edge(*pts[2], *pts[3])
        scallop_edge(*pts[3], *pts[0])
        shape.finish(color=color, width=op.get("width", 2), closePath=False)
        shape.commit()
        return f"cloud(vector): {op['rect']}"


def _op_line(page, op):
    color = hex_to_rgb(op.get("color", "#FF0000"))
    p1 = fitz.Point(*op["p1"])
    p2 = fitz.Point(*op["p2"])
    an = page.add_line_annot(p1, p2)
    an.set_colors(stroke=color)
    an.set_border(width=op.get("width", 2))
    if op.get("arrow"):
        an.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
    if op.get("comment"):
        an.set_info(content=op["comment"])
    an.update()
    return f"line: {op['p1']}->{op['p2']}"


def _op_text(page, op):
    """Free-floating text note (FreeText annot)."""
    color = hex_to_rgb(op.get("color", "#FF0000"))
    fill = hex_to_rgb(op.get("fill"))
    fs = op.get("fontsize", 12)
    # build a box around the point if only a point is given
    if "rect" in op:
        rect = _rect(op["rect"])
    else:
        px, py = op["point"]
        w = op.get("width_pt", max(80, len(op["text"]) * fs * 0.6))
        h = op.get("height_pt", fs * 1.6)
        rect = fitz.Rect(px, py, px + w, py + h)
    an = page.add_freetext_annot(rect, op["text"], fontsize=fs,
                                 text_color=color, fill_color=fill)
    if fill:
        an.set_border(width=op.get("width", 1))
        try:
            an.set_colors(stroke=color)
        except Exception:
            pass
    an.update()
    return f"text: {op['text']!r}"


def _op_callout(page, op):
    """Text box plus an arrow leader pointing at a target point."""
    color = hex_to_rgb(op.get("color", "#FF0000"))
    fill = hex_to_rgb(op.get("fill", "#FFFFFF"))
    fs = op.get("fontsize", 12)
    rect = _rect(op["rect"])
    an = page.add_freetext_annot(rect, op["text"], fontsize=fs,
                                 text_color=color, fill_color=fill)
    an.set_border(width=op.get("box_width", 1))
    try:
        an.set_colors(stroke=color)
    except Exception:
        pass
    an.update()
    # leader line from nearest box corner to the target point, with arrow
    tx, ty = op["point"]
    # anchor on the box edge closest to target
    ax = min(max(tx, rect.x0), rect.x1)
    ay = min(max(ty, rect.y0), rect.y1)
    ln = page.add_line_annot(fitz.Point(ax, ay), fitz.Point(tx, ty))
    ln.set_colors(stroke=color)
    ln.set_border(width=op.get("width", 1.5))
    ln.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
    ln.update()
    return f"callout: {op['text']!r} -> {op['point']}"


def _op_stamp(page, op):
    """Custom text stamp: a bold bordered box. Optional rotation."""
    color = hex_to_rgb(op.get("color", "#D00000"))
    rect = _rect(op["rect"])
    fs = op.get("fontsize", max(14, int((rect.y1 - rect.y0) * 0.5)))
    an = page.add_freetext_annot(rect, op["text"], fontsize=fs,
                                 text_color=color,
                                 align=fitz.TEXT_ALIGN_CENTER,
                                 rotate=op.get("rotate", 0))
    an.set_border(width=op.get("width", 2))
    try:
        an.set_colors(stroke=color)
    except Exception:
        pass
    an.update()
    return f"stamp: {op['text']!r}"


def _op_redact(page, op):
    fill = hex_to_rgb(op.get("fill", "#000000"))
    page.add_redact_annot(_rect(op["rect"]),
                          text=op.get("text"),
                          fill=fill)
    return f"redact(pending): {op['rect']}"


OPS = {
    "highlight": _op_highlight,
    "rect": _op_rect,
    "box": _op_rect,
    "circle": _op_circle,
    "cloud": _op_cloud,
    "line": _op_line,
    "arrow": lambda pg, op: _op_line(pg, {**op, "arrow": True}),
    "text": _op_text,
    "note": _op_text,
    "callout": _op_callout,
    "stamp": _op_stamp,
    "redact": _op_redact,
}


def cmd_apply(a):
    with open(a.spec) as f:
        spec = json.load(f)
    doc = open_doc(a.pdf)
    default_page = spec.get("page", 1)
    log = []
    redact_pages = set()
    for op in spec["ops"]:
        n = op.get("page", default_page)
        page = page_or_die(doc, n)
        kind = op["type"]
        if kind not in OPS:
            sys.exit(f"error: unknown op type {kind!r}. "
                     f"valid: {', '.join(sorted(OPS))}")
        log.append(f"p{n}: " + OPS[kind](page, op))
        if kind == "redact":
            redact_pages.add(n)
    # apply any pending redactions per page (this burns them in)
    for n in redact_pages:
        page_or_die(doc, n).apply_redactions()
    doc.save(a.out, garbage=3, deflate=True)
    print(f"applied {len(spec['ops'])} op(s):")
    for line in log:
        print("  " + line)
    print(f"saved -> {a.out}")


# ---------- argparse ----------

def main():
    ap = argparse.ArgumentParser(description="Render and annotate PDFs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="page count + sizes")
    s.add_argument("pdf")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("text", help="extract text")
    s.add_argument("pdf")
    s.add_argument("--page", type=int, help="1-based page; default all")
    s.add_argument("--words", action="store_true",
                   help="list word boxes with coordinates")
    s.set_defaults(func=cmd_text)

    s = sub.add_parser("render", help="render page/region to PNG")
    s.add_argument("pdf")
    s.add_argument("--page", type=int, required=True)
    s.add_argument("--dpi", type=int, default=150)
    s.add_argument("--region", help="x0,y0,x1,y1 in points (zoom/crop)")
    s.add_argument("--grid", action="store_true",
                   help="overlay a point-labelled coordinate grid")
    s.add_argument("--grid-step", type=float, dest="grid_step",
                   help="grid spacing in points (default: auto)")
    s.add_argument("--out", help="output PNG path")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("list", help="list existing annotations")
    s.add_argument("pdf")
    s.add_argument("--page", type=int)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("apply", help="apply markups from a JSON spec")
    s.add_argument("pdf")
    s.add_argument("--spec", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_apply)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
