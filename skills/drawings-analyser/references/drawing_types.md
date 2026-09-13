# Drawing Types — Taxonomy and Per-Type Analysis Prompts

This is the reference Claude uses when classifying sheets and analysing them.
Different drawing types contain fundamentally different information; using
the same prompt on a layout and a single line diagram produces nonsense on
one of them. This file defines the types and the prompt template per type.

**Important:** classification is judgement, not pattern matching. Claude
reads the rendered PNG and the vector JSON for each sheet and decides what
type it is. Drawing conventions vary across offices, countries, and
disciplines — there are no reliable regex patterns for sheet numbers.

---

## Drawing type taxonomy

Use these types and only these types. If a sheet doesn't fit, use `other`
and explain in the justification.

| Type | What it is | Common signals |
|---|---|---|
| `general_arrangement` | Floor plans, site plans, key plans. The default "layout" sheet. Plan view of a level or area. | Plan view, scale typically 1:50–1:200, room labels, grid lines, dimensions. No section cuts, no schedules dominating the sheet. |
| `section_view` | Vertical cut through the building or a part of it. | Profile geometry, level annotations (FFL, ceiling, roof), labels like "Section 1-1", scale typically 1:50–1:100. |
| `elevation` | External (or internal) view of a vertical surface. | Façade, no floor plan, materials/finishes called out on surfaces, typically 1:50–1:200. |
| `detail` | Close-up of a specific assembly or junction. | Scale typically 1:5–1:20, callouts referencing parent sheets, materials labelled with tight specificity. |
| `schedule_sheet` | Tabular data — door, window, fixture, panel, finishes, equipment schedules. | Dominated by tables. Multiple rows × multiple columns. May have small drawings as keys but the table is the content. |
| `general_notes` | Mostly text — specifications, general notes, trade-specific notes. | High text density, low or no geometric content, often portrait or split text/diagram. |
| `legend` | Defines the symbols used in this drawing set. | "LEGEND", "SYMBOLS", "ABBREVIATIONS" headings; a key or table mapping symbol → description. Often appears on the first sheet of each discipline. |
| `single_line_diagram` | Schematic representation of a system (electrical, hydraulic, mechanical). | One-line schematic, no spatial scale, switchgear/equipment boxes, lines representing distribution, labels like "SLD" or "schematic". |
| `cover_sheet` | Project info, drawing register, sheet list, location plan. | Title-page styling, list of all drawings in the set, location plans, project details. |
| `coordination_drawing` | Multiple disciplines overlaid — clash detection / services coordination. | Mixed line styles (different colours/patterns per discipline), services coordination notes, often labelled "coordination". |
| `other` | Anything else. | Justify what it is. |

`discipline` is a separate axis — `Architectural`, `Structural`, `Electrical`,
`Mechanical`, `Hydraulic`, `Civil`, `Fire`, `Communications`, `Landscape`, etc.
A sheet has one type and one discipline.

---

## Classification prompt (Step 5)

For each sheet in `sheet_index.json`, send Claude the rendered PNG plus the
vector JSON, and ask:

> You are classifying a single construction drawing sheet.
>
> Below is a rendered image of the sheet, and a JSON containing every piece
> of selectable text on it (with bounding boxes) plus a sample of geometric
> primitives. Use both. The text is reliable — read the title block and any
> headings. The image shows you what's actually on the sheet.
>
> Classify this sheet into exactly one `drawing_type` from the taxonomy
> below, and identify its `discipline`. Provide a confidence
> (`high` / `medium` / `low`) and a one-sentence justification grounded in
> what you see — not what the sheet number suggests.
>
> [paste taxonomy table here]
>
> Return JSON only, matching this schema:
>
> ```json
> {
>   "sheet_id": "<from title block, or null if not visible>",
>   "title": "<from title block, or null>",
>   "discipline": "<one of the disciplines listed above>",
>   "drawing_type": "<one of the types from the taxonomy>",
>   "confidence": "high|medium|low",
>   "justification": "<one sentence>"
> }
> ```

Aggregate the results into `sheet_classification.json`:

```json
{
  "classified_at": "2026-04-15T10:00:00",
  "sheets": [
    { "stem": "...", "sheet_id": "...", "drawing_type": "...", ... },
    ...
  ]
}
```

Show the user a quick summary table after classification (counts per type,
counts per discipline, any `low` confidence sheets) and ask them to confirm
or override before any per-sheet analysis runs.

---

## Per-type analysis prompts (Step 7)

After classification, the per-sheet analysis uses a different prompt
template per drawing type. The shared inputs are always:

- The rendered PNG (2576px long edge)
- The vector extraction JSON
- The relevant discipline's symbol library (from Step 6) — for sheets where
  symbols matter
