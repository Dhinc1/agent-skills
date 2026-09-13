# Derivation Library

The knowledge that turns measured **primaries** into derived **secondaries**, plus the figures used to sanity-check a finished takeoff. These are starting points, not gospel — every project has its own specification, and a number read off the actual drawing or schedule always beats a default here. When a default is used, it must be written into the takeoff's Assumptions column so it can be challenged.

Read this before Step 2 (build assemblies) and Step 5 (sanity check).

> **This file answers "what does each primary derive into?". For "what primaries exist on this trade in the first place?", use the coverage checklists in `trade_checklists/` (Step 1).** The two work together: the checklist gives the spine of primaries to measure, this library expands each one into its secondaries. Each checklist also ends with a worked assembly in the same shape as the tables below.

## Contents
- [How to read an assembly](#how-to-read-an-assembly)
- [Concrete & structure](#concrete--structure)
- [Architectural / finishes](#architectural--finishes)
- [Electrical](#electrical)
- [Hydraulic / plumbing](#hydraulic--plumbing)
- [Mechanical](#mechanical)
- [Civil / external](#civil--external)
- [Waste factors](#waste-factors)
- [Default depths & thicknesses](#default-depths--thicknesses)
- [Sanity-check benchmarks](#sanity-check-benchmarks)

---

## How to read an assembly

An assembly is one measured primary plus the secondaries it drives. The primary is measured off the drawing; every secondary is a formula referencing it. Volume is never measured — it is **always** an area times a depth, because a depth read from a section or schedule is far more reliable than trying to measure a 3D quantity off a 2D sheet.

```
PRIMARY (measured)            SECONDARIES (derived by formula)
─────────────────────────────────────────────────────────────
Slab area  A (m²)  ──┬──►  Concrete vol  = A × t × (1+waste)        [m³]
   thickness t       ├──►  Reinforcement = (A × t) × ratio_kg_m3    [kg]
   (from section)    ├──►  Sub-base      = A                        [m²]
                     └──►  (Formwork to edges is its OWN primary —
                            perimeter, because it isn't derivable
                            from area.)
```

The judgement call in Step 1 is *which* quantities must be measured directly and which can ride on a formula. Measure the minimum set; derive the rest. Fewer manual measurements means fewer chances to miss something.

---

## Concrete & structure

A structural element is measured as **three trades at once**: **concrete** (volume, m³ — always area × depth, split by grade and zone), **formwork** (area, m² — *every face of concrete that needs a mould*), and **reinforcement** (mass, kg/t — read the bar schedule if it exists; mesh is m² × its code in kg/m²). The primary is the *element* (a slab area, a footing count by type, a column count); the three trades are its secondaries. See `trade_checklists/structural.md` for the full element list.

| Primary (measure) | Type | Secondaries (derive) | Formula |
|---|---|---|---|
| Slab / hardstand area | Area | Concrete volume | `area × thickness × (1+waste)` |
| | | Reinforcement (mesh) | `area × (1+lap_waste)` m² of mesh, OR `volume × kg_per_m3` for bar |
| | | Sub-base / compaction | `area` |
| | | Edge formwork | measure perimeter separately (own primary) |
| | | Soffit formwork | suspended slabs only (`area`); ground slabs have none |
| Footing count by type | Count | Concrete per type | `count × (L×W×D per type from schedule)` |
| | | Reinforcement | `concrete_vol × kg_per_m3` |
| | | Side formwork | `count × perimeter × depth per type` |
| | | Excavation | `footing_vol × bulking × working_space` |
| Column / beam count by type | Count | Concrete, rebar, formwork | from section dimensions in the schedule; formwork = exposed perimeter × height/length |
| Wall area | Area | Concrete (in-situ) | `area × thickness × (1+waste)` |
| | | Reinforcement (each face) | `area × bar_ratio`, or read the reo plan |
| | | Formwork | `area × 2` (both faces) |
| | | Blockwork units (if masonry) | `area × units_per_m2`; core-fill grout `area × cells × cell_vol` |
| | | Mortar, render | ratios per m² |

**Formwork is the line most often under-measured.** It is not derivable from concrete volume — it's the *area of every face that needs a mould*: slab edges and step-down/set-down faces, beam sides + soffits, column faces, both faces of in-situ walls, and a box-out for every penetration. Ground slabs have **no** soffit formwork; suspended slabs do. Measure slab-edge and penetration formwork as their own primaries.

**Reinforcement — read the schedule, don't re-measure.** If a bar/reo schedule exists it IS the reo QTO (High confidence). Mesh is measured in m² then converted by its code: **SL72 = 2.96 kg/m², SL82 = 4.53 kg/m²** (verify on the sheet). Suspended slabs are bar in both directions top and bottom — take from the reo plan, not a mesh ratio. Don't forget trimmer bars at penetrations (on details, easy to miss) and chairs at ~1000 mm centres both ways (2–4% of reo cost).

Reinforcement ratios (bar, kg/m³ of concrete) — use only when nothing is scheduled, and confirm against the structural spec:
- Slabs on ground: 80–120 · Suspended slabs: 100–160 · Beams: 150–250 · Columns: 200–400 · Footings: 60–120 · Pile caps: 150–300

---

## Architectural / finishes

| Primary | Type | Secondaries | Formula |
|---|---|---|---|
| Room floor area | Area | Floor finish (tile/vinyl/carpet) | `area × (1+waste)` |
| | | Tile/sheet count | `area / unit_coverage` rounded up |
| | | Screed/self-level | `area` |
| Room perimeter | Linear | Skirting / cornice | `perimeter − door_widths` |
| | | Wall base, set-down trims | `perimeter` |
| Wall area (perimeter × height) | derived | Paint | `wall_area × coats` |
| | | Plasterboard | `wall_area / sheet_area` rounded up |
| Ceiling area | Area | Grid/tiles, paint | usually ≈ floor area less voids |
| Door / window count by type | Count | Frames, hardware sets, glazing | `count × set_per_door` |

Default ceiling height when not noted: **2.7 m** (residential/commercial) — but read the section first; flag if assumed.

---

## Electrical

The estimator's split is **resource difference** and **installation method** (a light fixed off a ladder and the same light needing a scissor lift are two takeoff items). Tag counts are the primaries.

| Primary | Type | Secondaries | Formula |
|---|---|---|---|
| Light fitting count by type | Count | Cable (per type) | `count × avg_run_m × (1+waste)` |
| | | Conduit, fixing, lamps | `count × ratio` |
| Power outlet count by type | Count | Cable, conduit | `count × avg_run_m` |
| | | Circuit count | `count / points_per_circuit` |
| Switch / sensor / detector count | Count | Cable, back-boxes | `count × ratio` |
| Distribution board count | Count | Submains, breakers | from single-line diagram |
| Cable tray run | Linear | Tray, bracketry, bends | `length × (1+waste)`, supports `length / spacing` |

Typical average cable run per point (very project-dependent — prefer to derive from DB locations on the single-line where possible): lighting 8–12 m, power 6–10 m, data 15–25 m.

---

## Hydraulic / plumbing

| Primary | Type | Secondaries | Formula |
|---|---|---|---|
| Fixture count by type (WC, basin, etc.) | Count | Connections, traps, valves | `count × set_per_fixture` |
| | | Pipe to fixture | `count × avg_branch_m` |
| Pipe run by service & diameter | Linear | Pipe, fittings, insulation, lagging | `length × (1+waste)`; fittings `length / spacing` |
| Floor waste / gully count | Count | Connections, puddle flanges | `count × ratio` |

Read pipe diameter and service from the **line label** next to the run (e.g. "FW100", "CW20"), not from line thickness alone. Different services on the same sheet are different takeoff items.

---

## Mechanical

| Primary | Type | Secondaries | Formula |
|---|---|---|---|
| Diffuser / grille count by type | Count | Flexible duct, connections | `count × ratio` |
| Ductwork run by size | Linear | Sheet metal area, insulation | `length × girth` for sheet area |
| FCU / AHU / unit count | Count | Connections, drains, controls | `count × set` |

---

## Civil / external

| Primary | Type | Secondaries | Formula |
|---|---|---|---|
| **Site clearing & grubbing** | Area | (cleared platform) | measure the developed/disturbed extent as a polygon at scale |
| **Topsoil strip** | derived | Topsoil volume to stockpile | `clearing_area Ã strip_depth` (150 mm default) |
| **Bulk cut to level** | derived | Cut volume | `platform_area Ã avg_cut_depth` (avg depth from contours vs FFL) |
| **Bulk fill to level** | derived | Fill volume (compacted) | `platform_area Ã avg_fill_depth`; cart/import = `(cut â fill)` |
| Pavement / road area by type | Area | Wearing course, base & sub-base layers | `area Ã layer_thickness` per layer |
| Kerb / edge run by type | Linear | Kerb units, concrete bed & haunch | `length`, concrete `length Ã section_area` (~0.05 m³/m typical) |
| Surface channel / dish drain | Linear | Concrete, mesh | `length`, concrete `length Ã section_area` |
| Pit / manhole count | Count | Excavation, surround, lids | `count Ã set` |
| Pipe run by diameter | Linear | Pipe, bedding, trench excavation, backfill | `length`, trench `length Ã width Ã depth` |
| Subsoil / slotted drain | Linear | Slotted pipe, filter stone, geofabric | `length Ã (1+waste)` |

**Earthworks — the line everyone forgets.** On any civil/site sheet the biggest-value quantities are usually the earthworks, and they carry no tag, so they're easy to omit. **Clearing & grubbing** and **topsoil strip** are measurable (clearing area is a polygon; topsoil = area × depth). **Cut & fill** is not an object on a 2D PDF — it's the difference between the existing surface (contours) and the proposed surface (FFL/platform levels): read the contour range across the platform and the finished levels, take an average cut and fill depth, and multiply by platform area. Flag it **Low** and note a proper balance needs a TIN / spot-level model — but **always report a figure**; a missing earthworks line is a worse error than an approximate one.

---

## Waste factors

Applied on top of the net derived quantity (the `(1+waste)` term). Confirm against any project-specific allowance.

| Material | Waste |
|---|---|
| Concrete | 2–5% |
| Reinforcement bar | 5–7.5% (laps often separate) |
| Mesh | 10–15% (laps) |
| Cable | 5–10% |
| Pipe | 5–10% |
| Flooring / carpet / vinyl | 5–10% |
| Tiles (straight / diagonal) | 10% / 15% |
| Plasterboard | 10% |
| Paint | 10–15% |
| Ductwork | 10–15% |

---

## Default depths & thicknesses

Use only when the section/schedule doesn't give a real value, and **always flag the assumption**.

| Element | Default |
|---|---|
| Slab on ground | 150–200 mm |
| Suspended slab | 150–250 mm |
| Strip footing | 300–600 mm deep |
| Pad footing | 400–800 mm deep |
| Topping / screed | 50–75 mm |
| Road base course | 150–300 mm |
| Asphalt wearing course | 40–50 mm |

---

## Sanity-check benchmarks

In Step 5, compare the takeoff against these. A figure well outside the range isn't necessarily wrong, but it must be **explained**, not waved through. These are order-of-magnitude checks, not acceptance criteria.

**Scale check first.** Pick a known dimension (a structural grid, a door at 820/920 mm, a parking bay at 2.4–2.6 m wide) and confirm the measured value matches. A takeoff on the wrong scale is wrong by the square (areas) or cube (volumes) of the error — this is the single highest-leverage check.

| Check | Typical range |
|---|---|
| Concrete per m² of building footprint | 0.3–0.6 m³/m² (low-rise) |
| Reinforcement per m³ concrete | 80–160 kg/m³ (see structure table) |
| Floor area vs sum of room areas | should reconcile within a few % |
| Ceiling area vs floor area | ≈ 1:1 less voids/stairs |
| Light fittings per m² (office) | roughly 1 per 8–12 m² |
| Power outlets per m² (office) | roughly 1 per 6–10 m² |
| GFA vs site footprint × storeys | should reconcile |

**Cross-document checks** (the most valuable):
- Tag counts vs the corresponding **schedule** (door schedule says 15, plan tags = 15?).
- Same item across plan / RCP / section / detail is **one** item, not three.
- Legend/title-block occurrences excluded from counts (definitions, not instances).
- Quantities consistent with any quantities already stated in the spec or BOQ.
