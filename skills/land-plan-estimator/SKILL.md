---
name: land-plan-estimator
description: >-
  Read, index, measure, and estimate from land-development / civil site plan
  sets delivered as PDFs (subdivision layouts, grading & drainage, utility
  plans, road plan-and-profile, erosion control, landscape/buffer plans,
  construction details, boundary/survey). Use this ANY time the user uploads
  or points to a plan set, drawing set, "the civils", a sheet index, or a
  large multi-sheet PDF and wants to query it, summarize sheets, pull
  quantities (lot counts, disturbed acreage, cut/fill, pipe sizes, pavement
  areas, curb LF, buffer LF, setbacks), prepare a land-development budget
  takeoff, or find which sheet a given detail lives on. Trigger even if the
  user just says "read these plans" or "what does sheet C-3 say" — do NOT
  try to stuff the raw PDF into context, use this preprocessing-and-index
  workflow instead.
---

# Land Plan Estimator

## Why this exists

Civil plan sets are large-format, multi-sheet PDFs (often 15-40MB, ARCH/ANSI
D sheets). Dumping the whole set into context is slow, expensive, and
inaccurate — the more you jam in, the worse the answer. The fix is a
one-time preprocessing step that turns each sheet into cheap, structured
data: split the set, pull the vector text layer WITH coordinates, detect
scale, rasterize each sheet, then write a compact per-sheet summary plus a
routing index. After that, answering a question means reading a small index
and one or two sheet summaries. A takeoff means MEASURING off that
structured data with a script — never eyeballing a rendered image and typing
a number.

Everything is file-backed and lives next to the source PDF. No external
database required (an optional SQLite layer exists for a complex set with
many schedule-driven structures — see Step 1b).

**v2 note:** this version folds in the parts of ContractorOS's
construction-takeoff and drawings-analyser skills (reviewed and adapted
2026) that would have caught this business's real estimating mistakes: a
storm pipe size transposed between two adjacent runs, a duplicate paving
lift double-charged, and a curb quantity pulled from a `2 × centerline`
formula proxy instead of a measurement. See "Field-tested gotchas" below —
each one cost a real takeoff on this project.

## The workflow

### 1. Preprocess (`split_extract.py`)

First confirm the set is CAD vector (Civil3D/AutoCAD exports carry a clean
text layer). Run the preflight, then the full pass:

```bash
pip install --break-system-packages pymupdf pdfplumber   # if not present
python scripts/split_extract.py "PATH/TO/plans.pdf" --check-only   # vector vs scanned
python scripts/split_extract.py "PATH/TO/plans.pdf" --split-pdf    # full run
```

`--check-only` reports how many sheets have a usable text layer and stops.
`--split-pdf` is REQUIRED, not optional, in v2 — it writes the single-sheet
PDF every downstream `measure.py` call and the final Bluebeam-safe markup
both need. Add `--sqlite` for a local `plans.db` manifest index when you
want cross-project SQL later; for a single set the `.md` index is enough.

Accepts a merged set or a directory of PDFs. Writes a `*_sheets/` folder
with, per sheet (numbered sequentially across the whole set —
`sheet_001`, `sheet_002`, ...): `sheet_NNN.png` (raster), `sheet_NNN.txt`
(plain text dump, for cheap reading), `sheet_NNN.pdf` (single sheet, for
measuring/markup), `sheet_NNN.json` (word-level text WITH coordinates,
title-zone flags, detected scale, vector geometry counts), and a
`manifest.json` indexing all of it.

Read `manifest.json` first. Key fields per sheet: `titleblock_hint`,
`has_text_layer`, `text_chars`, `scale` (detected factor + confidence — see
below), `vector_drawing_count`. If `scanned_sheets_no_text_layer` is
non-empty, those sheets are raster only. If `sheets_no_scale_detected` is
non-empty, read that sheet's own scale note off the render before measuring
anything on it — never assume a scale.