- The trade perspective (from Step 5a of the existing skill)
- This per-type template

The output is always a Markdown file with structured fields in Markdown-KV
format (`Field: Value`) followed by prose. Markdown-KV is more reliably
parsed by downstream LLM sessions than JSON or YAML.

### Two universal sections (every type, every sheet)

Two sections appear in every per-sheet markdown regardless of drawing type.
They turn `drawings/` from a static description archive into a directory
of *what each sheet can answer precisely* — so future Claude sessions know
when and where to call `scripts/query_drawing.py` for an exact answer.

#### Section: `## Answerable from this drawing`

A short, honest list of the questions this specific sheet can answer
**precisely** (via vector queries against the source PDF) and the questions
it cannot. Don't claim the sheet can answer something it can't, and don't
omit something obvious that it can. Three buckets:

```
## Answerable from this drawing

**Precisely (via query_drawing.py):**
- <question type> — e.g. "Total slab area, excluding office cutout"
- <question type> — e.g. "Footing schedule contents (table)"
- <question type> — e.g. "Overall building dimensions"

**By inspection of the rendered PNG (vision required, less precise):**
- <question type> — e.g. "Count of F7 footings (vision counts unreliable)"
- <question type> — e.g. "Approximate location of riser shaft"

**Not answerable from this sheet — refer:**
- <question type> → <other sheet>, e.g. "Office slab geometry → S-102"
- <question type> → <other source>, e.g. "Slab reinforcement → typical details"
```

This section is what makes the skill usable for downstream querying. Be
concrete. Don't say "construction detail" — say "wall-to-slab junction at
external edge". Don't say "schedule" — say "door schedule (32 doors)" or
"footing schedule (13 types)". The user will read this section to decide
which drawing to query.

#### Section: `## Coordinate hints for query-time extraction`

Approximate bounding boxes (in PDF points; same coordinate system as the
vector JSON) for the named regions a future query is most likely to need.
You estimate these from the vector JSON and the rendered PNG. They don't
need to be pixel-perfect — the query script clips to page bounds, and a
generous bbox returns the right primitives. Use the page dimensions
visible in the vector JSON's `width_pts` and `height_pts`.

```
## Coordinate hints for query-time extraction

Page size: <width_pts> × <height_pts> pts (origin top-left)

Region                          | bbox (x0, y0, x1, y1)
--------------------------------|--------------------------
Title block                     | <x0> <y0> <x1> <y1>
Drawing area (excludes title)   | <x0> <y0> <x1> <y1>
<Named feature 1>               | <x0> <y0> <x1> <y1>
<Named feature 2>               | <x0> <y0> <x1> <y1>
<Schedule / table region>       | <x0> <y0> <x1> <y1>
```

Examples of useful "named feature" regions, depending on drawing type:
- General arrangement: each major slab, each zone, each labelled space
- Section: each construction layer, each level annotation strip
- Schedule sheet: each table; rows of interest if a sub-region is needed
- Single line diagram: each switchboard or distribution node
- Detail: the full detail outline, the layered section if shown
- Coordination drawing: each named coordination zone

Three rules for these hints:

1. Always include `Title block` and `Drawing area` — they're useful on
   every sheet.
2. For schedule sheets, every table gets its own region. The query
   script's `tables` command can then target a specific table.
3. For general arrangement plans where the user is likely to ask about
   areas, every distinct slab or zone gets a region. The hint can be
   generous — a polygon query inside it returns the actual outline.

The hints are *suggestions*, not constraints. A future query can use any
bbox; these are just pre-computed for the regions most likely to matter.

### Template — `general_arrangement`

```
# Sheet <ID> — <Title> (<Perspective> perspective)

## Title block
Sheet ID: <from vector JSON>
Title: <from vector JSON>
Drawing Type: general_arrangement
Discipline: <from classification>
Scale: <from vector JSON or visible on sheet>
Revision: <from vector JSON>
Date: <from vector JSON>
Source PDF: <relative path to drawings_split single-sheet PDF>

## View extent
<What's shown — which level, which zone, partial or full>

## Grid and setout
<Grid references visible (e.g. A–G across, 1–8 down). Setout points and
critical dimensions if shown.>

## Spaces / rooms / zones
<Walk the sheet zone by zone. Every labelled space gets a line:>
- <Room name / number>: <key features for the chosen perspective>
- ...

## Building elements (perspective-tilted)
<For an electrical perspective on an architectural plan: ceiling types,
wall types, riser locations, accessible roof spaces, slab thicknesses
where penetrations matter. For a hydraulic perspective: set-downs, slab
edges, riser shafts, floor wastes. For a GC perspective: cover everything
evenly.>

## Materials / specifications called out
<Any material, grade, size, manufacturer, model named on this sheet —
verbatim. Do not infer.>

## Cross-references on this sheet
<Section markers, detail bubbles, schedule references, spec references.
Use the Step 8 graph to mark resolved/unresolved when available.>

## Notes / annotations
<General notes, construction notes, hold points, inspection points,
authority requirements — verbatim or near-verbatim where critical.>
```

