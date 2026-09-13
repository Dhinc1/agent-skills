# land-plan-estimator

A Claude skill for reading and estimating from civil land-development plan sets (PDF)
without dumping the raw PDF into context. Preprocesses a plan set into per-sheet text +
raster images (imperial units throughout), optionally builds a structured/queryable
database with provenance validation, then estimates against a pay-item catalog with
an element ledger, deterministic reconciliation, a blind anchor-dimension check, and
explicit confidence labeling (plan-stated vs. measured-off-linework).

## Layout

- `SKILL.md` — the skill definition: workflow, element ledger, reconciliation and
  anchor-dimension check, markup, sheet-summary template, confidence rules, and the
  estimating process.
- `scripts/split_extract.py` — deterministic preprocessing (requires `pymupdf`:
  `pip install --break-system-packages pymupdf`). Splits a plan set into per-sheet
  `.txt`, `.png`, optional single-sheet `.pdf`, a per-sheet JSON (text blocks, scale,
  vector-drawing count, pdfplumber geometry), and `manifest.json`. Also detects and
  parses plan scale (metric ratio, imperial `1"=N'`, or architectural fraction
  notation), with a slope-callout guard. Supersedes `preprocess_plans.py` — v1's
  script is no longer used; safe to delete from the working copy.
- `scripts/measure.py` — measurement engine: polygon areas, polyline lengths, tag
  counts, dimension-callout extraction, table extraction, page rendering, and
  Bluebeam-safe PDF markup. All geometry output is imperial (ft, SF, acres, SY).
- `scripts/extract_instances.py` — coordinate-grounded instance extraction (turns a
  schedule catalogue into per-placed-object rows with x/y, for reconciling counts).
- `scripts/build_db.py` — loads a `structured.json` (schedules, instances,
  relationships, notes) into queryable SQLite. Optional (Step 1b), for large or
  heavily-requeried plan sets.
- `scripts/validate_provenance.py` — confirms every structured-DB value's source-sheet
  citation actually contains that value; relocates or flags mismatches. Optional,
  pairs with `build_db.py`.
- `references/pay_items.md` — target pay-item catalog (by CSI-ish division) with unit
  of measure and takeoff basis, built from real bids. Enrich as new projects add items.
- `references/scope_kickoff.md` — template for scoping a project before estimating
  (which divisions to include, segregated scopes, exclusions to match a bid, and
  which takeoff method — Steps 1-4 only, or also Step 1b).

## Using it

Point the agent at this folder alongside a plan-set PDF and ask it to read, index, or
estimate from the plans. See `SKILL.md` for the full workflow.

## Change history

Kept in git log — the useful unit here is "what estimating mistake prompted this
change," not a version number. When you update `SKILL.md` or `pay_items.md` after a
real takeoff exposes a gap, say what happened in the commit message.

v2 (this update) folded in `construction-takeoff` and `drawings-analyser` from the
ContractorOS plugin: an element ledger + deterministic reconciliation + blind
anchor-dimension check, and an optional structured-DB + provenance-validation path.
Converted all geometry output to imperial. Prompted directly by three Cottages at
Back Creek takeoff errors: a 15"/12" storm pipe transposition, a duplicated paving
intermediate-course lift, and a curb-LF formula-proxy that missed cul-de-sac bulbs.