Tune `--long-edge` if title-block or dimension text is unreadable in the
raster: raise to ~2800 for dense sheets, lower to ~1600 to save tokens on
simple ones.

**Scale detection is metric AND imperial**, because this business's plan
sets are imperial (`SCALE:1" = 40'`, `SCALE:1" = 60'`, `1/8"=1'-0"` for
details) — not `1:100`. It rejects a bare `1:N` sitting next to
FALL/SLOPE/GRADE/BANK/BATTER (civil sheets are full of "MIN 1:50 FALL"
slope callouts, not scales). Still confirm a detected scale against a
printed dimension or a known feature (a lot width, a ROW) before trusting
any length/area off it — see the scale-check gotcha below.

### 1b. Optional deep index (structured DB) — for a schedule-heavy set

For a set with many schedule-driven structures (storm structures, sanitary
manholes, a long plant schedule) where you'll query "how many / where / does
the plan count match the schedule" more than once, build the structured
layer instead of re-reading text each time:

1. **Extract instances per plan sheet** (never on a schedule sheet — a tag
   in a schedule is a DEFINITION, not a placed instance):
   ```bash
   python scripts/extract_instances.py sheet_015.json --pattern "1A-\d+" \
       --sheet sheet_015 --exclude "1500,980,1850,1180" -o takeoff/instances_1A.json
   ```
   `--exclude` drops the schedule/legend box read off one overview render.
   `--space-tolerant` handles CAD letter-spaced tags ("1 A - 1 1").
2. **Assemble `structured.json`** — Claude's judgment, not a script: a
   `schedules` table (type → size/material/spec, from the schedule), an
   `instances` table (from step 1, one row per placed tag with x/y/sheet),
   and `notes` (general-notes callouts). Every row carries a `reliability`
   (HIGH text / MEDIUM vision / LOW scaled).
3. **Build the queryable database:**
   ```bash
   python scripts/build_db.py takeoff/structured.json -o takeoff/plans.sqlite
   ```
4. **Validate provenance — mandatory if you built the DB.** This is the
   single highest-value check in v2: it confirms every value's distinctive
   tokens actually appear on its cited source sheet, and flags or relocates
   the row when they don't.
   ```bash
   python scripts/validate_provenance.py takeoff/structured.json \
       --textdir "PATH/TO/plans_sheets" --fields fields.json \
       --apply -o takeoff/provenance_report.json
   ```
   `fields.json` maps `{table: [id_field, value_field, source_field]}`.
   Report every relocation and flag to the user — don't silently apply and
   move on.

Skip Step 1b entirely for a small or simple set — reading the per-sheet
`.txt`/`.json` directly is faster when there's little to reconcile.

### 2. Summarize each sheet

For every sheet, read its `.txt` (or `.json` for coordinates), and Read its
`.png` (the image carries the linework, callouts, and layout the text layer
misses). Then write `sheet_NNN.md` using the template below. Skip the image
only when the text is already complete for a text-only sheet (general
notes).

Work through sheets in order. For a large set, batch it and note progress.

### 3. Build the routing index

Write `_index.md` in the sheets folder: one line per sheet mapping sheet
number → title → discipline → what lives on it → key quantities → detected
scale. This is what you read first on every future query to decide which
sheet(s) to open.

### 4. Answer queries

Read `_index.md`, route to the relevant sheet(s), read those `.md` files.
For counts/locations/relationships when a structured DB exists (Step 1b),
query it — exact and cheap. Open the `.png` (or the single-sheet `.pdf`)
only when the summary is insufficient or the question is inherently visual.
For any geometry question (an area, a length, a dimension not already
captured), use `measure.py` at query time — never eyeball a scaled distance
off the render and state it as a number.

## Estimating from a plan set

When the task is a takeoff or estimate, not just Q&A:

1. Read `references/scope_kickoff.md` and have the user fill it (or state
   scopes inline). Only estimate the divisions they include.
2. Use `references/pay_items.md` as the target list and section order.
   Measure for those items in the included divisions. Add items the plan
   shows that the catalog lacks; never silently drop scope.
