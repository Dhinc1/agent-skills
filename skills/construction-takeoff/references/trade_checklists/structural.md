# Structural — Takeoff Coverage Checklist (Concrete · Reinforcement · Formwork)

A **starting-point** coverage list for a structural takeoff: the quantities a complete structural BOQ usually needs. It exists to stop the takeoff under-extracting — work through every category here and decide, for *this* project, whether each line is present, absent, or needs splitting. **It is not exhaustive.** Real drawings always carry items no generic list anticipates, so after working through this, scan the actual sheets, sections, and schedules for anything extra and add it.

## The structural takeoff is three trades measured together

Every structural element is measured **three ways at once** — these are the three primary measurement types, and almost every line below produces all three:

1. **Concrete — volume (m³).** Driven by the element's dimensions. Volume is **always area × depth (or length × cross-section)** — never measured directly off a 2D sheet. Split by **grade** (N25 internal vs N32 external behave differently) and by **zone** where thickness changes.
2. **Formwork — area (m²).** *Every face of concrete that needs a mould.* This is the line most often under-measured: slab edges, step-down/set-down faces, beam sides and soffits, column faces, wall faces, penetration box-outs. A small area per metre, but hundreds of metres on a building.
3. **Reinforcement — mass (kg or tonnes).** Bars, mesh, and accessories. **If a reinforcement schedule exists, that IS your reo QTO — read it, don't re-measure it** (a scheduled bar mass is High confidence; a derived `volume × kg/m³` ratio is Low). Mesh is measured in m² then converted to kg by its code (e.g. SL72 = 2.96 kg/m², SL82 = 4.53 kg/m²).

## How to use this list

