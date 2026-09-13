# Schema guidance — designing the DB per discipline

Universal tables (always):
- `sheets(sheet_id, title, drawing_type, scale, discipline, rev, source_type)`
- `notes(topic, rule_value, source_sheet)` — general/spec notes, one rule per row, verbatim value.
- `relationships(from_entity, relation, to_entity, source_sheet, confidence)` — connective facts STATED in text.
- `placeholders(entity_or_topic, what_is_missing, why, suggested_sheet)` — for facts needing vision (counts off plans, traced runs, raster sheets).

Entity table (one per discipline; keep EVERY listed item even if attributes are null — entity-completeness):
- Structural: `footing_schedule`, `members(mark, category, section, span_or_location, source_sheet, confidence)`, `slabs`, `grids`, `levels`.
- Plumbing: `fixtures(tag, fixture_class, description, manufacturer, model, schedule_name, source_sheet)`, `connections(fixture_tag, service[CW|HW|sewer|trap|vent|gas], size, qty, source_sheet)`, `waste_routing(fixture_tag, method, discharges_to, source_sheet)`.
- Electrical: `boards(tag, type, rating, voltage, source_sheet)`, `circuits(board_tag, circuit_no, load_desc, breaker, cable, source_sheet)`, `luminaires(type, description, wattage, ip_rating, mounting, source_sheet)`.
- HVAC: `equipment(tag, type, capacity, source_sheet)`, `connections(equip_tag, service[supply|return|condensate|gas], size, source_sheet)`.

Two cross-cutting layers (A/B validated: lifted answers ~9.5→14 / 16 and calibration ~9→15 well-calibrated, blind-judged):
- **`reliability` on EVERY fact** — HIGH (vector text / schedule), MEDIUM (vision gestalt / single-source), LOW (scaled / inferred — e.g. ANY length on a set with no printed dimensions). The model reports it and hedges LOW/scaled values. Without it, models state scaled figures (bay spacing, building length) as hard facts — the #1 calibration failure.
- **`context_notes(note, reliability, basis, what_to_verify)`** — qualitative free-text annotations from a VISION pass, using vision for its real strength (gestalt, not counting): "the warehouse slab is the main concrete footprint, spanning ~the full grid"; "the west-wall waste main runs ~the full building length". These answer *understanding* questions the schedule can't, and are the right home for Tim's "runs the entire length of the building" / "main concrete footprint" observations. Mark MEDIUM (visual); never invent precise numbers — pair every note with `what_to_verify`. In testing, the augmented arm answered all the understanding questions the control had to abstain on, and reliability tags REDUCED over-claiming (0 vs 3) — augmentation added value with no harm.

Rules:
- **Store `count` as an explicit integer — never inline notation like "F10 x2".** Ambiguous "x2" + a separate 2-location list made BOTH arms misread it as 4 footings. Use `count: 2` + a separate `instances` list.
- Numeric, atomic, queryable fields over sentences. Convert "2500 x 2000 x 900" to length_mm/width_mm/depth_mm.
- Parse schedules COMPLETELY — they are pre-structured databases sitting on the sheet; they are the highest-value, highest-confidence content.
- Count/aggregate over the entity table, not the relationship/connection table (edge cases with no connections must still count).
- "X2"/"(X2)" = qty 2. "-" in a column = no such connection (don't create the row).
- Every row: source_sheet; confidence where scaled/inferred.

---
## Hardening rules (from independent HVAC + civil stress tests)
- **Checklist sweep (enforce completeness):** for EVERY item on the discipline's "commonly missed" list, either populate its table OR write an explicit `placeholders` row — never silently drop. This is what turns the §6 lists from advice into a guarantee.
- **Grid-less schedules:** HVAC/electrical schedules are often whitespace-aligned, not ruled. `query_drawing.py tables` (pdfplumber `extract_tables`) collapses them into one cell. When a schedule has no gridlines, **read the text blocks by x-position** (cluster by the x of each cell) instead of trusting the table parser. Most-valuable sheet; don't lose it.
- **Count vs length:** linear items (kerb, pipe, duct) — store `count` (tag instances) and `measured_length_m` as SEPARATE fields. Never report a tag count as metres.
- **HVAC — add these tables** when the items are taggable: `dampers(tag, type[FD|SD|FSD], rating, location, source_sheet)`, `controls(tag, type[thermostat|sensor|DDC], serves, source_sheet)`, `air_paths(system[OA|exhaust|relief], cfm, from, to, source_sheet)`. Else they can only ever be placeholders.
- **Civil — node level binding (first-class method):** inverts/levels are often inline `CL=`/`IL=` callouts on the plan (not on a long-section). For each node instance, grab the nearest `CL=`/`IL=` text blocks within R px sharing the node's x, store as node properties (reliability HIGH). This is the civil analogue of "depth from section". Also model the **outfall/headwall** as a node — the lowest invert often sits there, not on a manhole.
- **Ban proximity topology:** do NOT infer pipe/duct from→to by "nearest two nodes" — it is provably wrong (a fall/length can contradict the nearest IL gap). Capture topology only when STATED (connection schedule / single-line), or for gravity drainage reconstruct it from the **IL-drop ≈ length × grade** network. Otherwise record a `placeholder`.

---
## Project hierarchy + primary/secondary quantities (general, project-type-agnostic)
Structure any set as **Project → Disciplines → Systems → Components**, then split each component into **PRIMARY** (counted/measured directly off the drawing — tag instances, schedule items, tagged lengths/areas) and **SECONDARY** (derived from primaries via ratios — rebar from concrete volume, formwork from element faces, cable from outlet count, fittings from pipe length). [the construction-takeoff primary/secondary method]

Keep it GENERAL — the same shape fits a building, a road, or a solar farm; only the branches change, never the primary/secondary split:
- **Building →** civil / structural / services (hydraulic, mechanical, electrical, fire) / architectural.
- **Electrical (any project) →** point of supply → main switchboard/distribution → submains & reticulation → final circuits → fittings.
- **Road →** earthworks / pavement / drainage / services / line-marking & furniture.
- **Solar farm →** array (modules, racking, piles) / DC reticulation / inverters & transformers / HV connection / civil (access, fencing).

Capture a `breakdown` the model fills from what's ACTUALLY in the set — disciplines present, systems per discipline, primary vs secondary per component — plus a `placeholder` for any expected-but-absent branch (a building set with no electrical = flag it). Primary instances come from the `instances` table (with coordinates); secondary quantities are derived, each tagged with its ratio + reliability. **Infer the project type from the set and adapt the branches — don't force a fixed taxonomy.**

*Validated (blind A/B, same input, flat extraction vs this scaffold): the scaffold captured **14/17 coverage categories vs 10/17** and made **0 real errors vs 4** — the flat pass forgot concrete waste %, concrete pump, footing mesh laps and excavation working space, and overstated reinforcement ~3× on a wrong unit weight. Forcing "derive each secondary, state the ratio" drives both completeness and correctness.*
