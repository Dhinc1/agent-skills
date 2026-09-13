# agent-skills

A catalog of the agent skills and developer tools used across CoveConstruct
work. One repo, one place to clone, one place to update — rather than a
scattering of single-purpose repos.

Two kinds of thing live here, and the split is deliberate:

| Directory | Holds | Consumed by |
|---|---|---|
| `skills/` | **Skills** — instructions an agent loads to do a job. Markdown first; any scripts are deterministic helpers the instructions call. | Claude (and other agents), at task time |
| `tools/` | **Tools** — software you install and run. A real program with an installer and a config file. | You, on a machine |

The test: if the artifact is *read by a model to decide what to do*, it is a skill.
If it is *executed by you to produce a result*, it is a tool.

## The skill standard (R11)

Skills here follow **R11** of the Agent Operations Guide (kept privately in
`Dhinc1/bot-guidelines`): automation
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
| `SKILL.md` | The skill definition — workflow, sheet-summary template, confidence rules, estimating process. |
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

### Tools

**`tools/claude-statusline/`** (v2.0.0) — one statusline for every machine running
Claude Code. Shows folder, model, effort level, git branch, context usage with
escalating compact/handoff warnings, and the 5-hour and weekly rate-limit windows.
Usage figures come from Claude Code's own `rate_limits` data, so they match
claude.ai/settings/usage exactly. No ccusage, no npx, ~60ms per refresh.

Install or update on any machine:

```bash
curl -fsSL https://raw.githubusercontent.com/Dhinc1/agent-skills/main/tools/claude-statusline/install.sh | bash
```

Or from a checkout: `./tools/claude-statusline/install.sh`. Requires `jq`. On
Windows, run it from Git Bash — see the tool's README for why.

| File | What it is |
|---|---|
| `install.sh` | Installer/updater. Copies to `~/.claude/statusline/` and merges the `statusLine` entry into `~/.claude/settings.json` (backing it up first). Never overwrites your config. |
| `statusline.sh` | The statusline itself. Reads Claude Code's JSON on stdin, writes one line. |
| `statusline-config.json` | Default thresholds, colors, and per-segment on/off switches. Installed once, then yours. |
| `README.md` | Segment-by-segment reference, color table, configuration, Windows notes, debugging. |

## Related repos

| Repo | Why it's separate |
|---|---|
| `Dhinc1/bot-guidelines` (private) | The operating doctrine these skills are written against — universal rules R1–R11, host standards, team charter, enforcement. Private: it is work in progress and describes internal infrastructure. |

## Adding to this repo

A new skill goes in `skills/<name>/` with a `SKILL.md` covering all six R11 fields,
plus a row in the Contents index above — an unindexed entry is one nobody will
find. New doctrine goes in `Dhinc1/bot-guidelines`, not here.

A new tool goes in `tools/<name>/` with an installer and a README stating its
requirements.
