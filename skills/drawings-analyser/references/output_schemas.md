# Output Schemas — New Artefacts

The upgraded skill writes four new artefacts beyond the original three.
This file defines their schemas. Read it when generating each file.

All JSON is human-readable indented (`json.dump(..., indent=2)`). All
markdown uses Markdown-KV format for structured fields followed by prose
sections.

---

## `sheet_index.json`

Built by `scripts/build_sheet_index.py` after `process_drawing.py` has run
across every drawing PDF. Pure file I/O — no judgement.

```json
{
  "drawings_split_root": "<absolute path>",
  "total_sheets": 142,
  "sheets": [
    {
      "stem": "A-Series_sheet1",
      "source_pdf": "A-Series.pdf",
      "single_sheet_pdf": "<abs path>/A-Series_sheet1.pdf",
      "image_path": "<abs path>/A-Series_sheet1.png",
      "extraction_path": "<abs path>/A-Series_sheet1.json"
    }
  ]
}
```

The `extraction_path` JSON is the per-sheet vector data produced by
`process_drawing.py`. Schema:

```json
{
  "page_number": 1,
  "width_pts": 2384.0,
  "height_pts": 1684.0,
  "all_text": "<every text block joined by newlines>",
  "text_blocks": [
    {"text": "...", "size": 10.0, "bbox": [x0, y0, x1, y1], "in_title_zone": true}
  ],
  "title_block_candidates": [<subset of text_blocks where in_title_zone=true>],
  "pdfplumber": {
    "available": true,
    "chars_count": 524,
    "lines_count": 312,
    "rects_count": 87,
    "curves_count": 0,
    "lines_sample": [{"x0": ..., "y0": ..., "x1": ..., "y1": ...}],
    "rects_sample": [{"x0": ..., "y0": ..., "x1": ..., "y1": ..., "width": ..., "height": ...}]
  },
  "vector_drawing_count": 142
}
```

---

## `sheet_classification.json`

Produced after Step 5 (AI classification — Claude reads each sheet's PNG
+ vector JSON and decides type/discipline). One entry per sheet from
`sheet_index.json`.

```json
{
  "classified_at": "2026-04-15T10:00:00Z",
  "model": "claude-opus-4-7",
  "convention_notes": "<any high-level observations about this set's conventions, e.g. discipline prefix used, sheet numbering scheme>",
  "sheets": [
    {
      "stem": "A-Series_sheet1",
      "single_sheet_pdf": "<abs path>",
      "sheet_id": "A-201",
      "title": "GROUND FLOOR PLAN",
      "discipline": "Architectural",
      "drawing_type": "general_arrangement",
      "confidence": "high",
      "justification": "Plan view at 1:100, full floor extent with rooms labelled and grid lines. No section cuts or schedules dominating the sheet."
    },
    {
      "stem": "E-Series_sheet5",
      "single_sheet_pdf": "<abs path>",
      "sheet_id": "E-501",
      "title": "MAIN SWITCHBOARD - SINGLE LINE DIAGRAM",
      "discipline": "Electrical",
      "drawing_type": "single_line_diagram",
      "confidence": "high",
      "justification": "One-line schematic with switchgear symbols, no spatial scale, distribution lines branching to downstream boards."
    }
  ]
}
```

After classification, show the user a summary table:

```
By type:
  general_arrangement   28
  detail                34
  schedule_sheet        12
  section_view          18
  legend                 6
  ...

By discipline:
  Architectural   42
  Structural      26
  Electrical      31
  Hydraulic       18
  Mechanical      19
  ...

Low-confidence sheets (please review):
  - A-Series_sheet23 (sheet_id: A-307) — classified as 'detail', low confidence
    Justification: Mixed plan and detail content, scale unclear
```

Ask the user to confirm or correct any low-confidence classifications
before proceeding. Override by editing the JSON directly or by replying
with the correction inline.

---

## `symbol_library.json`

Built in Step 6 from every sheet classified as `legend`. For each symbol,
Claude extracts the ID, description, and bbox; then `crop_region.py`
crops a PNG of the symbol from the source PDF.

```json
{
  "extracted_at": "2026-04-15T10:00:00Z",
  "legend_sheets": [
    {"stem": "E-Series_sheet1", "sheet_id": "E-001", "discipline": "Electrical"},
    {"stem": "M-Series_sheet1", "sheet_id": "M-001", "discipline": "Mechanical"}
  ],
  "symbols": [
    {
      "id": "E-GPO-D",
      "name": "GPO Double",
      "description": "Double general-purpose outlet, 10A",
      "discipline": "Electrical",
      "image_path": "0. AI Context/symbol_crops/E-GPO-D.png",
      "source_legend_stem": "E-Series_sheet1",
      "source_legend_sheet_id": "E-001",
      "source_bbox": [120, 540, 380, 580]
    }
  ]
}
```

