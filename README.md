# agent-skills

A catalog of the agent skills and operating doctrine used across CoveConstruct
work. One repo, one place to clone, one place to update — rather than a
scattering of single-purpose repos.

**This repo is private.** Anything that needs to be fetched by an unauthenticated
client — an installer one-liner, a `raw.githubusercontent.com` URL — cannot live
here; it belongs in its own public repo. See [Related repos](#related-repos).

Two kinds of thing live here, and the split is deliberate:

| Directory | Holds | Consumed by |
|---|---|---|
| `skills/` | **Skills** — instructions an agent loads to do a job. Markdown first; any scripts are deterministic helpers the instructions call. | Claude (and other agents), at task time |
| `guidelines/` | **Doctrine** — how agent work is run at all: universal rules, host standards, team charters, and the enforcement that backs them. | You, when deciding how to route and run work |

The test: if the artifact is *read by a model to decide what to do*, it is a skill.
If it is *read by a human to decide how agents are run*, it is doctrine.

## The skill standard (R11)

Skills here follow **R11** of `guidelines/AGENT-OPERATIONS-GUIDE.md`: automation
graduates through demonstrated reliability — manual task → corrected task →
frozen skill → scheduled routine → team. Never skip a rung, and never schedule
attempt #1. A method is frozen into a skill only after it has survived correction.

A hardened skill states six things:

1. **When to use it** — the trigger conditions, specific enough that an agent
   recognises the situation without being told.
2. **Required inputs and access** — what data, files, credentials, and permissions
   the run needs before it starts.
3. **The exact sequence** — the ordered steps, not a description of the general idea.
4. **How to validate the result** — the check that distinguishes a real success
   from a plausible-looking failure.
5. **What to return** — the shape of the output the caller receives.
6. **What requires approval** — the steps an agent must stop and ask about rather
   than perform.

A skill missing any of the six is not frozen yet; it is still a corrected task.

## Contents

### Skills

**`skills/land-plan-estimator/`** — reads and estimates from civil land-development
plan sets (multi-sheet PDFs) without dumping the raw PDF into context. Preprocesses
a set into per-sheet text and rasters, builds a routing index, then estimates
against a pay-item catalog with explicit confidence labelling (plan-stated vs.
measured-off-linework).

| File | What it is |
|---|---|
| `SKILL.md` | The skill definition — workflow, sheet-summary template, confidence rules, estimating process. Declares itself as `land-plan-reader`. |
| `scripts/preprocess_plans.py` | Deterministic prep. Splits a plan set into per-sheet `.txt`, `.png`, optional `.pdf`, and a `manifest.json`. Requires `pymupdf`. |
| `references/pay_items.md` | Pay-item catalog by division, with unit of measure and takeoff basis. Built from real bids; enrich as projects add items. |
| `references/scope_kickoff.md` | Pre-estimate scoping template — which divisions to include, segregated scopes, exclusions. |
| `README.md` | Human-facing overview of the skill. |

**`skills/pdf-markup/`** — marks up PDFs the way you would in Bluebeam: highlights,
boxes, revision clouds, callouts, arrows, stamps, and redactions, produced as real
editable PDF annotations rather than a flattened image. It renders the page to an
image with a coordinate grid first, so it can *see* the sheet before placing
anything — which also makes it a visual inspection tool for scanned drawings with
no text layer (count the fixtures, check a dimension, and mark each one as it goes).
The source file is never modified; redaction is the one destructive op and it
confirms first.

| File | What it is |
|---|---|
| `SKILL.md` | The skill definition — the render-first loop, coordinate system, the markup spec format, and every op type. |
| `scripts/pdf_markup.py` | The single script behind it: `info`, `text`, `render`, `list`, `apply`. Requires `pymupdf` and `pillow`. |

### Guidelines

**`guidelines/`** — the operating doctrine. Start with `AGENT-OPERATIONS-GUIDE.md`;
the rest are its companions.

| File | What it is |
|---|---|
| `AGENT-OPERATIONS-GUIDE.md` | The core guide (v0.2) — universal rules R1–R11, the routing rubric for deciding what runs where, kill criteria, and the lesson pipeline. Every rule cites the incident or source that earned it. |
| `HERMES-AGENT-OPERATING-STANDARD.md` | Hermes mechanics — how the standard is implemented on that host. |
| `HERMES-STANDING-TEAM-CHARTER.md` | Standing team roles, their metrics, and sunset criteria. |
| `apply-enforcement.sh` | Moves rules from prose into the control layer, per R1. |
| `regression-suite/` | The gatekeeper for model tier changes — a model enters or changes tier only on a full pass, never on "feels smarter". |
| `README.md` | Overview of the doctrine set. |

## Related repos

| Repo | Why it's separate |
|---|---|
| [`Dhinc1/claude-statusline`](https://github.com/Dhinc1/claude-statusline) (public) | The Claude Code statusline. Public because its installer is fetched by `curl` from raw.githubusercontent.com, which requires an unauthenticated-readable repo. |

## Adding to this repo

A new skill goes in `skills/<name>/` with a `SKILL.md` covering all six R11 fields.
New doctrine goes in `guidelines/`. In both cases add a row to the Contents index
above — an unindexed entry is one nobody will find.

Before adding anything, ask whether it must be fetchable without credentials. If
so, it needs its own public repo and a row in Related repos instead.
