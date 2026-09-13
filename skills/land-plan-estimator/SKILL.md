---
name: land-plan-reader
description: >-
  Read, index, and answer questions about land-development / civil site plan
  sets delivered as PDFs (subdivision layouts, grading & drainage, utility
  plans, road plan-and-profile, erosion control, WWTP/well siting, construction
  details, boundary/survey). Use this ANY time the user uploads or points to a
  plan set, drawing set, "the civils", a sheet index, or a large multi-sheet PDF
  and wants to query it, summarize sheets, pull quantities (lot counts,
  disturbed acreage, cut/fill, pipe sizes, setbacks), prepare an estimate, or
  find which sheet a given detail lives on. Trigger even if the user just says
  "read these plans" or "what does sheet C-3 say" — do NOT try to stuff the raw
  PDF into context, use this preprocessing-and-index workflow instead.
---

# Land Plan Reader

## Why this exists

Civil plan sets are large-format, multi-sheet PDFs (often 15-40MB, ARCH/ANSI D
sheets). Dumping the whole set into context is slow, expensive, and inaccurate —
the more you jam in, the worse the answer. The fix is a one-time preprocessing
step that turns each sheet into cheap text: split the set, pull the embedded text
layer, rasterize each sheet, then write a compact per-sheet `.md` summary plus a
routing index. After that, answering a question means reading a small index and
one or two sheet summaries — roughly 30x less context than re-reading the PDF,
and more accurate because the model sees the one sheet that matters.

Everything is file-backed and lives next to the source PDF. No external database.

## The workflow

### 1. Preprocess

First confirm the set is CAD vector (AutoCAD/Civil3D exports carry a clean text
layer). Run the preflight, then the full pass:

```bash
pip install --break-system-packages pymupdf   # if not present
python scripts/preprocess_plans.py "PATH/TO/plans.pdf" --check-only   # vector vs scanned
python scripts/preprocess_plans.py "PATH/TO/plans.pdf" --split-pdf    # full run
```

`--check-only` reports how many sheets have a usable text layer and stops. If it
reports ~100% vector, the text path is primary and the image pass is the
exception. If sheets come back scanned (older recorded plats, as-builts), those
rely on the image. Add `--sqlite` to also write a local `plans.db` (one row per
sheet) when you want cross-project SQL later; for a single set the `.md` index is
enough.

Accepts a merged set or a directory of PDFs. Writes a `*_sheets/` folder with,
per sheet: `sheet_NNN.png` (raster), `sheet_NNN.txt` (extracted text layer),
optional `sheet_NNN.pdf` (single sheet), and a `manifest.json`.

Read `manifest.json` first. Key fields per sheet: `titleblock_hint` (bottom-right
text, usually the sheet number + title), `has_text_layer`, `text_chars`, `png`,
`txt`. If `scanned_sheets_no_text_layer` is non-empty, those sheets are raster
only — the `.txt` is empty and you must rely on the `.png` image.

Tune `--long-edge` if title-block or dimension text is unreadable in the raster:
raise to ~2800 for dense sheets, lower to ~1600 to save tokens on simple ones.

### 2. Summarize each sheet

For every sheet, read its `.txt`, and Read its `.png` (the image carries the
linework, callouts, and layout the text layer misses). Then write
`sheet_NNN.md` using the template below. Skip the image only when `.txt` is
already complete for a text-only sheet (e.g. a general-notes sheet).

Work through sheets in order. For a large set, batch it and note progress. The
goal: someone doing an estimate or a takeoff should be able to answer from the
`.md` alone and only open the image for a visual check.

### 3. Build the routing index

Write `_index.md` in the sheets folder: one line per sheet mapping sheet number →
title → discipline → what lives on it → key quantities. This is what you read
first on every future query to decide which sheet(s) to open.

### 4. Answer queries

Read `_index.md`, route to the relevant sheet(s), read those `.md` files. Open the
`.png` (or the split `.pdf`) only when the summary is insufficient or the question
is inherently visual (a grading transition, a detail geometry, a boundary bearing).
Never re-read the full merged PDF to answer a routine question.

## Estimating from a plan set

When the task is a takeoff or estimate, not just Q&A:

1. Read `references/scope_kickoff.md` and have the user fill it (or state scopes
   inline). Only estimate the divisions they include. One project may be storm +
   paving with no water/sewer; another adds both.
2. Use `references/pay_items.md` as the target list and section order. Measure
   for those items in the included divisions. Add items the plan shows that the
   catalog lacks; never silently drop scope.
3. Break out segregated scopes into their own sections: pump/lift station,
   package plant/WWTP, and each offsite roadway. Catch offsite by callout (a
   named public road, "OFFSITE", NCDOT encroachment, a station range beyond the
   boundary), not by where it sits in a sheet, and record the station limits so
   onsite and offsite never double-count.
4. Carry the same exclusions the bids use (geotech, SWPPP inspection,
   import/export, rock, permits) so an estimate lines up against a real bid.
5. **Transcribe schedule tables in full — never eyeball-summarize one.** Pipe
   schedules, structure schedules, and plant schedules (storm/sewer FROM-TO-SIZE-
   LENGTH tables, curb inlet/drop inlet/FES counts, buffer plant lists) are the
   sheet's ground truth. Pull every row into a table or a small script, sum by
   category programmatically, and only then compare to whatever number you had
   before. A schedule with 40+ rows is exactly where a visual skim mis-sizes one
   segment (15" read as 12", or the reverse) — that class of error doesn't show
   up as a wrong total, it shows up as two adjacent line items that are each
   wrong by the same amount in opposite directions. If two pipe (or structure)
   sizes in the same network look off by a matching amount, that's the signature
   — go re-pull the table.
