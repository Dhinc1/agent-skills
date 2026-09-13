# Architectural / Finishes — Takeoff Coverage Checklist

A **starting-point** coverage list for a architectural / finishes takeoff: the quantities a complete architectural / finishes BOQ usually needs. It exists to stop the takeoff under-extracting — work through every category here and decide, for *this* project, whether each line is present, absent, or needs splitting. **It is not exhaustive.** Real drawings always carry items no generic list anticipates, so after working through this, scan the actual sheets and schedules for anything extra and add it.

## How to use this list

- **Don't skip a category because it looks irrelevant** — check it against the drawings first. A category with nothing on the drawings becomes a one-line note ("no [category] in scope"), not a silent omission.
- **These are the PRIMARY quantities** — the things you measure or count directly. Each becomes a line on Tab 1 (Primary Quantities). Everything else (the components, consumables, labour, plant) is a **secondary**, derived from the primary by the assembly — see the worked example at the foot of this file and `../derivation_library.md`.
- **Split a line only where it changes the result** — by type, size, grade, or installation method (e.g. a light fixed off a ladder vs. the same light off a scissor lift). The `(size: ___)` / `(dia: ___)` placeholders mark exactly the splits that usually matter on this trade; fill them from the schedule.
- **Always land a quantity, even low-confidence.** If an item is clearly present but hard to measure precisely, estimate it off the building footprint / a count × a rate / a perimeter and flag it **Low** with the basis in the notes — never leave it blank. (But never fabricate a quantity the drawings don't contain — see SKILL.md "Honesty about confidence".)

## Coverage checklist — Architectural / Finishes


### WALLS - LM BY TYPE

| Item | Unit | Measurement type |
|---|---|---|
| External block wall - W3 (rendered + painted, 200mm, 3.0m high) | LM | Linear (measure runs) |
| Bathroom wet wall - W2 (render + paint outside; render + tile inside, 3.0m high) | LM | Linear (measure runs) |
| Internal block wall - W1 (painted both sides, 200mm, 3.0m high) | LM | Linear (measure runs) |
| Internal partition - lightweight (110mm, 2.7m high) | LM | Linear (measure runs) |

### FLOORS

| Item | Unit | Measurement type |
|---|---|---|
| F0 - Screed 40mm on 85mm concrete base (walkway) | m² | Area |
| F0 - Screed 40mm on 85mm concrete base (car way) | m² | Area |
| F1 - Floor hardener finish, smooth polished (garage) | m² | Area |
| F1 - Floor hardener finish, smooth polished (storage) | m² | Area |
| F0 - Concrete polished screed (closet) | m² | Area |
| F2 - Linoleum on screed (bathroom) | m² | Area |
| Transition strips (where finishes meet) | LM | Linear (measure runs) |

### CEILINGS

| Item | Unit | Measurement type |
|---|---|---|
| R2 - Plasterboard ceiling on metal furring | m² | Area |
| Bulkheads / drop downs (vertical face) | m² | Area |
| Exposed steel structure paint (garage / walkway) | m² | Area |

### DOORS

| Item | Unit | Measurement type |
|---|---|---|
| D1 - Hollow steel door (F5+F4+F1) with frame | No. | Count (off plan/schedule, once) |
| D2 - Metal frame door for inserting (F2+F4) | No. | Count (off plan/schedule, once) |
| D3 - Laminated wood / honeycomb door (L1+B1) | No. | Count (off plan/schedule, once) |
| D4 - Sliding wood closet doors (L1+B1, 2 panels) | No. | Count (off plan/schedule, once) |
| D5 - Sliding wood closet doors (L1+B1, 3 panels per opening) | No. | Count (off plan/schedule, once) |
| D6 - Steel double door (F1+F2+F4) | No. | Count (off plan/schedule, once) |
| D7 - Steel access door, single (F4+F1) | No. | Count (off plan/schedule, once) |
| M1 - Metal rolling door (garage, motorised) | No. | Count (off plan/schedule, once) |

### WINDOWS

| Item | Unit | Measurement type |
|---|---|---|
| W1 - Aluminium frame, sliding glass (G1 - 4mm), 1500x1328 | No. | Count (off plan/schedule, once) |
| W2 - Aluminium frame, sliding glass (G1 - 4mm), 1607x1623 | No. | Count (off plan/schedule, once) |
| W3 - Steel frame, sliding glass (G2 - 6mm), 1100x1426 | No. | Count (off plan/schedule, once) |

### GLAZED WALLS / SLIDING DOORS

| Item | Unit | Measurement type |
|---|---|---|
| Glazed sliding wall (large run) | m² | Area |

### ROOF FINISHES

| Item | Unit | Measurement type |
|---|---|---|
| R1 - Corrugated steel roof sheeting | m² | Area |
| Eave gutter | LM | Linear (measure runs) |
| Downpipes (count + LM) | No. | Count (off plan/schedule, once) |

### EXTERNAL WORKS - FENCING & GATES

| Item | Unit | Measurement type |
|---|---|---|
| Fixed steel fence - F4+F1 (1500mm high) | LM | Linear (measure runs) |
| Sliding fence panel (motorised, vehicle gate) | No. | Count (off plan/schedule, once) |
| Pedestrian access gate | No. | Count (off plan/schedule, once) |

### SUNDRIES

| Item | Unit | Measurement type |
|---|---|---|
| Silicone / sealant (general - if not in assemblies) | LM | Linear (measure runs) |
| Builder's clean (final) | m² | Area |
| Pre-handover defects allowance | Sum | Lump-sum allowance |

## Worked assembly — how one primary expands into secondaries

This is the pattern every line above follows: you measure/count the **primary (P)** once, and the assembly multiplies it out into the components, consumables, labour, and plant — each a *ratio × primary*. Volume secondaries are always `area × depth`. Replicate this shape for every primary in the takeoff; the full library of ratios lives in `../derivation_library.md` and the source spreadsheets.

**Primary:** External block wall - W3 (rendered + painted, 200mm, 3.0m high) — *LM* (measured/counted directly)

| Secondary component | Unit | Ratio / primary | Trade | Note |
|---|---|---|---|---|
| Block (200mm hollow concrete) | No. | 12.5 | Materials | ~12.5 blocks per LM × 3m height |
| Mortar (sand:cement:lime) | m³ | 0.04 | Materials | ~40 L per LM at 3m height |
| Reinforcement - vertical N12 (cores filled) | kg | 4.5 | Steel | At ~800-1000 c/c |
| Block fill grout (vertical cores) | m³ | 0.012 | Concrete | Wet fill cells |
| Lintels (allowance per LM) | No. | 0.05 | Materials | Pro-rata. Most LM has no opening |
| DPC (base course) | LM | 1 | Materials | Continuous |
| Wall ties / starter bars | No. | 4 | Steel | At corners and junctions |
| External render (3m × 1m face) | m² | 3 | Render | External face × 3m height |
| Internal render (3m × 1m face) | m² | 3 | Render | Internal face × 3m |
| External paint - primer + 2 coats oil | m² | 3 | Paint | External face. Includes 6% deduction at openings |
| Internal paint - primer + 2 coats water-based | m² | 3 | Paint | Internal face. Includes 6% deduction at openings |
| Labour - block layer | Hr | 0.6 | Labour | ~0.6 hr per LM at 3m height |
| Labour - labourer (block) | Hr | 0.6 | Labour |  |
| Labour - render hand | Hr | 0.5 | Labour | Both faces |
| Labour - painter | Hr | 0.4 | Labour | Both faces |
| Scaffold / access (allowance) | LM | 1 | Plant | Pro-rata at full height |
