---
name: drawings-analyser
description: Turn a construction drawing set (PDF or folder of PDFs) into a queryable structured database plus per-sheet markdowns, a symbol library, a cross-reference graph, and a concept wiki of the notes/specs. Builds the building's components as instances with coordinates (IFC-style), tags every fact with a reliability score, validates its own sources, and flags conflicts/RFIs. Then answers questions by querying the database (counts, locations, relationships) and the source PDFs on demand (areas, schedules, dimensions) — far cheaper than re-reading the PDF each time. Trigger when drawings are shared and the user says "analyse/review these drawings", "break down this drawing set", "build a database from these drawings", "extract the symbols", "find coordination issues", "how many X", "where are the X", or asks Claude to understand, query, or get across a drawing set. Not for full-set takeoffs (use construction-takeoff) or project onboarding (use project-indexer).
---

# Drawings Analyser

Turns a construction drawing set into durable, structured artefacts that any downstream session reads cheaply — without re-parsing the PDFs — and into a **queryable structured database** of the building's components. Then answers precise follow-up questions by querying those artefacts.

## What this produces (two complementary layers)
1. **The prose layer** — per-sheet markdowns, symbol library, cross-reference graph, coordination issues. Exhaustive, contextual, self-correcting. (The original analyser output.)
2. **The structured layer** — a normalized SQLite database: the schedules (type catalogue), the **instances** of each component with their coordinates (the IFC-style model), the relationships stated in text, the notes — every row carrying a **reliability** score, plus qualitative **context notes** from a vision pass. This is what answers "how many F10 footings / where are they / what runs the full length of the building / which circuit feeds what."

Keep BOTH. They were A/B-validated against each other and against raw images: structure beats images on cost (~20×) and hallucination resistance; the prose layer is self-correcting and caught DB extraction errors; the database answers counts/locations/relationships the prose can't; reliability + context notes lifted answer accuracy 9.5→14/16 and calibration 9→15/16 with zero added hallucination.

## The eight learnings this skill is built on (evidence, not assertion)
Measured across structural + plumbing + electrical sets, 80+ blind-judged questions:
1. **Structure beats images.** Never make the model count symbols or trace connections off a render — extract to structure, query that. (Vision is ~40–55% on symbol counting; the vector text layer is ~100% on text.)
2. **Hybrid > either alone.** Keep prose (contextual, self-correcting) AND the database (exact, queryable).
3. **Validate provenance at build time.** The DB's one failure mode is *silent extraction errors* — a value attributed to the wrong sheet. `validate_provenance.py` relocates mis-sourced rows. Took a test DB 96.4%→100%, 0 hallucinations. Always run it.
4. **Entity-completeness.** Every component gets an entity/instance row even with null attributes; aggregate counts over the entity table, never the relationship table — and store `count` as an explicit integer, never inline notation like "F10 x2" (ambiguity caused a real miscount).
5. **The vector/raster fork decides feasibility.** A vector PDF with a real text layer → near-lossless structured extraction, no ML. A scanned OR outlined-text sheet (no text layer) → extraction gets nothing; it needs vision. `process_drawing.py` reports text density per sheet; **for sheets with no text layer, flag a placeholder — never fabricate.**
6. **Schedule = catalogue; tags = instances. Capture BOTH.** A schedule gives one row per TYPE; every tag on a plan carries an (x,y) in the text layer, so also extract one row per physical INSTANCE with coordinates. This is the IFC model and it answers counts/locations. Validated: coordinate-filtered instance counts matched a verified takeoff **14/14 marks**.
8. **Build a concept wiki for the notes/requirements (not just per-sheet).** The database holds the physical things; the **concept wiki** holds the rules/specs about them, regrouped BY CONCEPT across all sheets ([[wikilinks]] + source citations + a conflict/lint register) — Karpathy's LLM-wiki pattern. Reconcile-once at ingest beats gather-and-reconcile-under-pressure at query: blind A/B (same source, by-sheet vs by-concept) — concept wiki scored completeness 6/6 vs 5/6, correctness 6/6 vs 4.5/6, caught conflicts the per-sheet pass garbled, ~40% cheaper. See `references/concept_wiki.md`.
7. **Reliability score + qualitative context notes — add both.** Tag every fact HIGH (text) / MEDIUM (vision) / LOW (scaled) so the model hedges scaled values instead of stating them as fact; attach free-text `context_notes` from a vision gestalt pass ("the warehouse slab is the main concrete footprint, spanning ~the full grid"; "the west-wall waste main runs ~the full building length"). Use vision for gestalt, never for counts; pair each note with `what_to_verify`.