### Template — `section_view`

```
# Sheet <ID> — <Title> (<Perspective> perspective)

## Title block
[same as above with Drawing Type: section_view]

## What this section shows
<Which plan does it cut through, where (grid line / location), and what's
visible foreground vs background>

## Levels and dimensions
<Every annotated level — FFL, ceiling, roof, parapet — and key vertical
dimensions>

## Construction shown (perspective-tilted)
<Slab/wall/roof construction depicted, with materials and grades where
called out. For electrical: ceiling space depth, riser geometry, soffit
type. For hydraulic: slab penetrations, drainage gradients, set-downs.
For structural: load paths, member sizes, connections.>

## Materials and specifications
<As called out on this sheet>

## Cross-references on this sheet

## Notes / annotations
```

### Template — `elevation`

```
# Sheet <ID> — <Title> (<Perspective> perspective)

## Title block
[Drawing Type: elevation]

## What this elevation shows
<Which façade or internal wall, orientation if shown>

## Façade composition / finishes
<Material zones — cladding, glazing, masonry, metal — with extents and
specs where called out>

## Heights and setouts
<Parapet heights, FFLs, sill/header heights for openings>

## Openings
<Windows, doors, louvres — type references, sizes if shown>

## Cross-references on this sheet

## Notes / annotations
```

### Template — `detail`

```
# Sheet <ID> — <Title> (<Perspective> perspective)

## Title block
[Drawing Type: detail]

## What's being detailed
<Assembly, junction, or condition. Where in the building it's used.>

## Parent sheet(s)
<Which sheets this detail is referenced from, per the cross-reference graph>

## Layered construction
<Layer by layer, from inside to outside or top to bottom: material,
thickness, fixings/fasteners, vapour barriers, insulation type and grade,
finishes>

## Critical dimensions
<As called out — overall thickness, member sizes, fastener spacings>

## Specifications referenced
```

### Template — `schedule_sheet`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: schedule_sheet]

## Schedule type
<Door / Window / Fixture / Panel / Finishes / Equipment / etc.>

## Row count
<Total entries>

## Headers
<Column headers as they appear>

## Entries
<For schedules under ~30 rows, extract every row in Markdown table form.
For larger schedules, summarise the structure and extract the first 10 +
last 10 rows. Downstream sessions can open the source PDF for the full
schedule.>

## Cross-references on this sheet
<Where the items in this schedule are deployed — e.g., "doors deployed
on sheets A-201, A-202, A-203" if visible>
```

### Template — `general_notes`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: general_notes]

## Notes
<Extract every note faithfully. Group by category as they appear on the
sheet — General, Structural, Electrical, Hydraulic, Fire, etc. Do not
paraphrase. The vector JSON has every character; use it.>

## Specifications referenced
<Any spec sections cited in the notes>

## Standards referenced
<Australian Standards, codes, authority requirements named>
```

### Template — `legend`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: legend]

## Symbols defined
<Every symbol from the legend. For each:>
- ID: <symbol shorthand if given, otherwise an inferred ID>
- Description: <as written>
- Discipline: <from classification>
- Bbox on sheet: <approximate bbox in PDF points so symbol_library.json
  can crop the symbol image>

## Abbreviations
<If the sheet contains an abbreviations list, capture every entry.>

## Notes about symbol usage
<Any notes about when to apply which symbol — verbatim.>
```

> The legend sheet's per-sheet markdown feeds Step 6 (symbol library
> extraction). After this step runs, the bbox coordinates listed here are
> used by `crop_region.py` to produce a PNG per symbol.

### Template — `single_line_diagram`

```
# Sheet <ID> — <Title> (<Perspective> perspective)

## Title block
[Drawing Type: single_line_diagram]

## System represented
<What this SLD covers — the whole electrical install, a specific switchboard,
a hydraulic riser, a mechanical control schematic>

## Source(s) of supply
<Utility connection, generator, source pump, primary energy input. Voltage,
phase, capacity if shown.>

## Distribution structure
<Walk the schematic from source downstream. For each major node:>
- Node: <e.g. MSB, DB-L1, RCD-1>
  - Upstream: <what feeds it>
  - Protective device: <breaker rating, RCD, fuse>
  - Cable: <size, cores, type if shown>
  - Loads / downstream: <list>

