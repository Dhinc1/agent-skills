---
name: construction-takeoff
description: All-trade construction quantity takeoff from drawings (PDF or folder). Runs drawings-analyser first, then works the scope against per-trade coverage checklists (structural, architectural, civil, electrical, HVAC, plumbing) for a complete BOQ. Counts tagged items off the vector text layer, measures lengths and areas at scale, derives secondaries via assemblies (volume = area x depth); structural gets concrete, reinforcement and formwork, civil gets earthworks. Hard-to-measure quantities get a flagged estimate, not a blank. Keeps an element ledger and reconciles scope against it; every length/area is anchor-checked against independently derived building dimensions by a blind subagent. Marks up every measured sheet and produces an Excel BOQ with method, confidence and provenance per line. Use when a user uploads drawings and wants a takeoff, BOQ, counts, areas, lengths, concrete, reinforcement, formwork or earthworks - any trade. Trigger on 'take off', 'takeoff', 'quantify', 'count the', 'BOQ'.
---

# Construction Takeoff

Convert a set of construction drawings into a bill of quantities: a complete, structured list of the measured quantities a project needs, with every line traceable back to how it was derived. The quantities drive estimated cost, programme, procurement, and contracts — so getting them right, and being honest about confidence, matters more than producing a big number quickly.

## The mental model

A takeoff is three steps, and this skill follows them in order. Skipping step 1 is the classic way to produce a fast, wrong takeoff.

1. **Work out what to measure.** Review the drawings and decide what to measure before counting anything: the list of quantities the scope needs, and which are measured directly versus derived. Work this list against the per-trade coverage checklists in `references/trade_checklists/` so a whole category never gets silently dropped — they're the starting-point spine of what a complete BOQ carries for each trade. Keep the breakdown simple — separate items into their own lines only where it genuinely changes the result for this scope.
2. **Build the assemblies.** For each thing you'll measure, decide what it *drives*. A measured slab area drives concrete volume, reinforcement, sub-base, and a concrete pump's hours — all by formula. You measure the primary once; the assembly computes the rest.
3. **Measure and generate the bill of quantities.** Do the counts, lengths, and areas. Because the assemblies are set up, each measurement automatically generates its secondary quantities. Consolidate, and out comes the BOQ.

### The principle that makes it work on any trade: AI does judgement, scripts do plumbing

Drawings vary endlessly — by office, country, discipline, and CAD package. The brittle approach is to hardcode rules ("`L\d+` is a light, the title block is bottom-right, `1:100` means…"). That breaks on the first set that does it differently, and it silently can't handle a trade nobody added to the list.

So this skill draws a hard line:

- **Scripts** do the cheap, deterministic work: split the PDF, pull the text layer with exact coordinates, count occurrences of strings they're *given*, compute polygon areas and polyline lengths at a scale they're *given*.
- **Claude** does every piece of judgement: reading the legend and schedules to learn what this set's tags and line-types mean, deciding which quantities are primary, choosing which tokens to count and which regions to exclude, identifying which polygon is the slab, reading the depth off the section, and sanity-checking the result.

The script is never asked what something *means*. That's why it generalises across all trades without a per-trade rule anywhere in the code.

### Run lean

Accuracy first — but most wasted effort is *avoidable* rendering. Don't render-and-look repeatedly to hunt coordinates: read the schedule/legend region off **one** overview render, separate plan instances from definitions deterministically (full count − the one-per-mark a schedule defines), and let `count --markup-out` reuse the hit locations rather than re-finding them. Verify with a **single** marked-render pass per sheet (full sheet, then zoom a dense zone only if needed) at the lowest legible DPI. Extract text once (the engine already uses the complete words-layer). Spend tokens on judgement and verification, not on exploratory re-rendering.

### Field-tested gotchas (read these — each cost a real takeoff)

This skill has been run on real sets; these are the traps that actually bit:

- **Tags are usually hyphenated** (WC-1, FD-2, AHU-3, D-01). The counter now keeps hyphens inside tags, so pass them exactly as written. If a `count` returns **0 for every tag but the page has words**, it prints a WARNING — never report zeros as "none found" without investigating.
- **Rotated A0 sheets:** `count` reports hit x/y in the page's **native** space. `--exclude-bbox` is read in **render/display** space. They do **not** line up on a rotated sheet. To exclude using the coordinates `count` just printed, use **`--exclude-bbox-native`**. (Or read the exclude box off a `render --grid` image and use plain `--exclude-bbox`.)
- **Scale is often not a clean `1:N`.** Title blocks may say "As indicated"; MEP/US sets use **imperial** scales (1/8"=1'-0"). `parse_scale` now accepts imperial (pass e.g. `--scale "1/8=1'-0"` → 1:96), but always **verify scale by the grid-spacing regularity check** before trusting any area/length.
- **The marked PDF must open in Bluebeam.** Do NOT deliver a PyMuPDF-saved PDF as the final markup — its rewritten structure fails to open in Bluebeam Revu. See Step 6 for the pikepdf-overlay-on-original method.
- **A "folder of discipline PDFs" is often NOT one project.** A set handed over as `1. Structural / 2. Plumbing / 3. Architectural / …` can be a *sampler* — each PDF a different building, country and unit system (e.g. an Australian warehouse, a US supermarket, a South-African school). Confirm this in Step 0 and treat each discipline as its own project: **quantities are not additive across trades**, scales/units differ per PDF, and the deliverable must say so. Don't roll them into one building.
- **Area/slab overlays land on the wrong place if the coordinate transform is wrong** — this is the single most common markup failure and it bit a real run. A DXF/CAD-exported PDF can carry a page `Rotate`, a non-trivial content-stream CTM, *and* a y-axis convention that is not a simple `H − y` flip. The measured **area number can be correct while the shaded box is on the wrong half of the slab.** The only defence is the corner-check in Step 6: render the marked page and verify **each of the four corners of the shaded rectangle sits on its corner grid bubble** before signing off. Never deliver an area overlay you have not corner-checked against the drawing.
- **Always deliver the marked PDF as a FILE.** Produce it with the pikepdf-overlay method and save it to the output folder. Do **not** leave markup only "live" in a Bluebeam Revu session — if the tool/workspace goes down, the deliverable is lost. The file is the record.
- **Diagrammatic / NTS routing:** you can still **trace and mark the routes** (polyline overlay) to show coverage, but never attach a scaled metre figure — report the run as a derived allowance / fixture-unit estimate and flag it Low. Marking the route ≠ measuring its length. **Read the GENERAL NOTES for "diagrammatic" / "schematic" / "not to scale" before trusting any pipe length** — MEP plumbing/mechanical sets routinely state "pipe routing shown is diagrammatic" in note 1–3. If they do, every pipe length is an approximation and Low, no matter how cleanly you measured it.
- **Monochrome / greyscale CAD exports — you cannot isolate a system by colour.** Many Revit/CAD PDFs print every service in greys and black with no colour separation, so the `length` command's `by_stroke` colour rollup will NOT separate "all the cold-water line". Then isolate the pipe by **line-weight** (pipe is drawn heavier than the architectural background — filter strokes to width ≥ ~1.0 and a dark, non-background colour) **plus the size label on the run** ("1\" CW", "4\" S") read off the legend — never by colour alone. Say in the notes that the figure was isolated by weight, because that also sweeps in some non-pipe heavy linework (borders, leaders) and widens the band.
- **Dashed pipe undercounts its own length.** Domestic water / vent / gas are often drawn **dashed**; `length` sums only the dash marks, not the gaps, so the raw figure is short by the gap fraction (≈ 40–55%). Read the dash duty-cycle off a zoom (dash vs pitch) and divide by it, or measure a representative **solid** equivalent run, before reporting. The corrected figure is still Low.
- **The same fixture is on the plan AND the risers/part-plans — count it once, on the plan.** On plumbing sets a WC/lav/urinal/sink shows on the overall floor plan, again on the enlarged restroom part-plans, and again on the riser diagrams (one fixture, 2–3 appearances). Take fixture **counts off the overall floor plan only**; treat part-plans/risers as a cross-check, never additive. (Real run: a riser sheet showed WC×8 / LAV×16 against the plan's WC×10 — adding them would have inflated the count.)
- **A tagged item's LENGTH may be stated in its schedule — read it, don't scale it.** Trench drains, ground beams, counters etc. often carry their run length in the fixture/equipment schedule (e.g. "8 FT (2.44 m)"). The schedule figure is High; a scaled polyline of the same item is Medium at best. Check the schedule's size/length column before measuring any linear.
- **A vector PDF can still have NO text layer — "outlined" CAD exports.** Many DWG/Revit-to-PDF exports flatten *all* text to vector outlines (curves), so `split_extract` reports tens of thousands of vector paths but `words = 0` with `source_type` vector/mixed — it is **NOT raster**, yet `count` matches nothing and prints its 0-tags WARNING on every sheet. Don't report "no tags found": recognise the signature (**high vector-path count AND words ≈ 0**) and either vision-count, or take quantities off the **schedules / single-line diagrams** instead. You can still read the outlined text off a render (titles, legends, schedules); for landscape content on a portrait sheet, render **rotated** (often 270°) and crop the table band **full-width** so a whole row of items is counted in one pass with no left/right seam double-count. **Confirm it positively in one line** — `text`-search the page for a tag you can plainly SEE on it (e.g. `page.search_for("B2")`). If a printed tag returns **zero** hits, the text is outlined: stop trying to count by text and switch to vision or the schedules. (A schedule sheet on the same set will return real hits — that contrast is the proof.)
- **"For Tender" sets often don't contain the quantities at all.** Before promising counts, confirm the numbers are actually printed. Schedule Qty columns are frequently **blank** with a note like "quantities to be confirmed by contractor", and single-line-diagram **"No. of points" / "Load" rows are placeholders ("X" / "XX")**. If so, the count is simply not in the document — quantify what IS there (circuits by type, cable sizes, equipment types/specs) and say plainly that fitting/outlet counts and cable lengths need a plan symbol count. **Never manufacture numbers to fill the column.** Surface this in Step 0 so the user can choose to authorise a plan symbol count (the contractor's tender count) before you spend on it.
- **Electrical: the single-line diagram (SLD) is a primary counting source — when it's filled in.** A DB schedule / SLD lists every final circuit by designation (Lighting / Socket Outlet / Dedicated SSO / Air-conditioning / Geyser …) with its cable size and breaker, so counting circuits by designation off the SLDs is more reliable than symbol-counting the plans and hands you the cable size per circuit for free. Lighting circuits are typically 3×2.5mm² and socket circuits 3×4mm² (verify on the sheet). But heed the placeholder warning above — confirm "No. of points" carries real numbers before treating a circuit count as a fitting count, and remember a circuit count ≠ a fitting/outlet count.
- **When you must vision-count, fix the EXTENT of the work FIRST — never count a guessed sub-region.** The trap: zoom into the obvious dense cluster, count it, and silently miss a whole wing. Before counting, bound the *real* extent of the trade's content — take the bounding box of the discipline's own colours straight from the vector geometry (e.g. the red fittings + blue wiring on an electrical plan: walk `page.get_drawings()`, keep paths whose stroke is that colour, and record min/max x,y), or scan the full sheet at low DPI — then tile the WHOLE of that extent so every zone is covered. A count from a partial region is an undercount, and it won't *look* wrong until someone checks the markup against the drawing. (Real run: counted the obvious office cluster, missed a boardroom + offices in the lower band → ~40% undercount, only caught when the overlay was finally rendered.)
- **Never ship a "zone" rectangle as markup — markup is per item, or nothing.** A translucent box drawn around "where I counted" serves no purpose: it proves nothing, can't be checked against individual items, and if its coordinates were eyeballed it visibly won't match the drawing — which destroys trust even when the numbers are fine. Markup means **one mark per counted/measured item**, driven by the item's own captured location (Step 6), then rendered and verified. If you can't mark per item (a schedule/SLD-only count with no plan coordinates), deliver **no** overlay and rely on per-line provenance in the workbook. A decorative box is worse than no box.

## Composition with related skills

- **drawings-analyser — RUN THIS FIRST, every time.** This skill's default Step 0 is to hand the whole set to `drawings-analyser` to break it up: it produces a `drawings_analysis/` folder with single-sheet PDFs, per-sheet classifications (type/discipline), a symbol library with crops, the detected scale, a cross-reference graph, and "Answerable / Coordinate hints" — i.e. the scope, scale and tag vocabulary handed to you on a plate. **Always run it first** (or reuse an existing `drawings_analysis/` or `0. AI Context/` folder from a previous run) before any measuring; only fall back to this skill's own lighter split-and-read pass if drawings-analyser is genuinely unavailable. Do NOT use drawings-analyser for the takeoff itself — it *understands* the set, this skill *measures* it.
- **assemblies** — that skill produces a ZZTakeoff import sheet and a *human* measurement worklist (its rule: a person does the final measuring). This skill is the other path: it does a *full AI takeoff*, measuring the primaries itself and filling in the quantities. Same primary-vs-secondary backbone, different division of labour. Keep the Excel column names aligned so a user can move between them.
- **pdf-markup** *(optional)* — the skill marks up and renders drawings itself (Step 6, via `measure.py`). If the richer pdf-markup skill happens to be installed, you can use it for fancier annotation, but it is not required.

### Reference files (read these at the steps noted)