The IDs are not pattern-matched. Claude assigns them. If the legend gives
a shorthand (e.g. "GPO-D"), use it. Otherwise infer one from the
description.

`source_bbox` is in PDF points, used by `crop_region.py` to produce the
PNG. Long edge is 512px — small enough to be cheap, big enough to be
recognisable.

When the per-sheet analysis runs in Step 7, the relevant subset of
`symbol_library.json` (filtered to the sheet's discipline) is included
in the prompt. Don't include the whole library on every sheet — that's
token waste.

---

## `cross_references.json`

Built in Step 8 from every per-sheet markdown's "Cross-references on this
sheet" section.

```json
{
  "built_at": "2026-04-15T10:00:00Z",
  "convention_detected": "Detail-on-top: '1/A-301' = detail 1 on sheet A-301. Specification references use 'Spec NN NN NN' format (CSI MasterFormat).",
  "references": [
    {
      "source_sheet": "A-201",
      "source_stem": "A-Series_sheet1",
      "source_type": "section_marker",
      "source_label": "1",
      "target_sheet": "A-301",
      "target_stem": "A-Series_sheet8",
      "target_label": "1",
      "target_type": "section_view",
      "resolved": true
    },
    {
      "source_sheet": "A-201",
      "source_stem": "A-Series_sheet1",
      "source_type": "section_marker",
      "source_label": "5",
      "target_sheet": "A-305",
      "target_stem": null,
      "target_label": null,
      "target_type": null,
      "resolved": false,
      "reason": "Target sheet A-305 not in drawing set"
    },
    {
      "source_sheet": "A-201",
      "source_stem": "A-Series_sheet1",
      "source_type": "spec_ref",
      "source_label": "26 05 19",
      "target_sheet": null,
      "target_type": "specification",
      "resolved": null,
      "reason": "Specification cross-references resolved against project.md, not drawings"
    }
  ]
}
```

`source_stem` and `target_stem` link back to the artefacts in
`drawings_split/`. They're how downstream skills navigate.

---

## `coordination_issues.md`

Output of Step 9 — the coordination pass. Markdown, not JSON, because the
audience is a human reading it.

Structure:

```markdown
# Coordination Issues

_Generated 2026-04-15 by project-indexer Step 9. Auto-detected — verify before acting on any of these._

## Summary
<one-paragraph overview: how many issues, severity distribution>

## Unresolved cross-references
<every reference with resolved: false. Format:>

- **A-201 → A-305 (section marker "5")** — target sheet not in drawing set.
  Investigate: A-305 may have been removed, renamed, or is missing from
  this transmittal.

## Symbols used but not defined
<any symbol that appears in per-sheet markdowns that isn't in symbol_library.json>

- **"FW" on H-201, H-202, H-301** — used as a label but not defined in the
  hydraulic legend. Likely "floor waste" by convention; confirm with
  hydraulic engineer.

## Drawing register inconsistencies
<sheets referenced but not present, sheet count mismatches, missing revisions>

## Trade coordination gaps
<inferred from comparing per-sheet markdowns across disciplines>

- **Electrical penetrations vs structural penetration plan**
  - E-201 calls out 6 floor penetrations for cable risers in zones B and C.
  - S-201 (structural penetration plan) shows 4 penetrations in zones B
    and C — quantities and locations don't match.
  - Action: coordinate before slab pour.

- **Hydraulic floor wastes vs architectural set-down zones**
  - H-202 shows floor wastes in WET-01, WET-02, WET-03.
  - A-201 shows set-downs labelled in WET-01 and WET-02 but not WET-03.
  - Action: confirm WET-03 set-down with architect.
```

These are the patterns to look for; Claude finds the actual issues from
the project's content, not from a hard-coded list.

---

## Update to `drawings.md`

The existing `drawings.md` index gets two additions:

1. **`drawing_type` column in the register table** — populated from
   `sheet_classification.json`.
2. **A "Cross-references summary" section near the top** — count of
   resolved vs unresolved references, link to `cross_references.json`
   and `coordination_issues.md`.

Existing structure (drawing register, discipline-by-discipline list with
links to per-sheet `.md` files) is unchanged.