3. Break out segregated scopes into their own sections: pump/lift station,
   package plant/WWTP, and each offsite roadway. Catch offsite by callout (a
   named public road, "OFFSITE", NCDOT encroachment, a station range beyond
   the boundary), not by where it sits in a sheet, and record the station
   limits so onsite and offsite never double-count.
4. Carry the same exclusions the bids use (geotech, SWPPP inspection,
   import/export, rock, permits) so an estimate lines up against a real bid.
5. **Transcribe schedule tables in full — never eyeball-summarize one.**
   Pipe schedules, structure schedules, and plant schedules (storm/sewer
   FROM-TO-SIZE-LENGTH tables, curb inlet/drop inlet/FES counts, buffer
   plant lists) are the sheet's ground truth. Use `measure.py tables`
   (pdfplumber) against the schedule's bbox, or pull every row into a small
   script, sum by category programmatically, and only then compare to
   whatever number you had before. A schedule with 40+ rows is exactly
   where a visual skim mis-sizes one segment (15" read as 12", or the
   reverse) — that class of error doesn't show up as a wrong total, it
   shows up as two adjacent line items each wrong by the same amount in
   opposite directions. If two pipe (or structure) sizes in the same
   network look off by a matching amount, that's the signature — go
   re-pull the table. **This happened on Cottages at Back Creek**: a 56'
   run was read as 15" when the schedule said 12", overstating one line and
   understating the other by the same 56'.
6. **Variable-width or tapered geometry needs a station-by-station
   takeoff, not a plan-view label.** Turn lanes, roadway widenings, tapers,
   and anything else that isn't a constant cross-section over its length
   cannot be measured from a single width callout. Pull the actual
   cross-section sheets (usually keyed by station), record the width at
   each station, and compute area with average-end-area (length × average
   of the two end widths) per segment. Treat a uniform-width assumption for
   this kind of item as a placeholder to be replaced, not an estimate to
   defend.
7. **Before dropping new numbers into an existing budget template, audit
   the whole section you're touching — not just the rows you plan to
   edit.** Dump every row in that category (labels, quantities, formulas)
   and check for (a) another row with the same or a near-duplicate label
   that's already active, (b) formulas that still reference an input cell
   and fire even though the row looks like an unused template default.
   **This happened on Cottages at Back Creek**: two near-identical "1.5"
   intermediate course" paving rows were simultaneously active, effectively
   double-charging one lift — caught only because Dave asked for a
   reconciliation against the plan's own pavement section. Re-run this
   audit any time you add a line to a category.

### Measuring primaries with `measure.py`

Do the actual measuring off the durable single-sheet PDFs, one sheet at a
time. `measure.py` writes JSON to stdout (redirect or capture it). See its
own docstring (`python scripts/measure.py --help`) for the full command
reference; the essentials:

- **Counting (tagged items):** `measure.py count --tags ... --exclude-bbox
  ...` — the reliable way to count a tagged structure/fixture. Pass the
  exact tag strings you learned from the legend/schedule. **Three-way
  cross-check, not optional:** the text-layer count, the schedule's stated
  Qty, and a visual pass over the markup (Step 6) must agree. If they
  diverge and you can't reconcile them, say so and drop the confidence.
- **Lengths (pipe runs, curb, buffers):** `measure.py length --bbox ...
  --scale ...` returns every polyline in the region with length in FEET,
  stroke colour, and width, plus a `by_stroke` rollup. Isolate the item by
  stroke (matched to the legend) and region, then sum. **Prefer a
  plan-stated length when one exists** (`measure.py dimensions` over the
  label) — a called-out "125.00'" beats a computed polyline.
- **Areas (basins, pavement zones, buffers, clearing limits):**
  `measure.py polygons --bbox ... --scale ...` returns area in SF and
  acres, largest-first. Validate against the visual before trusting it.