6. **Variable-width or tapered geometry needs a station-by-station takeoff, not
   a plan-view label.** Turn lanes, roadway widenings, tapers, and anything
   else that isn't a constant cross-section over its length cannot be measured
   from a single width callout on the plan view. Pull the actual cross-section
   sheets (usually a "ROADWAY SECTIONS" series keyed by station), record the
   width at each station, and compute area with average-end-area (length ×
   average of the two end widths) per segment. Treat a uniform-width assumption
   for this kind of item as a placeholder to be replaced, not an estimate to
   defend.
7. **Before dropping new numbers into an existing budget template, audit the
   whole section you're touching — not just the rows you plan to edit.** Dump
   every row in that category (labels, quantities, formulas) and check for (a)
   another row with the same or a near-duplicate label that's already active —
   two lifts of the same intermediate-course pavement, a second "1.5" overlay"
   hiding in a different section, (b) formulas that still reference an input
   cell and fire even though the row looks like an unused template default
   (a "(6'-8' depth band)" pipe row computed as a % of road frontage, still live
   underneath a hand-entered quantity in the row next to it). These don't
   surface as errors — they quietly double a cost. Re-run this audit any time
   you add a line to a category, not just on the first pass.

### Confidence: label it, don't fake it
Two different reliability levels, and they must be marked per line:
- **High:** scope structure, labeled callouts, and quantities printed on the
  sheet or in a schedule (pipe schedule, structure table, seeding acreage).
- **Low, human-verify:** geometric takeoff measured off linework (pipe LF,
  pavement SY, curb LF) on a rasterized sheet. Flag these `verify`; do not
  present a measured quantity as if it were a plan-stated one.

A **formula proxy inside the budget template is not a High-confidence
number**, even though it looks precise. `curb LF = 2 × road centerline` is a
convenience default — it systematically misses cul-de-sac bulb curb and
intersection curb returns, which is real length. Treat any such formula-driven
quantity as `verify`: prefer a plan-stated or client-confirmed total when one
exists, and say plainly when a number is a formula proxy standing in for a
real measurement, not just when it's a raw eyeball takeoff.

Anchor unit prices to the catalog's real bid numbers, but keep measured
quantities separate from stated ones in the output so the human checks the
right rows. State which rate source you actually used — the template's own
column defaults, or a verified bid-rate database — rather than letting the
distinction go unstated; if you don't know which it is, say so and ask before
presenting a cost as sourced.

Use this exact structure so summaries are scannable and machine-routable. Omit
fields that genuinely don't apply; never invent values — if something isn't legible,
write `unclear` and note that the image should be checked.

```markdown
# Sheet {number} — {title}

- **Discipline:** {cover | survey/existing | site/lotting | grading & drainage |
  utilities (water/sewer) | storm/BMP | erosion control (E&SC) | road plan-profile |
  details | landscape | other}
- **Scale / datum:** {e.g. 1"=50', NAD83 NC State Plane, NAVD88; or "unclear"}
- **Sheet no. in title block:** {C-3.0, etc.}

## What's on this sheet
{2-4 sentences, plain language: what a reviewer would find here.}

## Key data
- {lot count / lot range / typical lot dims — for lotting sheets}
- {disturbed area, total site area — acres}
- {cut / fill volumes — CY, if shown}
- {pipe/utility sizes & materials: water main, sewer, storm; WWTP or well specs}
- {road: name, ROW width, pavement section, station range}
- {setbacks / buffers / easements}
- {BMP type & sizing, if a stormwater sheet}

## Notes & specs
{general notes, construction notes, spec callouts, permit conditions on this sheet}

## Cross-references
{"See C-5.0 for profile", detail bubbles pointing elsewhere, matchlines}

## Check-the-image flags
{anything the text layer couldn't capture that a human should eyeball}
```

## Land-development specifics to watch for

- **Title blocks** sit bottom-right; `titleblock_hint` in the manifest usually
  captures the sheet number and title — use it to name sheets fast.
- **Quantities that matter for this business:** lot count and lot mix, disturbed
  acreage (permitting), cut/fill balance, water/sewer sizing, WWTP or onsite-system
  capacity (GPD), well siting, road lengths and pavement sections, BMP sizing.
- **Boundary/survey sheets** carry bearings, distances, and the legal description —
  extract these verbatim from the text layer when present; they're precision-critical
  so flag the image for a check rather than paraphrasing numbers you can't read.
- **Plan-and-profile sheets** pair a plan view (top) with a profile (bottom) keyed by
  station; note the station range and which utility/road the profile is for.
- **Matchlines** mean a feature continues on an adjacent sheet — record both sides in
  Cross-references so routing works.
- **Scanned/as-built sheets** (no text layer) are common in older or recorded plats —
  rely on the image and OCR only if you need bulk text.

## When a summary isn't enough

If a query needs exact geometry, a dimension you can't read at the current raster,
or a detail callout, open `sheet_NNN.png`; if still ambiguous, open the split
`sheet_NNN.pdf` (vector, zoomable) or re-rasterize that one sheet at a higher
`--long-edge`. Reserve full-PDF reads for genuine whole-set questions.