- **Read the drawings in this order** before measuring: general arrangement / plan (element locations, overall dimensions) → sections & elevations (depths, thicknesses, heights) → details (connections, lap lengths, bar sizes) → footing/slab schedule (standardised types, zones) → **reinforcement schedule (if it exists, this is your reo)**.
- **These are the PRIMARY quantities** — the elements you measure or count directly (a slab area, a footing count by type, a wall area, a column count). Each becomes a line on Tab 1 (Primary Quantities). Concrete volume, formwork area, reo mass, and the rest are **secondaries** derived from the primary by the assembly — see the worked example at the foot of this file and `../derivation_library.md`.
- **Split a line where the resource changes** — by element type, by grade, by thickness/depth zone, and by anything with its own pour detail (a slab thickening at a load point, a wet-area set-down). The schedule types (F1, F6, ST1…) are the natural split.
- **Always land a quantity, even low-confidence.** If reo isn't scheduled, estimate it `concrete_vol × kg/m³` off the structure table in `../derivation_library.md` and flag it **Low**. If a slab thickness isn't on a section, assume a default, flag it, and write the assumption in the notes — never leave concrete blank. (But never fabricate a quantity the drawings don't contain — see SKILL.md "Honesty about confidence".)

## Coverage checklist — Structural

### SLABS & FOOTINGS

| Item | Unit | Measurement type |
|---|---|---|
| Slab on ground by zone/grade (thickness from section) | m² | Area → concrete volume, mesh, formwork to edge |
| Suspended slab by zone/grade | m² | Area → concrete volume, bar both ways top & bottom, soffit formwork |
| Slab thickening / rib at load points (e.g. ST1 500W × 150D) | LM | Linear → extra concrete + bar, measured separately |
| Set-down / rebate (wet areas, reduced-thickness zones) | m² | Area → reduced concrete, extra edge formwork (separate pour detail) |
| Strip footing by type (from footing schedule) | LM | Linear → concrete (L × W × D), bar, side formwork |
| Pad / isolated footing by type | No. | Count → concrete per type, bar, formwork |
| Pile cap by type | No. | Count → concrete, bar (cage), formwork |
| Ground beam / edge beam by type | LM | Linear → concrete, bar, side + soffit formwork |
| Blinding / mud slab under footings | m² | Area → lean-mix concrete |
| Slab edge formwork | LM | Linear (perimeter × slab depth) — own primary, not derivable from area |
| Penetration / opening box-out | No. | Count → formwork box per pipe, duct, access opening |
| Trimmer / extra bars at penetrations | No. | Count → reo around openings (on details — easy to miss on plan) |

### COLUMNS

| Item | Unit | Measurement type |
|---|---|---|
| Column by type (from column schedule) | No. | Count → concrete (section × height), bar (cage + ties), formwork (perimeter × height) |
| Column starter bars / dowels | No. | Count → reo dowels into footing/slab below |
| Column capital / head detail | No. | Count → extra concrete + formwork where present |

### BEAMS

| Item | Unit | Measurement type |
|---|---|---|
| Beam by type (from beam schedule) | LM | Linear → concrete (section × length), bar, formwork (2 sides + soffit) |
| Band beam / wide shallow beam | LM | Linear → concrete, bar, soffit + edge formwork |
| Transfer beam | LM | Linear → heavy concrete + heavy reo, formwork |
| Lintel (structural, cast in situ) | No. | Count → concrete, bar, formwork |

### WALLS (CONCRETE / CORE)

| Item | Unit | Measurement type |
|---|---|---|
| Core / shear wall by thickness & grade | m² | Area (length × height) → concrete (area × thickness), bar each face, formwork both faces |
| Retaining wall by type | m² | Area → concrete, bar, formwork; plus footing/toe as separate line |
| Basement wall | m² | Area → concrete, bar, formwork (+ waterproofing flag) |
| Blockwork wall (reinforced, core-filled) | m² | Area → blocks, core-fill grout volume, vertical bar |
| Wall starter bars / dowels | No. | Count → reo dowels at base |

### PILES & DEEP FOUNDATIONS

| Item | Unit | Measurement type |
|---|---|---|
| Bored pile by diameter | LM | Linear (depth) → concrete (π r² × depth), cage reo, no formwork (ground-formed) |
| Driven / precast pile by type | No. | Count → supply length, splices |
| Pile cap (see Slabs & Footings) | No. | Count |
| Pile testing (static / dynamic / integrity) | No. | Count → testing allowance |

### STAIRS & MISC IN-SITU

| Item | Unit | Measurement type |
|---|---|---|
| In-situ concrete stair flight | No. | Count → concrete (waist + treads), bar, soffit + riser formwork |
| Plinth / equipment base | No. | Count → concrete, bar, formwork |
| Topping slab / structural screed | m² | Area → concrete (area × thickness), mesh |
| Kerb / upstand (structural) | LM | Linear → concrete, formwork |

### REINFORCEMENT ACCESSORIES & SUNDRIES

| Item | Unit | Measurement type |
|---|---|---|
| Bar chairs / spacers | No. | Count (~1000mm centres both ways) — 2–4% of reo cost |
| Mesh laps (allowance) | m² | Derived (10–15% on mesh area) |
| Tie wire | kg | Derived (~1% of reo mass) |
| Cast-in items (ferrules, anchor bolts, plates) | No. | Count off details |
| Construction / control / expansion joints | LM | Linear → joint material, dowels |
| Waterstop (to construction joints below ground) | LM | Linear |
| Curing compound / membrane | m² | Area (= concrete surface area) |
| Concrete pump (hours) | Hr | Derived from total concrete volume ÷ pour rate |

## Worked assembly — how one primary expands into secondaries

This is the pattern every line above follows: you measure/count the **primary (P)** once, and the assembly multiplies it out into concrete, formwork, reinforcement, consumables, labour, and plant — each a *ratio × primary*. **Volume is always `area × depth`**, never measured directly. Replicate this shape for every primary; the reinforcement ratios, waste factors, and default depths live in `../derivation_library.md`.

**Primary:** Slab on ground — 150mm, N25 (m² of slab area, measured directly off the plan at scale)

| Secondary component | Unit | Ratio / primary | Trade | Note |
|---|---|---|---|---|
| Concrete (N25) | m³ | 0.150 × 1.025 | Concrete | area × thickness × (1 + 2.5% waste); thickness from section |
| Mesh SL82 | m² | 1.10 | Steel | area × (1 + 10% laps); SL82 = 4.53 kg/m² → convert to kg |
| Mesh laps / chairs / tie wire | kg | derived | Steel | chairs at 1000 c/c both ways |
| Sub-base / compaction prep | m² | 1 | Earthworks | under slab |
| Vapour barrier / membrane | m² | 1.10 | Materials | under slab + laps |
| Edge formwork | LM | (own primary) | Formwork | perimeter × slab depth — measured separately, not derived from area |
| Penetration box-outs | No. | (own primary) | Formwork | count off plan/details |
| Curing compound | m² | 1 | Materials | top surface |
| Control joints / saw cuts | LM | per spec spacing | Concrete | |
| Concrete pump | Hr | vol ÷ pour rate | Plant | derived from concrete volume |
| Labour — concreter | Hr | 0.25 | Labour | per m² |
| Labour — steel fixer | Hr | 0.10 | Labour | mesh + accessories |

> Note: a **suspended** slab differs — reo is **bar in both directions, top and bottom** (measure from the reo plan/schedule, not a mesh ratio) and it carries **soffit formwork** (a ground slab has none). Build it as its own assembly.