- **Depths / volumes:** volume is always area × depth — never measured
  directly. Read the depth from a section, detail, or schedule
  (`measure.py dimensions` or `tables`), then multiply. If it genuinely
  isn't on the drawings, use a stated default and write the assumption
  into the takeoff.
- **Schedules:** `measure.py tables --bbox ...` (pdfplumber) reads a
  cropped schedule region as structured rows. Don't rely on auto-detection
  to LOCATE the schedule on a busy sheet — crop to its region first.

Pass `--scale` as an engineering ratio (`--scale "1:480"`), a plan-stated
imperial note (`--scale "1\"=40'"`), or an explicit `--ft-per-pt` override.
**Always confirm the detected/stated scale against a grid-spacing regularity
check or a printed dimension before trusting any length/area from it** — a
wrong scale throws areas off by the square of the error and volumes by the
cube.

### Write the element ledger as you measure — `takeoff/elements.json`

The assemblies (primary measurement → derived pay items) are the takeoff's
*derivation* layer. The ledger is its *evidence* layer: one machine-checkable
record of everything found, defined, and measured, so the reconciliation
pass (below) runs mechanically instead of by recollection. It costs almost
nothing — `count`, `polygons`, and `length` already return every coordinate;
the discipline is writing them down in one place as you go.

Record three kinds of entry:
- **Definitions** — every tag a schedule defines: `{tag, sheet, schedule_qty
  (if the column is filled), stated_size_or_length (if any)}`.
- **Instances** — every counted hit: `{tag, sheet, x, y, source: "plan" |
  "schedule" | "detail"}`. Only `source: "plan"` instances are additive.
- **Measurements** — every Linear/Area/Volume primary: `{item, kind, value,
  units (LF/SF/AC/CY), sheet, scale, method, confidence, notes}`.

### Reconcile before it ships (do not skip)

A takeoff that hasn't been checked against itself and the plan is a draft,
not a deliverable. Two passes:

**Deterministic, over `takeoff/elements.json`:**
1. **Schedule vs. plan** — for every tag with a stated schedule Qty, the
   plan-instance count must equal it. Divergence gets reconciled (wrong
   exclude box, a phantom detail-view duplicate) or the line's confidence
   drops with the discrepancy stated in the notes. This is the check that
   catches a mis-sized pipe run or a miscounted structure before it ships.
2. **Cross-sheet duplicates** — the same structure/fixture shown on a plan
   AND a detail/profile view is ONE item; a detail-view instance is never
   additive.
3. **Section audit** — before a new line goes into the budget template, the
   whole category it joins gets dumped and checked for duplicate-label rows
   or stale formulas still referencing an input cell (item 7 above).

**Independent — a blind subagent anchor-dimension check, for every
length/area that isn't a plan-stated number:** the person who measured
something will "see" agreement with their own number even when it's wrong —
the same reason a single radiologist re-reading their own scan catches
less than a second reader would. Use the Agent tool to spawn a subagent
that has **not** seen your total: give it the sheet(s), the scale, and the
measurement's geometry/region — never your computed answer or your
narrative — and have it:
1. Derive an **independent anchor** from a different source than the
   measurement being checked (a stated ROW width, a lot dimension, the
   distance between two grid/station callouts, the site boundary).
2. Check the measurement's plausibility against that anchor and return a
   ratio and a verdict: `plausible` (in a sensible band) or `out-of-band`
   with a suspected cause (wrong scale, wrong region, a formula-proxy
   standing in for a measurement, a double-counted segment).

**This is exactly the check that would have caught the curb-quantity
problem on Cottages at Back Creek**: the only active curb line used
`= 2 × road centerline` — a convenience formula that systematically misses
cul-de-sac bulb curb and intersection returns — and it looked plausible
enough on its own that it shipped unchecked until Dave supplied his own
measured total. An anchor check against the actual curb linetype (or, if
none exists, an explicit `verify` flag on the formula-proxy number) is what
should have run first. Treat any `out-of-band` verdict as a correction
trigger: re-measure, and only ship the figure if it survives re-measurement,
with the anomaly explained in the notes.