- `references/trade_checklists/` — **read at Step 1.** One starting-point coverage checklist per trade (`structural.md`, `architectural.md`, `civil.md`, `electrical.md`, `hvac.md`, `plumbing.md`) plus a `README.md` file-map. Walk the relevant trade's checklist category-by-category so the takeoff doesn't under-extract. Each file lists the primary quantities and ends with a worked assembly showing how one primary expands into its secondaries.
- `references/derivation_library.md` — **read at Step 2 and Step 5.** The ratios, waste factors, default depths, and sanity benchmarks that turn each measured primary into its derived secondaries.


## Setup

```bash
pip install pymupdf pdfplumber Pillow openpyxl pikepdf --break-system-packages
# qpdf is also used for Bluebeam-safe output; install if missing (apt-get install -y qpdf).
```

Work in a scratch dir and write final deliverables to the user's output folder. **Paths are environment-specific** — do not assume `/mnt/user-data/...` or `/home/claude/...`; use whatever uploads/output locations this session actually provides (in Cowork these are session-scoped). Everything the skill needs — splitting, text/geometry extraction, counting, markup, rendering — is in `scripts/`. For the *Bluebeam-safe* marked PDF you also use `pikepdf` + `qpdf` (Step 6).

`measure.py` writes its result as JSON to **stdout** — redirect or capture it (`... > out.json`); it does not write a file unless you ask (`--markup-out`, `render --out`, `markup --out`). `get_drawings()` (used by `polygons` and `length`) is the heavy step and can take ~40 s on a big raster sheet, so work **one sheet at a time** and give it room rather than running the whole set at once.

---

## Workflow

### Step 0 — Understand the set, and confirm scope

You cannot take off what you don't understand. Before measuring:

1. **Run `drawings-analyser` FIRST (the default first action).** Hand the set to the `drawings-analyser` skill to break it into single-sheet PDFs and produce per-sheet classifications, a symbol library, the detected scale, and a cross-reference graph (a `drawings_analysis/` folder). If a `drawings_analysis/`, `0. AI Context/`, or `manifest.json` from a previous run already exists, reuse it rather than re-running. Read those artefacts — that *is* Step 0, and it hands you the scope, scale, and tag vocabulary. **Only if `drawings-analyser` is genuinely unavailable** do you run this skill's own lighter split-and-read pass (step 2 below).
2. **Fallback split-and-read (only when drawings-analyser is unavailable).** Run `split_extract.py` to get one PDF + one text-layer JSON per sheet (add `--render` for PNGs you'll want for vision spot-checks):
   ```bash
   python scripts/split_extract.py "/path/to/drawings.pdf" -o ./takeoff/sheets --render
   ```
   Then, for each sheet, read the JSON and (where useful) the PNG and work out — *yourself, not by regex* — its drawing type, discipline, and **scale**. The JSON gives you `scale_candidates` and `source_type`. **Scale detection is weak in practice** — `scale_candidates` is often empty or ambiguous, and title blocks may read "As indicated". So:
- Read the **plan's own scale note** (e.g. "SCALE 1:250") off a render, not just the title block.
- Handle **imperial** scales (1/8"=1'-0" = 1:96, 1/4"=1'-0" = 1:48, 1"=20' = 1:240). Pass them to `--scale` directly (e.g. `--scale "1/8=1'-0"`) or convert to `1:N`.
- **Always confirm scale with the grid-spacing regularity check** (Step 5): even bay spacings (e.g. 11.5 m × 12) are strong evidence the scale is right; uneven spacings mean it's wrong.
- When the scale is missing or "As indicated", use the **scale-calibration ladder** in the gotchas above (search every sheet for a printed scale → even grid-bubble spacing → footprint vs known building type). Don't calibrate off noisy dimension-text "chains".
- A `raster` sheet has no usable vector geometry; lean on the PNG and schedules, and say so.
- **Check for an "outlined-text" vector export early.** If `split_extract` (or drawings-analyser) shows a high vector-path count but `words ≈ 0` (and `source_type` is vector/mixed, not raster), the publisher flattened the text to curves — there is no text layer to count, on *any* sheet. Don't burn time retrying `count`; decide up front whether to vision-count or to lift quantities from the schedules / single-line diagrams, and tell the user which.

**Large MEP PDFs:** `split_extract` can be slow / get killed on big raster-heavy sheets — the kill happens during the **rendering** of large rasters. If so, don't split the whole set up front: split per page with qpdf and work on demand (e.g. `qpdf in.pdf --pages in.pdf N -- pageN.pdf`) and run `measure.py` per sheet. Fixtures/services often live on **one** plan each (e.g. waste & vent on P100, water on P101) — take each quantity off the sheet it lives on, not every "plan".
3. **Learn this set's vocabulary.** Read the **legend** and the **schedules** (drawings-analyser's symbol library is the head start here). This is what replaces a hardcoded tag dictionary: you find out that on *this* job `L1` is a recessed downlight, `L2` is a batten, the dashed red line is the fire main, `FW100` labels 100 mm foul water. Note the exact tag strings and line-types you'll later count and measure — and note that legend entries are *definitions, not instances*. **While you're in the schedules, check whether they actually carry quantities** (a filled Qty / No.-of-points column) or are blank "to be confirmed by contractor" placeholders — that determines whether a count is even extractable (see the "For Tender" gotcha).
4. **Confirm scope with the user.** Takeoffs are scoped to a purpose. Ask what trade(s) and which sheets are in play, and what's in or out — unless they've already said. Don't silently take off everything if they wanted just the electrical. **If the set turns out to have no text layer and/or no scheduled quantities, raise it here** and let the user choose the method (vision count vs schedule/SLD-only vs not feasible) *before* you spend.

Show the user a short read-back: sheets found, types/disciplines, scales detected, the tag/line vocabulary you've learned, whether quantities are actually present in the document, and the scope you'll work to. Let them correct it before any measuring spend. (You'll turn this into the full coverage list in Step 1, working against the trade checklists.)

### Step 1 — Work out what to measure (recommend the primary quantities)

From the understood set and the agreed scope, produce a **recommended list of quantities to measure**, and present it for confirmation *before* measuring. For each line give: the element, the **measurement type** (Count / Linear / Area), the **tag or label** it corresponds to (from the legend — not a guess), and the sheet(s) it lives on.

**Build the list against the trade coverage checklist — this is what stops the takeoff under-extracting.** The most common failure of a takeoff is not a wrong number, it's a *missing* one: the obvious items get measured and a whole category is silently dropped. To prevent that, open the checklist for each in-scope trade in `references/trade_checklists/` (see its `README.md` for the file map: `structural.md`, `architectural.md`, `civil.md`, `electrical.md`, `hvac.md`, `plumbing.md`) and **walk every category in it**, deciding for *this* project whether each line is present, absent, or needs splitting. Don't work from memory — open the file; missing a category is the exact error the checklist exists to catch.

These checklists are a **starting point, not an exhaustive script**. They give a known-good spine of the primary quantities a complete BOQ for that trade usually carries, plus a worked example of how one primary expands into its secondaries. Two things follow:
- **Add what the list doesn't have.** Every project carries items no generic list anticipates — after walking the checklist, scan the actual drawings and schedules for anything extra and add it.
- **Account for what isn't there, don't drop it.** A category with nothing on the drawings becomes a one-line "not in scope" note, never a silent omission. That way the read-back proves you *considered* every category.

Decide what is **primary** (measured directly) and what is **secondary** (derived from a primary by formula). The checklist lines are the primaries; everything they drive is a secondary. Measure the minimum set of primaries and let everything else ride on an assembly — fewer measurements means fewer chances to miss something. See `references/derivation_library.md` for what's conventionally primary vs derivable per trade, and the worked assembly at the foot of each checklist for the expansion pattern.

**Land a quantity on every relevant line — even a rough one.** If an item is clearly present but impractical to measure precisely, estimate it (off the building footprint, a count × a rate, a perimeter) and flag it **Low** with the basis in the notes, rather than leaving it blank. A flagged estimate is information the estimator can challenge; a blank is a hole they'll miss. (The one thing you never do is invent a quantity the drawings don't contain — see "Honesty about confidence".)

Keep the breakdown simple. Split one item into two lines only where it genuinely matters for this scope — a type/size/grade that changes the result, a different installation method, or items living on different sheets. Don't split for the sake of it.

**Take each quantity off the right *type* of drawing — this is the single biggest source of double-counting.** The same element appears on several sheets: a column is on the plan, the footing plan, and two elevations; a precast panel is on the plan and one elevation; a plumbing fixture is on the floor plan, the enlarged part-plan, and the riser. So:
- **Counts** come from the **plan or the schedule**, once — never from elevations, sections, part-plans or risers (those re-show the same items 1–2+ more times; counting there double- or quadruple-counts).
- **Elevations/sections** are where you get **wall/cladding/panel areas** (face length × height), **member lengths** (girt and purlin runs), and **heights/levels** — not instance counts.
- If the scope spans both, decide *per quantity* which sheet is its source, and say so. A sheet being in scope doesn't mean every tag on it gets counted.

> Present it as: "Here's what I propose to measure directly, off which sheet, and what I'll derive from each. Anything to add or drop?" Wait for sign-off.

### Step 2 — Build the assemblies

For each confirmed primary, define the assembly: the secondaries it drives and the formula for each. Read `references/derivation_library.md` for the standard assemblies, ratios, waste factors, and default depths/thicknesses.

The one rule that never bends: **volume is always an area times a depth.** You don't measure a volume off a 2D sheet — you measure the area and read the depth/thickness from a section, detail, or schedule, then multiply. Same for trench volumes, footing volumes, asphalt layers.

Record each assembly so Step 4 can apply it mechanically, e.g.:

```
Primary: Slab on ground — 150mm   (Area, measured)
  ├ Concrete volume   = area × 0.150 × 1.05         m³   (thickness 150mm from S-202 §, 5% waste)
  ├ Reinforcement     = (area × 0.150) × 100        kg   (100 kg/m³, confirm vs structural spec)
  └ Sub-base          = area                        m²
Primary: Slab edge formwork        (Linear, measured separately — perimeter)
```

Where a material/productivity library and cost codes exist (e.g. via the `assemblies` skill conventions), reference them so the takeoff carries through to pricing; leave rates blank and flag if no match.

### Step 3 — Measure the primaries

Now do the actual measuring, one sheet at a time, working off the durable single-sheet PDFs in `sheets/` (or drawings-analyser's `drawings_analysis/`). The method depends on the measurement type. **Everything here is driven by what you learned in Step 0** — you supply the semantics, the script does the geometry.

#### Counting (tagged items)

Counting is the most reliable measurement, *if* done off the text layer rather than by eyeballing symbols. You already know the exact tag string for each item (Step 0). Count it:

```bash
python scripts/measure.py count "sheets/E-101.pdf" --tags L1 L2 GPO \
    --exclude-bbox 1500 980 1850 1180   # the legend/schedule box — definitions, not instances
```

- Pass the **exact tokens** you identified. The script reads the vector text layer in **words mode** (not span mode — span mode silently drops text held in form XObjects on many CAD exports, which can undercount by 3–5×), and it segments each text run against your vocabulary, so a standalone `L1`, a jammed `L1L2`, and `L1` inside "L1 RECESSED" all resolve correctly while unrelated runs like `SL81` are rejected. It returns a count and the coordinates of every hit. Coordinates are handled in the page's native space, so **rotated sheets (very common for A0/A1) are dealt with automatically** — including any `--bbox`/`--exclude-bbox` you read off a (rotated) render.

- **If `count` returns 0 on every tag of a page that clearly has text**, the page almost certainly has **no text layer** — either a raster scan or an outlined-text vector export (see the gotcha). Verify with `split_extract`'s `words`/`source_type`; don't keep retrying tags. Switch to vision counting or to the schedules / single-line diagrams, and flag confidence accordingly.

- **Three-way cross-check — this is not optional.** A clean count means the text-layer number, the schedule, and the visual all agree:
  1. **Text count** — what `count` returns.
  2. **Schedule** — does it reconcile with the relevant schedule (door schedule row, footing schedule, fixture schedule)?
  3. **Vision** — mark every hit (Step 6's translucent boxes) and look. If the highlights are *sparse* against obviously-tagged items, the text layer is incomplete for this sheet — investigate the extraction before trusting the number. If they're *dense and complete*, you're done. (On a real sheet this is exactly what exposed a 3× undercount: the markup was visibly sparse.)
  If the three diverge and you can't reconcile them, say so and drop the confidence — don't report a tidy number you don't believe.

- **Exclude the FULL schedule, not one row.** A schedule often spans many rows (e.g. F1–F13, then DF1, SF1, GB1 lower down) plus **typical-detail / note diagrams** that contain countable tags (a "FTG DF1" detail will have live `DF1` text). A single tight exclude box misses the outliers — they then count as phantom instances. Cover the whole schedule extent AND any note/detail that repeats a tag, then re-verify in Step 6 that **no** schedule/legend/note cell is highlighted.
- **A scheduled tag may be a LINEAR item, not a count.** Check the schedule SIZE/LENGTH column: "400 WIDE × 600 DEEP" (a strip footing / ground beam), a trench drain "8 FT (2.44 m)", or a pipe/tray run means the tag labels a *length*, not an EA — measure it as Linear (or read the stated length straight from the schedule), don't report the label count as a quantity.
- **Separate plan instances from definitions.** Every mark usually appears **once in the schedule** (and sometimes in a typical-detail note), and those must not be counted *or marked*. Exclude those regions with `--exclude-bbox` (read off one overview render) — this is the mechanism that keeps the count **and** the markup to real instances, since the markup is driven by the count's locations. Then **cross-check the total** the deterministic way: full-sheet count minus one per mark the schedule defines (minus any note/detail occurrences) should match. If it doesn't, your exclude region clipped too much or too little — adjust and confirm against the marked render. (Don't try to auto-detect the schedule as a "table" to locate it — on a busy drawing the table finder latches onto the sheet gridlines and returns a page-sized box.)

- Count each resource/installation variant **separately** (that's why they're separate primaries). Counting from text is reliable; counting from symbols by vision is not — only fall back to a careful vision count when an item genuinely has no text tag, and mark it lower confidence when you do.

#### Lengths (linear items)

Linear quantities (pipe, cable tray, ductwork, kerb, walls) come from vector geometry at the sheet's scale — but only after you know *which* lines are the item.

1. Work out what the line means: from the **line-type legend** and from the **text label sitting next to the run** (e.g. "FW100", "150 CT"). Extract the actual label — don't infer service or size from line thickness alone.
2. Measure with the scale you confirmed in Step 0:
   ```bash
   python scripts/measure.py length "sheets/H-201.pdf" --bbox 200 200 1400 900 --scale 1:100
   ```
   This returns every polyline in the region with its length in metres, plus its **stroke colour and width**, and a `by_stroke` rollup. Use the stroke (matched to the legend's line-type) and the region to isolate the runs that belong to the item, and sum those.
   - **On a greyscale/monochrome export `by_stroke` colour won't separate systems** — isolate by line-**weight** + the size label instead (see the gotcha). **Dashed runs undercount** — `length` sums dashes not gaps; correct by the dash duty-cycle or measure a solid equivalent, and flag Low.
3. **Prefer an annotated length** where the drawing states one (run `measure.py dimensions` over the label region) — a called-out "25m" beats a computed polyline. Computed lengths are inherently less certain than counts; reflect that in confidence.

#### Areas

1. Identify the boundary you want, and what to subtract (the office cut-out inside a warehouse slab; voids; the stair). This is judgement — read the room labels and the plan.
2. Measure:
   ```bash
   python scripts/measure.py polygons "sheets/S-101.pdf" --bbox 80 50 1620 720 --scale 1:100
   ```
   Returns closed polygons largest-first with area in m². The largest is usually the gross boundary; subtract the cut-outs you identified.
3. **For slabs, the grid-extent method is usually the PRIMARY method, not a fallback.** Slab edges are almost never a single closed vector polygon — `polygons` typically returns only small sub-rectangles (a room), never the 10,000 m² floor. So for any slab/floor, go straight to the **gridline extents**: take the corner grid bubbles, measure the span between them at scale, `length × width` = footprint, and confirm the bay spacing is even as a scale check. **Build the boundary rectangle from the gridLINE positions, not the bubble-circle centroids** — on a grid that bubbles only two sides, the centroid bounding box is offset into the margin (this produced a visibly wrong slab overlay until corrected). Deduct cut-outs (office, voids). A stated overall dimension beats both, where it's live text.
   **If pipe/duct routing is annotated "diagrammatic" / "schematic" / NTS** (common on plumbing & services plans), do **not** scale polylines for length — it's fiction. Derive runs from a per-fixture branch allowance or fixture-unit method, or take length only off a coordinated/isometric sheet, and flag the confidence.
4. **Validate against the visual** — shade the boundary (a translucent `box`/`cloud` via Step 6) and confirm it covers what you intended. A returned area far from expectation usually means the bbox clipped the polygon or you grabbed the wrong one; widen or narrow and re-query. Never report an area you haven't eyeballed.

#### Site sheets — measure earthworks too (don't stop at the structures)

A civil / site sheet is not finished when you've counted the pipes and manholes. The largest-value civil quantities are usually the **earthworks**, and they are easy to forget because they have no tag — yet "extract every quantity relevant to construction" means they must be on the BOQ. On any site / civil / external-works sheet, always ask for these and measure or estimate them:

- **Site clearing & grubbing (m²)** — the developed / disturbed platform area. Measure it as a polygon: take the extent of the development (the paved + building + courtyard cluster) off the site plan at the confirmed scale. A density/extent method on the coloured development works well; flag ±, since the cleared area usually runs a little beyond the paving to working margins.
- **Topsoil strip (m³)** — clearing area × strip depth (150 mm typical if not stated). Note the assumption.
- **Bulk cut and fill (m³)** — this is the one people skip because it isn't drawn as an object. Derive it from the **contours vs the finished levels**: read the existing-ground contour range crossing the platform (e.g. 1247–1257) and the finished floor / platform levels (FFL callouts, e.g. ~1251), and estimate an **average cut depth and fill depth** over the platform; volume = platform area × average depth. Say plainly it is an order-of-magnitude figure and that a proper **cut/fill needs a TIN / spot-level model** (existing surface vs proposed surface) to firm up — a 2D PDF does not carry the two surfaces. Flag **Low**, but **report a number** — a missing earthworks line is a worse error than an approximate one.

#### Depths (for volumes)

Volume = area × depth. Read the depth/thickness from the **section, detail, or schedule** — `measure.py dimensions` over the relevant region, or `measure.py tables` for a schedule. If it genuinely isn't on the drawings, use a default from `references/derivation_library.md` and **write the assumption into the takeoff**. Never bury an assumed thickness.

Tag every measured value with **method** (text_count / polygon_area / polyline_length / annotated_dimension / schedule / vision_count / estimate) and **confidence**, and keep its provenance (sheet, scale, region/command). This is what makes the takeoff auditable. **Keep the coordinates too** — the hit locations from `count` and the vertices/regions from `polygons` and `length`. Step 6 drops them straight onto the drawings as markup.

#### Write the element ledger as you measure — `takeoff/elements.json`

The assemblies are the takeoff's *derivation* layer (primary → secondaries by formula). The ledger is its *evidence* layer: one machine-checkable file recording everything found, defined, and measured, so Step 5 can verify completeness mechanically instead of by recollection. It costs nearly nothing — `count`, `polygons` and `length` already return every coordinate; the discipline is writing them down in one place as you go, not reconstructing them at the end.

Record three kinds of entry:

- **Definitions** — every tag the legend or a schedule defines: `{tag, kind: "legend_def"|"schedule_def", sheet, schedule_qty (if the column is filled), stated_size_or_length (if any)}`.
- **Instances** — every counted hit: `{tag, kind: "instance", sheet, x, y, source: "plan"|"part_plan"|"riser"|"section"}`. Only `source: "plan"` instances are additive; the others exist for cross-checks.
- **Measurements** — every Linear/Area primary: `{item, kind: "length"|"area", value, units, sheet, scale, vertices_or_region, method, confidence}`.

The ledger is also what the Step 5 verification agent reads *blind* — it sees the geometry and definitions, not your narrative or your totals.

### Step 4 — Derive the secondaries

Apply each assembly from Step 2 to its measured primary. Concrete = area × thickness × waste; reinforcement = volume × ratio; cable = count × average run × waste; and so on. Round per the assembly. Every secondary inherits its primary's provenance plus the formula used. **Derive the FULL set for every primary — Step 7's Takeoff Breakdown must list them all.**

### Step 5 — Reconcile and sanity-check (do not skip)

A takeoff that hasn't been checked against the rest of the project is a draft, not a deliverable. Step 5 has three passes: a deterministic scope reconciliation over the element ledger (5a), an independent verification agent for every length and area (5b), and the quick judgement checks (5c). See the benchmarks in `references/derivation_library.md`.

#### 5a — Scope reconciliation over the element ledger (deterministic)

Run these checks over `takeoff/elements.json`. Each is mechanical — it either passes or it names the exact tag/line that fails. The most common takeoff failure is a *missing* quantity, and these are the rules that catch it:

1. **Legend coverage** — every `legend_def`/`schedule_def` tag either has plan instances in the ledger or an explicit "not present / not in scope" line in the BOQ. A defined-but-uncounted tag is the missed-wing error in its most catchable form.
2. **Schedule vs plan** — for every tag with a filled `schedule_qty`, plan instance count = schedule Qty. Divergence gets reconciled (wrong exclude box, part-plan leak, blank-schedule placeholder) or the line's confidence drops with the discrepancy stated in the notes.
3. **Cross-sheet duplicates** — every `part_plan`/`riser`/`section` instance of a tag must correspond to a plan instance, never add to the total. If a riser shows more of a fixture than the plan does, investigate before trusting either.
4. **Checklist coverage** — every category in the in-scope trade checklists maps to a BOQ line or a "not in scope" note. (This re-verifies Step 1's walk *after* measuring, when it's cheapest to fix.)
5. **Assembly completeness** — every primary in the ledger has its full set of secondaries derived (cross-check against Step 2's recorded assemblies).

Report the reconciliation result to the user as a short pass/fail table — it is the proof of completeness, and it goes in the workbook's notes.

#### 5b — Independent verification agent for lengths and areas (anchor-dimension check)

Counts get a three-way cross-check at Step 3; lengths and areas get this. The measurer should never be the only checker of its own geometry — you will "see" agreement with your own number (the same reason radiology double-reads scans). So spawn a **subagent that has not seen your results**, give it the sheets plus the ledger's `measurements` entries (geometry, scale, sheet — *not* your totals, narrative, or expectations), and have it:

1. **Derive the anchor dimensions independently** — building envelope length × width off the grid spacing or a stated overall dimension, and the footprint area from them. The anchors must come from a *different* source than the measurement being checked.
2. **Check every area against an anchor** — slab ≈ envelope L×W minus identified cut-outs; any internal area < the floor it sits on; paving/clearing extents consistent with the site boundary. Report the ratio.
3. **Check every linear against the dimension it spans** — a cable tray run along the building can't exceed envelope length × a routing factor (~1.2–1.5 with risers/offsets) without explanation; wall runs vs the perimeter; kerb vs the paved edge length; a pipe main vs the building diagonal. Report the ratio.
4. **Return a verdict per measurement** — `plausible` (ratio in band) or `out-of-band` with the suspected cause: wrong scale (everything off by a consistent factor — check the square/cube signature on areas/volumes), wrong polygon, clipped bbox, dashed-line undercount, or diagrammatic routing scaled as if real.

Treat every `out-of-band` as a **correction trigger**: re-measure, and only if the figure survives re-measurement does it ship — with the anomaly explained in the notes. Record the agent's ratios in the workbook (an "Anchor check" column on Tab 1) so the estimator sees each length/area was independently triangulated, not just produced.

#### 5c — Quick judgement checks

- **Scale check first** — the highest-leverage check. Confirm a known dimension (structural grid, an 820/920 mm door, a 2.4–2.6 m parking bay) measures correctly. A wrong scale throws areas by the square and volumes by the cube of the error.
- **Cross-document** — counts vs schedules; quantities vs anything stated in the spec/BOQ; the same item shown on plan + RCP + section is **one** item.
- **Internal consistency** — room areas sum to the floor area; ceiling ≈ floor less voids; concrete per m² of footprint and rebar per m³ land in the normal range.
- **Order of magnitude** — does the slab area roughly match the building footprint? Do fittings-per-m² look like a real building?

Anything outside the expected range isn't automatically wrong, but it must be **explained in the notes**, not smoothed over. If a check fails, go back and re-measure — don't paper over it.

### Step 6 — Mark up the drawings (and vision-check the markup)

A takeoff shouldn't live only in a spreadsheet — it should be visible on the drawing, the way takeoff software shades what it has measured. The marked PDF is the **audit artefact**: it sits on the real vector drawing at true coordinates, prints, and goes back to a client as the checked sheet.

**Mark up every sheet you measured — not just one.** A common and trust-destroying miss is to overlay one sheet (say the structural block) and leave the sheet the user is actually looking at (say the civil site plan) bare. Walk the list of worked sheets at the end and confirm each one that contributed a quantity carries its markup. If a sheet contributed quantities and has no overlay, say why in the workbook (e.g. schedule-only count with no plan coordinates).

**There are two legitimate kinds of markup — keep them straight:**

- **Per-item marks for COUNTS** — one translucent box per counted item, driven by the count's own captured locations. The way to guarantee the markup shows only what's in the QTO (and never the schedule/legend definitions) is to let `count --markup-out` build the spec:
  ```bash
  python scripts/measure.py count "sheets/E-101.pdf" --tags L1 L2 GPO \
      --exclude-bbox 1500 980 1850 1180 \
      --markup-out ./takeoff/markup_E101.json --markup-page 3
  ```
  This writes one **translucent box (~35% opacity)** per counted hit, a distinct colour per tag, and prints a `legend` (tag → colour → count) to drop into the BOQ.
- **Shaded-extent overlays for AREAS / LINEARS** — a translucent polygon over a measured **area** (a slab/surface-bed footprint, a paving zone, the site-clearing / earthworks platform) or a `cloud`/`polygon`/`line` along a measured run. **This is required, not optional, for area quantities** — the shaded extent *is* the measurement, and it is exactly how takeoff software presents area work. Build the spec from the vertices you captured.

> **The forbidden thing is different: a guessed "zone" box standing in for per-item COUNT markup.** A box eyeballed around "where I counted" proves nothing and visibly won't line up. That is banned. A **measured** area boundary (corner-checked against the drawing) is the opposite — it is the deliverable. Don't confuse the two: mark measured area extents; never fake a count with a decorative box.

**One merged PDF set, so the user has a single file to flip through.** Apply the spec(s):

```bash
python scripts/measure.py markup merged.pdf --spec markup_E101.json --out drawings_marked.pdf
```

#### Bluebeam-safe output (REQUIRED for the final marked PDF)

Estimators open the marked drawings in **Bluebeam Revu**, and a PyMuPDF-saved PDF **will not open in Bluebeam** — PyMuPDF rewrites the whole document into a structure Bluebeam's parser rejects (Chrome/Adobe tolerate it, which masks the problem). The fix is to **overlay the markup onto the *original* uploaded PDF with `pikepdf`** (which preserves the original publisher's structure) and save **without object streams**:

```python
import pikepdf, json
from pikepdf import Name, Dictionary, Array
def hexrgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
pdf = pikepdf.open("ORIGINAL_uploaded.pdf")          # NOT a PyMuPDF re-save
for page_idx, spec_path in marked_pages.items():     # 0-based page index -> its markup spec
    pg = pdf.pages[page_idx]; res = pg.obj["/Resources"]
    H = float(pg.obj["/MediaBox"][3]) - float(pg.obj["/MediaBox"][1])   # read per page — do NOT hardcode
    egs = res.get("/ExtGState") or pdf.make_indirect(Dictionary()); res["/ExtGState"]=egs
    ops = json.load(open(spec_path))["ops"]; body=["q"]
    for i,op in enumerate(ops):
        x0,y0,x1,y1 = op["rect"]; r,g,b = hexrgb(op.get("fill","#1E88E5"))
        gname=f"/GSmk{i}"; egs[Name(gname)]=Dictionary({"/ca":op.get("opacity",0.35),"/CA":1.0,"/BM":Name("/Normal")})
        # PyMuPDF rect (y-down, top-left)  ->  PDF content (y-up, bottom-left): flip Y by page height
        body += [f"{gname} gs", f"{r} {g} {b} rg", f"{x0:.2f} {H-y1:.2f} {x1-x0:.2f} {y1-y0:.2f} re f"]
    body.append("Q")
    st = pdf.make_stream(("\n".join(body)+"\n").encode())
    c = pg.obj.get("/Contents")
    pg.obj["/Contents"] = Array([c, st]) if not isinstance(c, Array) else (c.append(st) or c)
pdf.save("drawings_marked.pdf", object_stream_mode=pikepdf.ObjectStreamMode.disable)
```

For a **polygon** (area/clearing/paving extent) overlay, emit a path instead of a rectangle: `x0 H-y0 m`, then `x H-y l` for each vertex, then `f` (fill) and a stroked pass for the outline. Key points: **flip Y** (`y_pdf = MediaBox_height - y1`); add a per-opacity `/ExtGState`; save with `ObjectStreamMode.disable`; and **read `H` from each page's own MediaBox** — do not hardcode it (it differs per set).

#### Vision cross-check — the loop that *corrects* the takeoff, not just signs it off

Render each marked sheet once and read it against the original the way a reviewer would. Do it in a single structured pass per sheet (full sheet, then zoom a dense zone only if needed):

```bash
python scripts/measure.py render ./outputs/drawings_marked.pdf --page N --dpi 100 --out check_pN.png
```

Then treat any discrepancy as a **correction**, not just a flag:

- **Highlights sparse against obviously-tagged items** → the text layer is incomplete (outlined/exploded CAD text, or a raster sheet). Switch that item to a deliberate **vision count**, mark those locations, and flag **Low**. The number that ships is the corrected one.
- **A definition still highlighted** (a schedule/legend cell lit up) → widen the `--exclude-bbox`, re-run `count --markup-out`, re-render.
- **Marks floating off-target / wrong scale** → fix the scale or coordinates and re-measure; a systematic offset usually means the wrong scale or the wrong sheet.
- **Areas / clearing / paving / slab extents — corner-check, do not eyeball.** A "looks-about-right" glance is NOT a check and has shipped completely wrong overlays. For every area/extent overlay, verify **each corner of the shaded polygon lands on the feature it bounds** (slab corners on the grid bubbles; the clearing polygon following the development edge) by reading the rendered marked page corner-by-corner. If any corner/edge is off, the coordinate transform (page `Rotate`, content CTM, or y-axis convention) is mis-set — **re-derive and re-render**, don't sign off. The area *number* can be right while the *shape* is on the wrong half; both must be correct before delivery.

Iterate until the marked sheet and the QTO agree, then report briefly.

### Step 7 — Output the deliverables

Produce a professional Excel workbook. Read the `xlsx` skill's SKILL.md for formatting practice, build with openpyxl, then run its `recalc.py` so formulas evaluate. **Sanitise text cells:** any free-text Notes/Basis cell that begins with `=` is parsed as a formula and errors — strip or prefix a leading `=`.

Use the **estimator's tab structure** (this is how a QS wants it, and it applies to every trade). **Tab order matters: Tab 1 = Primary Quantities, Tab 2 = the grouped Takeoff Breakdown.** Any flat/cover/index tab goes *after* those two.

- **Tab 1 — "Primary Quantities"**: the things measured directly (counts, measured areas/lengths) **and footprint/perimeter-based estimates** — nothing derived. This is the short, high-trust list, each line carrying its method and confidence, plus an **"Anchor check"** column for Linear/Area lines carrying the Step-5b verdict and ratio (e.g. "0.97 × envelope L×W — plausible"). Include a short reconciliation-summary note (the Step-5a pass/fail result) on this tab or the notes tab.
- **Tab 2 — "Takeoff Breakdown"**: each primary (a bold/shaded group header) immediately followed by its derived secondaries, indented beneath, every derived row an Excel formula referencing the Tab-1 measured cell. **Must be COMPLETE** — every primary gets its group, every secondary in its assembly listed; if you deliberately ran a partial takeoff, say so in a note row rather than silently truncating.
- **Tab 3 — "Material Summary"**: roll-up by material via `SUMIFS` over a Tab-2 "Material key" column.
- **Tab 4 — "Drawing Index"** (multi-sheet sets): sheet, title, type, scale, what was taken off it.

**Multiple projects in one workbook (sampler sets):** give each trade/project its own section header and never sum across them; add an Index & Notes tab stating each PDF is a different project.

Formatting: bold dark header (RGB 44,62,80), frozen panes, auto-filter; trade colour-coding; confidence colour-coding (High green / Medium amber / Low red); thin borders; sensible number formats.

Save the workbook to the user's output folder and present it **together with the marked-up drawing PDF(s)** from Step 6, leading with the BOQ. The deliverable is the pair: the bill of quantities, and the drawings showing where every number came from.

---

## Honesty about confidence

This skill does a full AI takeoff, but it is candid about which numbers are solid:

- **High** — text-layer tag counts verified against a schedule; areas from clean closed polygons at a confirmed scale; annotated dimensions read directly; lengths stated in a schedule.
- **Medium** — computed polyline lengths; areas needing manual cut-out subtraction; counts where a few items lacked tags; circuit counts read by eye from a clear SLD table.
- **Low** — anything counted from symbols by vision; measurements at an inferred (not stated) scale; depths from defaults; pipe lengths on a diagrammatic / greyscale / dashed plan; and **footprint/perimeter-based estimates** for quantities that are present on the drawing but impractical to measure precisely (paving areas, kerb runs, bulk earthworks).

Say what's Low and why.

**Extract every relevant quantity — estimate rather than leave a blank, but never fabricate one that isn't there.** Two cases that look similar but are opposite:

- **Present but hard to measure** (the element IS on the drawing — paving zones, kerb runs, clearing area, cut/fill) → **give a footprint/perimeter-based Class-5 estimate**, flagged **Low**, with the basis written into the notes ("≈ platform 12,400 m² − buildings", "perimeter of paved edges"). Do **not** leave it blank or "not derivable". A flagged estimate is information; a blank is a hole the estimator will miss. This is what "extract every quantity relevant to construction" means.
- **Genuinely absent from the document** (a "for tender" schedule with a blank Qty column, an SLD with "X" placeholder points) → report it as **not-derivable, with the reason**, and say what IS there. **Never manufacture a number to fill the column.**

The test: can I tie the estimate to something measured on this drawing (a footprint, a perimeter, a count × a rate)? If yes, estimate and flag it. If the figure would be pulled from thin air, it's absent — say so.

## Common pitfalls

- **Skipping drawings-analyser.** Run it first to break up and classify the set (Step 0).
- **Measuring before agreeing what to measure.** Recommend the quantity list and get sign-off first (Step 1).
- **Skipping the element ledger.** Without `elements.json` the Step-5a reconciliation can't run, and completeness goes back to being a feeling. Write definitions, instances, and measurements down as you go (Step 3) — never reconstruct them from memory at the end.
- **Signing off your own lengths and areas.** Counts get the three-way cross-check; every Linear/Area gets the independent anchor-dimension check by a blind subagent (Step 5b). A measurer reviewing its own geometry will see agreement that isn't there.
- **Under-extracting — measuring the obvious and missing a whole category.** This is the most common takeoff failure and the reason the trade checklists exist. In Step 1, walk the relevant `references/trade_checklists/*.md` category by category; record absent categories as a "not in scope" note rather than skipping them, and add anything the drawings carry that the list doesn't. A takeoff that lists fixtures but forgets the drainage, or slabs but forgets the formwork and reo, is incomplete even if every number it *does* have is right.
- **Counting symbols instead of text.** Count the text tags off the vector layer; reserve vision for verification and genuinely untagged items.
- **Counting legend/schedule entries as instances.** Exclude those regions in `count`.
- **Double-counting across views.** The same item on plan, section, and detail is one item.
- **Measuring volume directly.** It's always area × depth; read the depth, don't measure the solid.
- **Forgetting the earthworks on a civil/site sheet.** Site clearing & grubbing, topsoil strip, and bulk cut/fill are usually the biggest-value civil quantities and have no tag — always take them off (clearing/topsoil are measurable; cut/fill is a contour-vs-FFL estimate). A site takeoff that lists only pipes and manholes is incomplete.
- **Leaving a blank instead of an estimate.** If an element is on the drawing but hard to measure precisely, give a footprint/perimeter-based estimate flagged Low — don't drop it. (But never fabricate a quantity the document doesn't contain.)
- **Trusting nominal scale against the geometry's coordinate space.** A CAD/DXF-exported PDF can carry a content-stream transform (CTM) and/or page `Rotate`, so `get_drawings()` coordinates are NOT the nominal page-point space and the title-block "1:100" can be wrong relative to them. **Always calibrate scale against a printed dimension or an even grid bay before trusting any area/length** — e.g. measure the overall building line and check it against the stated overall dimension (a real run confirmed 1:100 only because a measured 31.24 m matched a printed 31.285 m; the raw page-point assumption was off). A wrong scale throws areas by the square and volumes by the cube.
- **Marking up only one sheet.** Overlay every sheet that contributed a quantity — especially the civil/site sheet the user is looking at — not just the first one you measured.
- **Assuming scale or depth silently.** If it's not on the drawing, assume explicitly and write it in the notes.
- **Reporting an area you haven't eyeballed.** Always validate polygons against the render, and corner-check every area/extent overlay.
- **Solid markup.** Use ~30% translucent fills so the item shows through.
- **Hyphen-split tags.** Tags like WC-1 / FD-2 are hyphenated; pass them exactly.
- **Excluding with the wrong coordinate space** on a rotated sheet (use `--exclude-bbox-native`).
- **Scaling diagrammatic services pipe** — if the note says diagrammatic/schematic/NTS, derive runs instead of scaling.
- **Slab boundary from bubble centroids** — build the rectangle from the gridLINE positions, not the bubble circles.
- **Delivering a PyMuPDF-saved marked PDF** — it won't open in Bluebeam; overlay on the original with pikepdf.
- **A leading `=` in a text/Notes cell** — Excel treats it as a formula and errors; sanitise it.
- **Signing off an area overlay without a corner-check** — a wrong page-rotation/CTM/y-flip can put a *correct* area on the wrong part of the sheet.
- **Assuming a folder of discipline PDFs is one building** — it's often a sampler of separate projects; treat each per-trade, don't add across trades.
- **Leaving markup only live in Bluebeam** — always save the marked PDF as a file.
- **Putting a flat/cover tab before Primary Quantities** — Tab 1 = Primary Quantities, Tab 2 = the grouped Takeoff Breakdown; everything else after.
- **A truncated Takeoff Breakdown** — list every secondary for every primary (the whole assembly); if you deliberately ran a partial takeoff, say so in a note row rather than silently dropping rows.
- **Forgetting earthworks / leaving a blank on a civil sheet** — always take off clearing & grubbing, topsoil, and a contour-vs-FFL cut/fill estimate; give a flagged footprint/perimeter estimate for anything present-but-hard-to-measure, but never fabricate a quantity the document doesn't contain.
- **Trusting nominal scale against the geometry's coordinate space** — a CAD-export PDF can carry a CTM/Rotate so `get_drawings()` coordinates aren't page points and the title-block scale can be wrong; calibrate against a printed dimension or even grid bay first.
- **Marking up only one sheet** — overlay every sheet that produced a quantity, especially the civil/site sheet, not just the first one measured.
- **Shipping a guessed "zone" rectangle as count markup** — mark each counted item at its own location, or deliver no count overlay. (A *measured* area extent is the opposite — that one you must mark and corner-check.)
