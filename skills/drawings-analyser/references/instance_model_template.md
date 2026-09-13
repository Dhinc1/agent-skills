# The instance model — the IFC-shaped template the model populates

This is the upgrade from a schedule **catalogue** (one row per type) to an instance **model** (one row per physical object, with coordinates). It is, deliberately, a lightweight version of how IFC/BIM structures data.

## How IFC actually structures it (and why this mirrors it)
An IFC element is: **object + placement + properties + relationships**.
- `IfcPipeSegment` / `IfcFooting` / `IfcLightFixture` = the typed object (the "what").
- `ObjectPlacement` = its **coordinates** (the "where").
- `Pset_*` property set = material, dimensions, specs (the "features").
- `IfcRelConnectsPorts` / containment = its **from/to** and what it sits in (the "topology").

Your proposal is exactly this. The template below is an IFC-shaped target the model fills, per element.

## The template (per element type)
```json
{
  "tag": "F10",
  "ifc_class_hint": "IfcFooting",          // or IfcPipeSegment, IfcLightFixture, IfcColumn...
  "type_properties": {                      // from the SCHEDULE (one definition)
    "description": "Pad footing",
    "length_mm": 3200, "width_mm": 3200, "depth_mm": 1200,   // L,W from schedule/plan; DEPTH often from SECTION/detail views
    "material": "N25 concrete", "reinforcement": "2 LAYERS SL81 T&B",
    "spec_ref": "S101 footing schedule"
  },
  "instances": [                            // from the PLAN text layer — every tag's (x,y), schedule region excluded
    {"x": 280, "y": 920, "sheet": "S101", "grid": "w14/wD"},
    {"x": 280, "y": 811, "sheet": "S101", "grid": "w15/wD"}
  ],
  "count": 2,                               // = len(instances) -> the takeoff quantity
  "topology": null                          // for LINEAR elements only: {"from": "...", "to": "...", "run_m": N}
}
```

For **linear** elements (pipe, cable, beam, duct) the `topology` block carries Tim's "runs from / runs to":
```json
"topology": {"from": "fixture SK139", "to": "floor sink FS-1", "service": "waste", "size": "1-1/2\"", "run_m": null}
```

## Where each field comes from (multi-view fusion — how a QS actually reads a set)
| Field | Source view | Method | Reliability |
|---|---|---|---|
| type/material/size (L×W) | **Schedule** | vector text | near-lossless |
| **depth / height** | **Section / detail views** | read the dimension on the cut | high (text) |
| **placement (x,y)** | **Plan** | tag bbox centroid in the text layer | high on vector sheets |
| **count** | Plan | `len(instances)` after excluding schedule/legend/diagram regions | high (validated 14/14 vs takeoff) |
| **grid / room** | Plan | compare instance (x,y) to grid-label / room coordinates | high where grids are tagged |
| **from / to (topology)** | Plan lines / single-line / riser | line-geometry grouping OR stated in a schedule | **HARD** — tabulated = easy, traced-on-plan = the open problem |

## The two hard edges (flag as placeholders, never fabricate)
1. **Raster / outlined sheets** have no text layer → no tag coordinates → instances need vision/OCR. Flag.
2. **Non-tabulated topology** (tracing a pipe/cable run across a plan) needs vector line-geometry grouping (`get_drawings()`), the genuinely unsolved part. Where from/to is *stated* (connection schedule, single-line, panel schedule) it extracts cleanly; where it only exists as drawn lines, record a `placeholder`.

## Why this is objectively better
- It answers the questions a schedule-only DB **cannot**: instance counts ("how many F10s" → 2), locations ("which footings on grid wD"), and spatial/proximity queries — the things needed for **both takeoff and querying**.
- Counts are deterministic and free (the positions are already in the text layer).
- It is the correct data shape (IFC), so it also exports/maps cleanly to BIM later.

Validated on the structural set: coordinate-filtered instance counts matched a verified human/AI takeoff **14/14 marks exactly**, and F10 coordinates placed both instances at w14/wD–w15/wD, matching the takeoff's independent location note.

---
## Method: binding loose level/dimension callouts to a node (civil + others)
Inverts (`IL=`), cover levels (`CL=`), finished levels (`FFL=`), and key dimensions are frequently
**loose text callouts on the plan**, not tabulated. To attach them to the right instance:
1. Extract node instances with coordinates (`extract_instances.py`).
2. For each node, find the nearest `IL=`/`CL=`/level callouts within radius R px (and roughly sharing x or y).
3. Store as node properties with reliability HIGH (it's text-layer), recording the callout it came from.
This is the general form of "depth-from-section": the *value* is on a different view/region than the *placement*, and the join is by coordinate proximity. Model special nodes too (outfall/headwall = lowest invert).

## Rule: topology only when stated or physically reconstructable
- `from`/`to` for a run: populate ONLY if a connection schedule / single-line / riser states it, OR (gravity drainage) reconstruct from the IL-drop ≈ length × grade network.
- NEVER infer from "nearest two nodes" — banned (false topology). Unknown from/to → a `placeholder`, not a guess.