## Two modes
1. **Index mode** — runs once per set. Splits, classifies, builds the symbol library, writes per-sheet markdowns, builds the cross-reference graph, surfaces coordination issues, AND builds the structured database (schedules → instances with coordinates → relationships → notes → context notes), then validates provenance.
2. **Query mode** — runs on each follow-up question. For counts/locations/relationships/aggregations, query the **database** (SQL — exact, cheap). For geometry not in the DB (polygon areas, annotated dimensions, region text), query the source PDF on demand via `query_drawing.py`. Fall back to the prose layer for context and to verify a surprising DB row.

It does drawings only. It is not a project indexer; it does not read specs, contracts, or correspondence.

## The core principle: AI does judgement, scripts do plumbing
Scripts do the cheap deterministic work — splitting PDFs, extracting vector text+geometry, rendering PNGs, cropping symbols, pulling tag instances with coordinates, loading the DB, validating provenance, computing polygon areas. Claude does the judgement — classifying sheets, extracting the symbol library, designing the per-discipline schema, populating instances/relationships/reliability, writing the per-sheet analysis, detecting the cross-reference convention, the coordination pass, the vision context notes, and routing query-time questions. No regex for sheet types or cross-reference conventions — those vary by office and break pattern-matching.

## Why query-time geometry extraction works
Vector data without semantic context is noise — an A1 sheet has 5,000–50,000 primitives. So we don't pre-extract all geometry. Index time captures *what's on each sheet* and *what each region can answer precisely* (markdown) and the *structured facts + instances* (DB). Query time, the user's question supplies the semantic context that bbox-prediction can't, so targeted extraction is more accurate than bulk dumping.

## Inputs
A single drawing PDF (one or many sheets) or a folder of drawing PDFs. Output goes in a sibling `drawings_analysis/` folder (or an existing `0. AI Context/`-style folder if the project uses one).

## Outputs
All in the output folder:
- **`drawings_split/`** — per sheet: single-sheet PDF, 2576px PNG render, vector extraction JSON (text+bbox, geometry, scale). Durable; read by query mode, the DB build, and `construction-takeoff`.
- **`sheet_index.json`**, **`sheet_classification.json`** — flat sheet list; AI type+discipline classification.
- **`symbol_library.json`** + **`symbol_crops/`** — every legend symbol with description, discipline, PNG crop.
- **`drawings/`** — one `.md` per sheet (type-aware, exhaustive, perspective-tilted), each with `Answerable from this drawing` + `Coordinate hints` sections.
- **`drawings.md`** — drawing register + index.
- **`cross_references.json`**, **`coordination_issues.md`** — cross-ref graph; coordination findings.
- **`db/structured.json`**, **`db/project.sqlite`**, **`db/SCHEMA.md`** — the structured database (schedules, instances, relationships, notes, context_notes; every fact with `reliability`). **`db/provenance_report.json`** — provenance validation result.
- **`concept_wiki/`** — the notes/requirements regrouped by concept ([[wikilinked]], source-cited) + `index.md` with the conflict/RFI register.

## Workflow — Index mode

### Step 1 — Confirm the analysis perspective (mandatory, ask the user)
Drawing analysis is tuned to a trade perspective (GC, electrical, hydraulic, mechanical, structural, civil, fire, comms). Ask upfront; don't infer silently. All sheets get exhaustive analysis regardless — the perspective just tilts the lens. Record it; it goes atop `drawings.md` and into every per-sheet prompt.

