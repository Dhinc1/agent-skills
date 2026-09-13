# land-plan-estimator

A Claude skill for reading and estimating from civil land-development plan sets (PDF)
without dumping the raw PDF into context. Preprocesses a plan set into per-sheet text +
raster images, builds a routing index, then estimates against a pay-item catalog with
explicit confidence labeling (plan-stated vs. measured-off-linework).

## Layout

- `SKILL.md` — the skill definition: workflow, sheet-summary template, confidence
  rules, and estimating process.
- `scripts/preprocess_plans.py` — deterministic preprocessing (requires `pymupdf`:
  `pip install --break-system-packages pymupdf`). Splits a plan set into per-sheet
  `.txt` (text layer), `.png` (raster), optional single-sheet `.pdf`, and a
  `manifest.json`.
- `references/pay_items.md` — target pay-item catalog (by CSI-ish division) with unit
  of measure and takeoff basis, built from real bids. Enrich as new projects add items.
- `references/scope_kickoff.md` — template for scoping a project before estimating
  (which divisions to include, segregated scopes, exclusions to match a bid).

## Using it

Point the agent at this folder alongside a plan-set PDF and ask it to read, index, or
estimate from the plans. See `SKILL.md` for the full workflow.

## Change history

Kept in git log — the useful unit here is "what estimating mistake prompted this
change," not a version number. When you update `SKILL.md` or `pay_items.md` after a
real takeoff exposes a gap, say what happened in the commit message.