## Mark up the drawings (Step 6)

A takeoff shouldn't live only in a spreadsheet. Mark every sheet you
measured — one translucent box per counted item (`count --markup-out`
builds the spec automatically, one colour per tag), or a shaded polygon for
a measured area/extent. **A guessed "zone" box standing in for a real count
is banned** — mark per item, driven by the item's own captured coordinates,
or ship no overlay for that line.

**Bluebeam-safe output is required for the final deliverable markup.**
`measure.py markup` (PyMuPDF annotations) is fine for a quick on-screen
check, but a PyMuPDF-saved PDF will **not open in Bluebeam Revu** — it
rewrites the document structure in a way Bluebeam's parser rejects (Chrome/
Adobe tolerate it, which hides the problem until the file reaches the
person who actually uses Bluebeam). Overlay onto the ORIGINAL single-sheet
PDF with `pikepdf` instead, and save without object streams:

```python
import pikepdf, json
from pikepdf import Name, Dictionary, Array

def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

pdf = pikepdf.open("sheet_015.pdf")          # the ORIGINAL single-sheet PDF, not a PyMuPDF re-save
pg = pdf.pages[0]
res = pg.obj["/Resources"]
H = float(pg.obj["/MediaBox"][3]) - float(pg.obj["/MediaBox"][1])   # read per page, never hardcode
egs = res.get("/ExtGState") or pdf.make_indirect(Dictionary()); res["/ExtGState"] = egs
ops = json.load(open("markup_015.json"))["ops"]
body = ["q"]
for i, op in enumerate(ops):
    x0, y0, x1, y1 = op["rect"]
    r, g, b = hexrgb(op.get("fill", "#1E88E5"))
    gname = f"/GSmk{i}"
    egs[Name(gname)] = Dictionary({"/ca": op.get("opacity", 0.35), "/CA": 1.0, "/BM": Name("/Normal")})
    # PyMuPDF rect (y-down, top-left) -> PDF content stream (y-up, bottom-left): flip Y by page height
    body += [f"{gname} gs", f"{r} {g} {b} rg", f"{x0:.2f} {H-y1:.2f} {x1-x0:.2f} {y1-y0:.2f} re f"]
body.append("Q")
st = pdf.make_stream(("\n".join(body) + "\n").encode())
c = pg.obj.get("/Contents")
pg.obj["/Contents"] = Array([c, st]) if not isinstance(c, Array) else (c.append(st) or c)
pdf.save("sheet_015_marked.pdf", object_stream_mode=pikepdf.ObjectStreamMode.disable)
```

For a polygon (area) overlay, emit a filled path (`x0 H-y0 m`, then
`x H-y l` per vertex, then `f`) instead of a rectangle.

**Vision cross-check, then correct — don't just sign off.** Render each
marked sheet (`measure.py render`) and read it against the original. A
definition still highlighted means the exclude box needs widening; marks
floating off-target mean the scale or coordinates are wrong. **For every
area/extent overlay, corner-check it**: verify each corner of the shaded
polygon lands on the feature it bounds by reading the rendered page
corner-by-corner. The area *number* can be right while the *shape* is on
the wrong part of the sheet — a page `Rotate` or content-stream transform
can do that, and only a corner check catches it. Never sign off on a
"looks about right" glance.

## Output: the takeoff worksheet + the budget template

The deliverable is two linked things, not one:

1. **A Takeoff Worksheet** (its own small workbook, or a tab appended to the
   budget workbook) — every primary measurement with its method
   (schedule / plan_count / polygon_area / polyline_length /
   annotated_dimension / estimate), confidence, the anchor-check ratio and
   verdict where one was run, the sheet it came from, and the rate SOURCE
   (the template's own default, or a verified bid-rate database — never
   leave this unstated). This is the audit trail: it lets the number in the
   budget template be checked without re-doing the takeoff.