### Step 2 — Split, render, vector-extract every drawing PDF
```bash
python scripts/process_drawing.py "<drawing_path>" -o "<output>/drawings_split/<source_stem>"
python scripts/build_sheet_index.py "<output>/drawings_split" -o "<output>/sheet_index.json"
```
Per page: single-sheet PDF, 2576px PNG, vector JSON (every text block + bbox, title-block candidates, detected scale, lines/rects/curves, vector count). **Vector extraction before vision** — pdfplumber gives 100%-accurate text; vision then only does geometry/symbols. **Note the per-sheet text density: sheets with ~0 extractable text are raster/outlined → vision-only; flag them now** (learning #5). Show the user the sheet count + source breakdown.
> **Scale & title-block gotchas** (the extractor now handles these, but verify): scale detection parses imperial (`1/8"=1'-0"`) and metric, **rejects a bare `1:N` next to FALL/SLOPE/GRADE/BANK** (it's a slope, not a scale — civil sheets are full of them), and returns `all_factors` for multi-scale sheets — a bare ratio is only MEDIUM confidence. Title-block text is often **rotated 90°** (tall/narrow bboxes), so `title_block_candidates`/sheet-ID may come back empty; read the sheet ID from the render if so. If `build_sheet_index.py` reports "0 sheets", you pointed it at the per-source subfolder — give it the parent `drawings_split/`.

### Step 3 — Classify every sheet by type + discipline (AI, not regex)
For each sheet send Claude the PNG + vector JSON; classify into one drawing type (`general_arrangement`, `section_view`, `elevation`, `detail`, `schedule_sheet`, `general_notes`, `legend`, `single_line_diagram`, `cover_sheet`, `coordination_drawing`, `other`) + discipline + confidence + justification. Taxonomy/prompt in `references/drawing_types.md`; schema in `references/output_schemas.md`. Aggregate to `sheet_classification.json`; show counts; let the user confirm/override. Read the sheet, not its number prefix.

### Step 4 — Build the symbol library
For every `legend` sheet, extract each defined symbol (ID, verbatim description, discipline, bbox), crop it:
```bash
python scripts/crop_region.py "<legend_pdf>" --bbox <x0> <y0> <x1> <y1> -o "<output>/symbol_crops/<id>.png" --long-edge-px 512
```
Aggregate to `symbol_library.json`. Pass the relevant-discipline subset into every per-sheet prompt (Step 5). Legend symbols are *definitions, not instances* — the legend sheet's markdown links to the library; it is not an occurrence of every symbol.

### Step 5 — Per-sheet analysis (type-aware)
Generate one `.md` per sheet using the type-specific template (`references/drawing_types.md`). Inputs: PNG, vector JSON, filtered symbol library, perspective, type template. Markdown-KV for structured fields, prose for visual interpretation. Every per-sheet markdown MUST include `## Answerable from this drawing` (precisely / by-inspection / not-answerable buckets) and `## Coordinate hints for query-time extraction` (bbox for title block, drawing area, each schedule/zone). **Do not count in Step 5** — describe; the DB (Step 5b) and query mode handle quantities.

### Step 5b — Instance extraction (the coordinate-grounded IFC layer) — NEW
For text-bearing PLAN sheets, extract every tagged component as an INSTANCE with its coordinate. The tag's (x,y) is already in the vector text layer — keep it.
```bash
python scripts/extract_instances.py "<sheet.json>" --sheet <ID> --pattern "<tag regex>" \
  --exclude <schedule_bbox> --exclude <legend_bbox> --exclude <title_bbox>
```
The `--exclude` boxes (take them from the sheet's `Coordinate hints`) drop the schedule/legend/diagram copies — **a tag inside the schedule is a definition, not a placed instance; this filter is what makes counts correct** (validated 14/14 vs a verified takeoff). Associate each instance to the nearest grid/room by comparing its (x,y) to grid-label coordinates. **Raster/outlined plans have no tag coordinates → instances need vision; record a placeholder, don't fabricate.**
> **Run instances ONLY on plan-classified sheets** (`general_arrangement`/plan), NEVER on `schedule_sheet`/`general_notes` — on a US/Canadian set the schedule is its own sheet, and running there returns phantom counts (every schedule row = a fake instance). Pass `--space-tolerant` (CAD letter-spaces tags: "SEW M H 1"). Where one sheet shows a demolition + renovation view of the same area, pass `--exclude-pattern "DEMOLITION|EXISTING"` or reconcile — the same unit is tagged twice. Reconcile the instance count against the schedule QTY column where one exists.

### Step 5c — Vision context notes (gestalt, not counting) — NEW
Run ONE qualitative vision pass over the key plan sheets to capture understanding the schedule can't: extents, runs, significance, zoning — e.g. "the main concrete footprint is the warehouse slab, spanning ~the full grid"; "the west-wall waste main runs ~the full building length"; "bracing concentrates at the building ends". Each note: `{note, reliability: MEDIUM, basis, what_to_verify}`. Use vision for gestalt ONLY — never invent counts or precise dimensions.

### Step 5d — Build the structured database — NEW
Design the per-discipline schema (`references/schema_guidance.md` + the IFC-shaped per-element model in `references/instance_model_template.md`) and write `db/structured.json`. Always include: `sheets`; the discipline entity table(s) (footings/fixtures/members/luminaires…); a `schedules` catalogue (type → size/material/spec); the `instances` table from Step 5b (tag, type, x, y, sheet, grid); `relationships` (connective facts STATED in text — `feeds`, `runs_to`, `contains`); `notes`; `context_notes` (Step 5c); and `placeholders` (what needs vision / non-tabulated runs). **Every fact carries `reliability` (HIGH text / MEDIUM vision / LOW scaled). Store `count` as an explicit integer.** Then:
```bash
python scripts/build_db.py "<output>/db/structured.json" -o "<output>/db/project.sqlite"
```
Write `db/SCHEMA.md` (tables + 3–4 example queries, incl. one count/aggregation and one relationship query).

### Step 5e — Validate provenance (mandatory) — NEW
```bash
python scripts/validate_provenance.py "<output>/db/structured.json" \
  --textdir "<output>/drawings_split/<stem>" --fields fields.json --apply -o "<output>/db/provenance_report.json"
```
`fields.json` maps `{table:[id_field, value_field, source_field]}` (source = the sheet id matching the per-sheet text files). Relocates rows whose tokens don't appear on their cited sheet; rebuild the sqlite from `structured_validated.json`. Report corrections to the user.

### Step 5f — Build the concept wiki (the notes/requirements layer) — NEW
Regroup the notes/specs/requirements BY CONCEPT (not by sheet) into `concept_wiki/` — one markdown page per concept (concrete-grades, reinforcement-and-mesh, cover, slabs, footings, joints; or for services: systems, materials, fixings, fire-rating, testing…), each fact citing its source sheet, cross-linked with [[wikilinks]]. The `concept_wiki/index.md` carries a standing **conflict / RFI register** (contradictions across sheets, stale notes, gaps). This is the Karpathy LLM-wiki ingest step, and it's where a design-review consistency check lives. Don't invent; the wiki summarises, so keep the per-sheet prose + raw text for granular fallback. See `references/concept_wiki.md`. (LLM operation — no script.)

### Step 6 — Cross-reference graph
Read every per-sheet "Cross-references on this sheet" section; have Claude detect the set's cross-ref convention (don't regex) and build `cross_references.json` (source→target, resolved true/false). Schema in `references/output_schemas.md`.

### Step 7 — Coordination pass
Read `drawings.md` (stub), `cross_references.json`, `symbol_library.json`; surface: unresolved cross-refs; symbols used but undefined; register inconsistencies; trade coordination *contradictions* across views (not repetitions — the same item on plan+section+detail is one item). Output `coordination_issues.md`, grouped, specific, no invented issues.

### Step 8 — Combined drawings.md index
Index (not duplicate): header (perspective + date); **a high-level "what's in this set" summary** (the building in one paragraph, disciplines present, key schedules, raster/no-text sheets flagged); cross-ref summary; drawing register table (Sheet ID, Title, Type, Discipline, Rev, link); discipline-by-discipline one-liners; a "Querying this drawing set" section pointing the next session at: **the database first** (`db/project.sqlite` + `SCHEMA.md` for counts/locations/relationships), then per-sheet `Answerable`/`Coordinate hints` + `query_drawing.py` for geometry. Keep under ~500 lines.
> **Where the summary lives (one home per fact):** the drawing-set summary goes HERE in `drawings.md`; the database *structure* goes in `db/SCHEMA.md`. If the project uses `project-indexer` (a `CLAUDE.md`/`project.md` exists), add only a ONE-LINE pointer there ("Drawings analysed → `drawings_analysis/drawings.md` + `db/project.sqlite`") — don't duplicate the summary up into CLAUDE.md.

### Step 9 — Final summary
Output folder; sheet count; type/discipline breakdown; symbol library size; cross-ref resolved/unresolved; coordination issues by category; **DB table + row counts, total instances, provenance corrections, context-note count, and any raster/no-text sheets flagged as vision-only placeholders**; perspective used; parse failures; reminder that follow-up questions are answered via query mode (DB + on-demand geometry, no re-analysis).

## Workflow — Query mode
After analysis, on a precise follow-up question. Do not re-run index mode.

**Q1 — Route.** Counts / "how many" / locations / "where are" / "which on grid X" / relationships / aggregations → the **database** (`db/project.sqlite`). Geometry (areas, annotated dimensions, region text not in the DB) → the right source PDF via `query_drawing.py`. Use `drawings.md` + per-sheet `Answerable from this drawing` to find the sheet; `cross_references.json` for relationships.

**Q2 — Database query (preferred where it applies).** Read `db/SCHEMA.md`, write SQL. Counts come from the `instances` table (e.g. `SELECT count(*) FROM instances WHERE tag='F10'` → 2; or `SELECT tag,grid FROM instances WHERE tag='F10'` → w14/wD, w15/wD). Aggregations/relationships are exact. **Report the row's `reliability`** and hedge LOW/scaled values. If the fact is a `placeholder` (needs vision / non-tabulated run), say so and route to geometry/visual.

**Q3 — Geometry query.** Read the per-sheet `Coordinate hints`; pick the bbox; call `query_drawing.py`:

| Question type | Sub-command | Notes |
|---|---|---|
| Area of slab/room/zone | `polygons` | `--scale` from title block; largest polygon usually the answer |
| Schedule contents | `tables` | structured rows; bbox if multiple tables |
| Text in a region | `text` | every text block + bbox |
| Annotated dimensions | `dimensions` | verify against visual |
| Page size / scale check | `page-info` | cheap sanity check |

```bash
python scripts/query_drawing.py polygons "drawings_split/<...>/<sheet>.pdf" --bbox 80 50 1620 720 --scale 1:100
python scripts/query_drawing.py tables   "drawings_split/<...>/<sheet>.pdf" --bbox 1180 730 1820 1100
```

**Q4 — Validate against the visual.** If a polygon area looks wrong, widen the bbox or filter polygons; load the PNG and check vertices line up. Don't return an unchecked number.

**Q5 — Answer with provenance + reliability.** Cite drawing, method, region, and the reliability/source. E.g. *"2 F10 footings (3200×3200×1200), at grids w14/wD and w15/wD. Source: db/instances (text-layer instances, HIGH — count validated against takeoff). "* or *"Warehouse slab ≈3,656 m² (S-101 polygon via query_drawing.py, scale 1:100) — MEDIUM: scaled, verify."*

**Q6 — Don't fabricate scale.** No detected scale and none on the title block → stop and ask before any area/length query.

## Composing with other skills
- Quantity takeoffs → `construction-takeoff` (reads the same `drawings_split/` single-sheet PDFs; the instance counts here can seed/validate it).
- Project onboarding → `project-indexer` / `pbs-project-indexer` (same `drawings_split/` format; produce CLAUDE.md/project.md for non-drawing docs).

## Important constraints
- **No quantity guessing in vision passes.** Counts come from the `instances` table (text-layer tags), not from looking at the render. Describe in prose; count in the DB.
- **No pattern matching for sheet types or cross-references.** AI judgement; conventions vary.
- **Split to PDF first, analyse second.** Durable single-sheet PDFs let a partial run resume.
- **Render at 2576px long edge.** Matches the model's native resolution.
- **Vector extraction before vision.** 100%-accurate text first; vision for geometry/symbols only.
- **Ask for perspective in Step 1.** Don't infer silently.
- **All sheets analysed exhaustively** regardless of perspective.
- **Every DB fact carries reliability; store `count` as an integer; aggregate over the entity/instance table.**
- **Run provenance validation (Step 5e) on every build.**
- **Vector/raster fork:** no-text sheets → vision-only; flag placeholders, never fabricate instances/connectivity for them. Non-tabulated runs (traced pipes/cables) → placeholder unless the from/to is stated in a schedule/single-line.
- **Don't invent information.** Note gaps briefly.
- **Re-runs incremental:** only reprocess source PDFs newer than their `manifest.json`; always re-run cross-references, coordination, and provenance validation after any change.
- **Always cite source + reliability on answers.**

## Optional — prove it on a new set
To validate that the structured context beats raw images on a given set, run the blind A/B/C protocol in `references/eval_protocol.md` (sub-agents answer from images vs prose vs DB; a blind judge grades). Recommended on a new discipline or when the user wants evidence.

## Reference files
- `references/drawing_types.md` — type taxonomy + classification + per-type analysis prompts + the universal `Answerable`/`Coordinate hints` guidance. Read before Steps 3 and 5.
- `references/output_schemas.md` — schemas for sheet_index, sheet_classification, symbol_library, cross_references, coordination_issues.
- `references/schema_guidance.md` — designing the per-discipline DB: universal tables, entity tables, the `reliability` field, the `context_notes` table, entity-completeness + explicit-`count` rules. Read before Step 5d.
- `references/instance_model_template.md` — the IFC-shaped per-element template (object + placement/coordinates + properties + from/to topology) and multi-view fusion (schedule→size, section→depth, plan→placement). Read before Steps 5b and 5d.
- `references/eval_protocol.md` — the blind A/B/C evaluation.
- `references/concept_wiki.md` — the notes/requirements layer (Karpathy LLM-wiki: ingest / query / lint by concept). Read before Step 5f.

## Scripts
- `scripts/process_drawing.py` — split + 2576px render + vector extraction (text+geometry+scale) per sheet.
- `scripts/build_sheet_index.py` — aggregate per-sheet artefacts into `sheet_index.json`.
- `scripts/crop_region.py` — crop a bbox to PNG (symbol crops).
- `scripts/extract_instances.py` — **NEW.** Tag → instance with coordinates; schedule-region exclude; the IFC placement layer.
- `scripts/build_db.py` — **NEW.** Load `structured.json` → `project.sqlite` (one table per key).
- `scripts/validate_provenance.py` — **NEW.** Check every DB row's source sheet against that sheet's text; relocate mis-sourced rows. The accuracy fix.
- `scripts/query_drawing.py` — query-time geometry: `polygons`, `text`, `dimensions`, `tables`, `page-info`. On-demand only.

All judgement is Claude's; scripts handle the cheap mechanical work so token spend goes where a model is actually needed.
