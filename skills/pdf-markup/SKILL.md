---
name: pdf-markup
description: >-
  Render and mark up PDF documents — highlights, boxes, revision clouds,
  callouts, arrows, text stamps, and redactions — producing real, editable PDF
  annotations plus a rendered preview. Crucially, it RENDERS any page or zoomed
  region to an image first so Claude can actually SEE the drawing before
  marking it up. Use this whenever the user wants to annotate, mark up, redline,
  comment on, cloud, highlight, stamp, or redact a PDF, or asks to "mark up this
  drawing", "add a revision cloud", "redline this", "redact this", "stamp it as
  reviewed", "circle the X", "put a callout on Y", or wants to visually inspect /
  count / measure something on a PDF that has no usable text layer. Always use
  this skill for PDF annotation work rather than hand-writing PyMuPDF code. Do
  NOT use it for full quantity takeoffs (construction-takeoff) or exhaustive
  sheet-by-sheet drawing breakdowns (drawings-analyser) — this is the lightweight
  see-it-and-annotate tool.
---

# PDF Markup

Render and annotate PDFs with a single script: `scripts/pdf_markup.py`. It uses
PyMuPDF, works on any PDF on disk, needs no external app open, and produces
**real PDF annotations** (selectable and editable later in Bluebeam, Acrobat,
etc.), not flattened images.

## The core workflow — always render before you mark up

You cannot reliably place a markup on a page you haven't seen. Follow this loop:

1. **Render the page with a coordinate grid** so you can read off positions:
   `render <pdf> --page N --grid`
2. **Look at the image.** Identify what to mark and read the target coordinates
   straight off the grid (it is labelled in PDF points). Zoom into a busy area
   with `--region` at higher `--dpi` when you need detail (e.g. to count or
   measure small items).
3. **Write a JSON spec** of markup operations using those coordinates.
4. **Apply** it: `apply <pdf> --spec spec.json --out marked.pdf`
5. **Render the result** (no grid) and check the markups landed where intended.
   Fix and re-run if not. Always show the user the final rendered preview.

This render-first habit is the whole point of the skill — it is also how you
answer "how many X are on this drawing" or "what's the dimension of Y" when the
PDF's text layer is bare: render, look, count or measure from the image.

## Coordinate system

- Units are **PDF points** (72 pt = 1 inch). Get page sizes with `info`.
- Origin is **top-left**; x increases right, y increases **down**.
- The grid overlay is labelled in these same points, so a value you read off the
  grid drops straight into a spec. Heavy gridlines are every 5th step and carry
  labels; spacing auto-scales to the page (override with `--grid-step`).

## Commands

```
python scripts/pdf_markup.py info   <pdf>
python scripts/pdf_markup.py text   <pdf> [--page N] [--words]
python scripts/pdf_markup.py render <pdf> --page N [--dpi 150] [--grid]
                                    [--grid-step PT] [--region x0,y0,x1,y1] [--out f.png]
python scripts/pdf_markup.py list   <pdf> [--page N]
python scripts/pdf_markup.py apply  <pdf> --spec spec.json --out <pdf>
```

- `info` — page count and size of each page in points (and inches).
- `text` — extract the text layer; `--words` adds each word's bounding box, handy
  for finding coordinates of labels without rendering.
- `render` — page → PNG. `--grid` overlays the coordinate grid. `--region`
  crops/zooms to a rectangle (points) — use a high `--dpi` (200–300) to inspect
  dense areas. Default dpi 150.
- `list` — dump existing annotations (type, rect, subject, comment). Run before
  marking up an already-reviewed sheet so you don't duplicate.
- `apply` — apply the spec and save a new PDF. The source file is never modified.

## The markup spec

A JSON file: a default `page` plus a list of `ops`. Each op may carry its own
`page` to mark up multiple sheets in one run. Coordinates are points.

```json
{
  "page": 1,
  "ops": [
    {"type":"highlight","text":"PRELIMINARY","color":"#FF8C00","comment":"status"},
    {"type":"box","rect":[118,198,222,362],"color":"#0066FF","width":2,"fill":null},
    {"type":"circle","rect":[300,200,400,300],"color":"#E00000"},
    {"type":"cloud","rect":[538,196,642,364],"color":"#E00000","comment":"RFI-12"},
    {"type":"callout","rect":[620,90,840,150],"point":[770,200],"text":"UPS clearance?","color":"#E00000"},
    {"type":"arrow","p1":[100,100],"p2":[200,160],"color":"#E00000"},
    {"type":"line","p1":[100,100],"p2":[200,100],"color":"#000000","width":1},
    {"type":"text","point":[120,400],"text":"Note here","fontsize":12,"color":"#E00000"},
    {"type":"stamp","rect":[60,55,250,105],"text":"REVIEWED","color":"#C00000","rotate":0},
    {"type":"redact","rect":[900,720,1170,760],"text":"REDACTED","fill":"#000000"}
  ]
}
```

### Op types

| type | required | optional | notes |
|------|----------|----------|-------|
| `highlight` | `text` | `color`, `comment`, `subject` | highlights every match of the text on the page |
| `box` / `rect` | `rect` | `color`, `fill`, `width`, `opacity`, `comment` | rectangle annotation |
| `circle` | `rect` | `color`, `fill`, `width`, `comment` | ellipse inside the rect |
| `cloud` | `rect` | `color`, `width`, `comment` | revision cloud (native cloudy border, vector fallback) |
| `line` | `p1`, `p2` | `color`, `width`, `arrow` | set `arrow:true` for an arrowhead at p2 |
| `arrow` | `p1`, `p2` | `color`, `width` | line with an arrowhead at p2 |
| `text` / `note` | `point` **or** `rect`, `text` | `color`, `fill`, `fontsize` | free-floating text; give `fill` for a filled box |
| `callout` | `rect`, `point`, `text` | `color`, `fill`, `fontsize` | text box with an arrow leader to `point` |
| `stamp` | `rect`, `text` | `color`, `width`, `fontsize`, `rotate` | bold bordered text stamp |
| `redact` | `rect` | `text`, `fill` | **destructive** — see below |

- `color`/`fill` are `#RRGGBB` (or `#RGB`). `rect` is `[x0,y0,x1,y1]`; points are `[x,y]`.
- Default colours: highlight yellow-ish, most others red, stamp dark red.

## Important behaviours

- **Non-destructive by default.** `apply` writes a new file; the input is
  untouched. Annotations are real and editable downstream.
- **Redaction is destructive and permanent.** `redact` burns out the underlying
  content (text and image) under the rect when applied — it does not just cover
  it. Only use it when the user explicitly wants content removed, and confirm
  first. Everything else is reversible by the user (delete the annotation).
- **Highlight needs a text layer.** It searches extracted text; if the label is
  graphics/raster it won't be found — fall back to a `box` or `cloud` placed by
  coordinate instead.
- **Multi-page:** put a `page` on individual ops, or set the top-level `page`
  default. `list`/`text` accept `--page` or default to all pages.

## Dependencies

PyMuPDF and Pillow. If missing:
`pip install pymupdf pillow --break-system-packages`

## Tips

- To **count items** on a drawing with no text layer: render the relevant region
  at high dpi, count from the image, then (if useful) drop a numbered `box` or
  `circle` on each so the user can verify the tally.
- To **measure** off a scaled drawing: read two points off the grid, compute the
  point distance, then convert with the sheet scale (e.g. 1:50 → 1 pt ≈ 50/72
  mm at full size). State the assumption; confirm the scale with the user.
- Keep markup colours consistent with the user's convention (clouds for changes,
  a colour per discipline/status) if they have one.