## Capacities and ratings
<Switchgear ratings, cable ratings, fault levels if shown>

## Cross-references on this sheet
<Where the equipment in this SLD physically lives — e.g., "MSB located on
A-201 at grid C-3" if cross-referenced>
```

### Template — `cover_sheet`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: cover_sheet]

## Project information
<Project name, address, client, principal contractor, lead consultant>

## Drawing register
<Every sheet listed on the cover, with sheet ID, title, revision, date>

## Location / context
<Site plan or location plan summary>

## Notes / disclaimers
```

### Template — `coordination_drawing`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: coordination_drawing]

## Disciplines overlaid
<Which trades are shown on this sheet>

## Coordination zones
<Areas where services are particularly congested or where there are
documented clashes>

## Resolved clashes
<Any clashes that have been resolved with a note explaining the resolution>

## Open coordination items
<Anything flagged for further coordination>

## Cross-references on this sheet
```

### Template — `other`

```
# Sheet <ID> — <Title>

## Title block
[Drawing Type: other — see justification]

## Justification
<Why this didn't fit any other type>

## Content
<Best-effort exhaustive description, perspective-tilted>

## Cross-references on this sheet
```

---

## Cross-reference detection prompt (Step 8)

The cross-reference graph is built by reading the per-sheet markdown files
already produced and asking Claude to detect the convention this drawing
set uses. Do not assume "1/A-301" means anything specific — different
offices and countries use different conventions.

> You are building a cross-reference graph for a construction drawing set.
>
> Below is the contents of every per-sheet markdown file produced for this
> project, in the order they were generated. Each file lists "Cross-references
> on this sheet" — the section markers, detail bubbles, schedule references,
> and specification references the sheet contains.
>
> Your job is two things:
>
> 1. Detect the cross-reference **convention** used in this set. Common
>    conventions include "detail-on-top" (`1/A-301` = detail 1 on sheet
>    A-301), "sheet-on-top" (`A-301/1`), or letter-based (`A` on sheet
>    `A-301`). Some sets use multiple conventions for different reference
>    types. State what you observe.
>
> 2. Build a **graph** of every cross-reference, with `source_sheet`,
>    `source_type`, `source_label`, `target_sheet`, `target_label`,
>    `target_type`, and `resolved` (true if the target sheet is in the
>    drawing set, false if not).
>
> Return JSON matching this schema:
>
> ```json
> {
>   "convention_detected": "<one or more sentences describing what you see>",
>   "references": [
>     {
>       "source_sheet": "...",
>       "source_type": "section_marker|detail_bubble|schedule_ref|spec_ref",
>       "source_label": "...",
>       "target_sheet": "...",
>       "target_label": "...",
>       "target_type": "section_view|detail|schedule_sheet|specification",
>       "resolved": true,
>       "reason": "<only if resolved is false>"
>     }
>   ]
> }
> ```

Output to `cross_references.json`.

---

## Coordination pass prompt (Step 9)

Final pass. Reads `drawings.md`, `cross_references.json`, and
`symbol_library.json`, then asks Claude:

> You have access to:
> - `drawings.md` — index of every sheet with summary
> - `cross_references.json` — every cross-reference detected, with
>   `resolved` flag
> - `symbol_library.json` — every symbol defined in any legend
>
> Surface coordination issues:
>
> 1. Cross-references where `resolved` is false — list them with the
>    source sheet and what they point at.
> 2. Symbols used on per-sheet markdowns that don't appear in the symbol
>    library for their discipline.
> 3. Drawing register inconsistencies — sheets referenced but not present,
>    sheet count mismatches, missing revisions.
> 4. Trade coordination gaps inferred from the per-sheet markdowns —
>    things like "electrical penetrations called out on E-201 with no
>    matching penetration on the structural penetration plan." Be specific.
>    Cite the sheets you're comparing.
>
> Output as `coordination_issues.md`. Group findings by category. Be
> precise. Do not invent issues — if there is no evidence, do not list it.

---

## Notes on prompt construction

- **Always include the vector JSON in the prompt.** It's the source of
  truth for text. The PNG is for visual interpretation only.
- **Always include the symbol library** (filtered to the relevant
  discipline) when analysing any sheet that contains symbols.
- **Always include the cross-reference graph** (filtered to references
  where this sheet is the source or the target) when analysing a sheet.
- Don't ask Claude to count things in the per-sheet pass. Counts are
  unreliable. If the user wants quantities, run the `construction-takeoff`
  skill against `drawings_split/<sheet>.pdf` separately.
- Use `low` confidence on classification as the trigger for a human
  check, not as a reason to skip the sheet. Always classify; flag the
  uncertain ones.
