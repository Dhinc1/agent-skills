# Trade Coverage Checklists

Per-trade **starting-point** lists of the quantities a complete bill of quantities usually needs. Their single job is to stop the takeoff **under-extracting** — i.e. measuring the obvious items and silently missing whole categories. They are used in **Step 1 (work out what to measure)**: open the file(s) for the trade(s) in scope and work through every category, deciding for *this* project whether each line is present, absent, or needs splitting.

**Read the checklist for each in-scope trade before recommending the quantity list.** Don't rely on recall — open the file. Missing a category here is the exact failure these files exist to prevent.

| Trade in scope | File |
|---|---|
| Structural — concrete, reinforcement, formwork | `structural.md` |
| Architectural / finishes — walls, floors, ceilings, doors, windows, roof, external | `architectural.md` |
| Civil / external — earthworks, pavement, drainage, sewer/water, temp works, services, line marking, fencing, landscaping | `civil.md` |
| Electrical — containment, conduit, cables, lighting, boards, power, fire detection, data, earthing | `electrical.md` |
| Mechanical / HVAC — plant, AHUs, terminals, ductwork, air distribution, pipework, fans, BMS, T&C | `hvac.md` |
| Hydraulic / plumbing — fixtures, tapware, cold/hot water, sanitary, stormwater, fire, gas, T&C | `plumbing.md` |

## What these are, and what they are NOT

- **They ARE** a coverage prompt: a known-good spine of categories and primary items per trade, drawn from real estimating templates, plus one worked assembly per file showing how a primary expands into its secondaries.
- **They are NOT exhaustive, and NOT a script to copy out.** Every project carries items no generic list anticipates. After working through the checklist, scan the actual drawings and schedules for anything extra and add it. Equally, a category with nothing on the drawings is recorded as a one-line "not in scope" note, never silently dropped.
- **They list PRIMARIES.** The components, consumables, labour, and plant are **secondaries** derived via assemblies (`../derivation_library.md`). The checklist tells you *what to measure*; the derivation library tells you *what each measurement drives*.

These complement `../derivation_library.md`: the checklists answer "what quantities exist on this trade?", the derivation library answers "what does each primary derive into, and what's the ratio?".
