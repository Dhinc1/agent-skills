# The concept wiki — the notes/requirements layer (Karpathy's LLM-wiki idea)

The database captures the physical THINGS (entities + instances). The concept wiki captures the RULES, SPECS and REQUIREMENTS about them — regrouped **by concept, not by sheet** — with [[wikilinks]], source-sheet citations, and a standing conflict/lint register.

**Why.** A requirement is scattered: concrete grade lives in the S002 grade schedule + plan callouts + detail notes. Per-sheet, you must re-gather and re-reconcile it on every query — and a capable agent slips under that pressure. The wiki reconciles it ONCE at ingest into one page.

**Validated (blind A/B, same source text, by-sheet vs by-concept):** the concept wiki scored completeness 6/6 vs 5/6, correctness 6/6 vs 4.5/6, **caught conflicts the per-sheet pass garbled**, and used ~40% fewer steps. Reconcile-once beats gather-and-reconcile-under-pressure.

## The three operations (Karpathy)
- **Ingest** — read each sheet's notes/specs; update the relevant concept pages (one note can touch several pages); keep [[wikilinks]] current; cite the source sheet on every fact.
- **Query** — concept/requirement questions go to the wiki (with citations). For granular edge-detail a synthesis may have dropped, fall back to the per-sheet prose / raw text.
- **Lint** — the `index.md` carries a first-class **conflicts / RFI register**: contradictions across sheets, stale or superseded notes, gaps. (In testing this caught the office-slab 25-vs-32 MPa conflict and a slump-tolerance conflict — real design-review value.)

## Pages (one per concept the set warrants)
- Structural: `concrete-grades`, `reinforcement-and-mesh`, `cover-and-durability`, `slabs`, `footings`, `joints`, `subgrade-and-pavement`.
- Services (any): `systems`, `materials`, `fixings-and-supports`, `testing-and-commissioning`, `fire-rating`, `penetrations`, `controls`.
- Plus `index.md` — links the pages with [[wikilinks]] and holds the conflict/lint register.

## Rules
- Don't invent; cite every fact's source sheet; use [[wikilinks]].
- The wiki SUMMARISES — keep the per-sheet prose + raw text for granular fallback (a synthesis can drop edge detail; cite so you can recover it).
- The conflict/lint register is an output, not a side-note — it's where a design-review consistency check lives.
- Biggest wins compound at SCALE (hundreds of sheets) and on REPEATED queries (reconcile once, not every time).