2. **The line-item entries in `references/pay_items.md`'s target
   template** (the existing LD Budget Template workbook) — the actual
   deliverable Dave uses. Cross-reference each entry back to its Takeoff
   Worksheet row.

Deliver both, plus the marked-up drawing PDF(s) from Step 6.

### Confidence: label it, don't fake it

Three reliability levels, marked per line:
- **High:** a quantity printed on the sheet or in a schedule (a stated pipe
  length, a schedule Qty, seeding acreage) — no measurement involved.
- **Medium:** a clean polygon/polyline measurement at a CONFIRMED scale,
  cross-checked (three-way for counts, anchor-checked for lengths/areas)
  and in-band.
- **Low, human-verify:** anything geometric that isn't independently
  checked, a scaled value at an unconfirmed scale, a default depth/rate
  assumption, or an out-of-band anchor check that wasn't re-measured to
  resolution. Flag these `verify`; never present a measured or assumed
  quantity as if it were plan-stated.

A **formula proxy inside the budget template is not a High-confidence
number**, even when it looks precise. `curb LF = 2 × road centerline` is a
convenience default — it systematically misses cul-de-sac bulb curb and
intersection curb returns, which is real length. Treat any such
formula-driven quantity as `verify`: prefer a plan-stated or client-
confirmed total, or a real measured curb linetype, when one is available —
and say plainly when a number is a formula proxy standing in for a real
measurement, not just when it's a raw eyeball takeoff.

Anchor unit prices to the catalog's real bid numbers, but keep measured
quantities separate from stated ones in the output so the human checks the
right rows. **State which rate source you actually used** — the template's
own column defaults, or a verified bid-rate database — rather than letting
the distinction go unstated; if you don't know which it is, say so and ask
before presenting a cost as sourced.

Use this exact structure for per-sheet summaries so they're scannable and
machine-routable. Omit fields that genuinely don't apply; never invent
values — if something isn't legible, write `unclear` and note that the
image should be checked.

```markdown
# Sheet {number} — {title}

- **Discipline:** {cover | survey/existing | site/lotting | grading & drainage |
  utilities (water/sewer) | storm/BMP | erosion control (E&SC) | road plan-profile |
  details | landscape | other}
- **Scale:** {e.g. 1"=40' (factor 480, high confidence); or "not detected — verify"}
- **Sheet no. in title block:** {C-3.0, etc.}

## What's on this sheet
{2-4 sentences, plain language: what a reviewer would find here.}

## Key data
- {lot count / lot range / typical lot dims — for lotting sheets}
- {disturbed area, total site area — acres}
- {cut / fill volumes — CY, if shown}
- {pipe/utility sizes & materials: water main, sewer, storm}
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

- **Title blocks** sit bottom-right; `titleblock_hint` in the manifest
  usually captures the sheet number and title. Title-block text is
  sometimes rotated 90° on large-format sheets — if the hint comes back
  empty or garbled, read the sheet ID off the render instead.
- **Quantities that matter for this business:** lot count and lot mix,
  disturbed acreage (permitting), cut/fill balance, water/sewer sizing,
  road lengths and pavement sections, BMP sizing, buffer/landscape LF and
  plant counts, offsite roadway/turn-lane scope.
- **Boundary/survey sheets** carry bearings, distances, and the legal
  description — extract these verbatim from the text layer when present;
  they're precision-critical, so flag the image for a check rather than
  paraphrasing numbers you can't read. `measure.py dimensions` does NOT
  parse bearings/curve tables — read those off the render.
- **Plan-and-profile sheets** pair a plan view (top) with a profile
  (bottom) keyed by station; note the station range and which utility/road
  the profile is for.
- **Matchlines** mean a feature continues on an adjacent sheet — record
  both sides in Cross-references so routing works.
- **Scanned/as-built sheets** (no text layer) are common in older or
  recorded plats — rely on the image and OCR only if you need bulk text.

## Field-tested gotchas (read these — each one cost a real takeoff)

- **Tags are usually hyphenated** (storm structure "1A-11", "SD-2"). The
  counter keeps hyphens inside a matched tag — pass them exactly as
  written. If `count` returns 0 for every tag on a page that clearly has
  text, it prints a WARNING — never report zeros as "none found" without
  investigating (see the outlined-text gotcha below).
- **A vector PDF can still have NO usable text layer — "outlined" CAD
  exports.** Some DWG/Civil3D-to-PDF exports flatten text to vector
  outlines, so `split_extract` reports a high `vector_drawing_count` with
  `has_text_layer` true (or near-zero text_chars) — this is NOT raster, yet
  `count`/`text` matches nothing. Confirm the signature with `measure.py
  text` over a region you can plainly see has labels: zero hits confirms
  outlined text. Switch to vision counting or the schedules/tables
  instead — don't keep retrying tags.
- **Rotated sheets:** `count` reports hit x/y in the page's native
  (un-rotated) space; `--exclude-bbox` is read in render/display space —
  they don't line up on a rotated sheet unless you use
  `--exclude-bbox-native` (built from coordinates `count` just printed) or
  read the exclude box off a `render --grid` image.
- **Scale is often not a clean callout.** Title blocks may say "AS
  INDICATED." Always run the grid-spacing/known-dimension check (a lot
  width, a ROW, an even station interval) before trusting any area/length
  — a wrong scale throws areas off by the square and volumes by the cube.
- **Exclude the FULL schedule region, not one row.** A schedule can span
  many rows plus a typical-detail callout elsewhere on the sheet that
  repeats a tag — a tight exclude box misses the outlier and it counts as
  a phantom instance.
- **The same structure/fixture on the plan AND a detail/profile view —
  count it once, off the plan.** Treat any non-plan appearance as a
  cross-check, never additive.
- **A scheduled tag may be a LINEAR item, not a count.** Check the
  schedule's SIZE/LENGTH column — a headwall or box culvert callout with a
  stated run length means the tag labels a length, not an EA.
- **Diagrammatic/NTS routing (utility crossings, some erosion-control
  schematics):** you can still trace and mark the route, but never attach
  a scaled length — report a derived allowance and flag it Low. Read the
  general notes for "diagrammatic"/"schematic"/"NTS" before trusting any
  traced-pipe length.
- **Never ship a guessed "zone" rectangle as count markup.** Markup is
  per item, driven by the item's own captured location, or none at all.

## Reference files

- `references/scope_kickoff.md` — read at the start of any estimate. What
  divisions to measure, segregated scopes, exclusions.
- `references/pay_items.md` — the target pay-item catalog (civil divisions,
  imperial units, takeoff basis per item) built from real bids. Enrich it
  as new projects add items; it also carries specific gotcha notes (pipe
  class, paving lift counts, curb formula-proxy caveat).

## Scripts

- `scripts/split_extract.py` — split + raster + vector-extract (text with
  coordinates, scale detection, geometry counts) per sheet. Run once per
  plan set.
- `scripts/measure.py` — the measurement engine: count / polygons / length /
  dimensions / tables / text / page-info / render / markup. Run at query
  time, one sheet at a time.
- `scripts/extract_instances.py` — tag → coordinate-grounded instance, for
  the optional structured-DB path (Step 1b). Schedule-region exclude built
  in.
- `scripts/build_db.py` — load `structured.json` into a queryable SQLite db.
- `scripts/validate_provenance.py` — confirm every DB value's tokens
  actually appear on its cited sheet; relocate or flag when they don't.
  Run this any time Step 1b is used — it is the single highest-value
  accuracy check in this skill.

## When a summary isn't enough

If a query needs exact geometry, a dimension you can't read at the current
raster, or a detail callout, open `sheet_NNN.png`; if still ambiguous, open
`sheet_NNN.pdf` (vector, zoomable) or re-rasterize that one sheet at a
higher `--long-edge`. Reserve full-PDF reads for genuine whole-set
questions.
