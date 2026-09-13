# agent-skills

A catalog of the agent skills and developer tools used across CoveConstruct work.
One repo, one place to clone, one place to update — rather than a scattering of
single-purpose repos.

Two kinds of thing live here, and the split is deliberate:

| Directory | Holds | Consumed by |
|---|---|---|
| `skills/` | **Skills** — instructions an agent loads to do a job. Markdown first; any scripts are deterministic helpers the instructions call. | Claude (and other agents), at task time |
| `tools/` | **Tools** — software a human installs and runs. Real programs with an installer and a config file. | You, on a machine |

The test: if the artifact is *read by a model to decide what to do*, it is a skill.
If it is *executed to produce a result*, it is a tool.

## The skill standard (R11)

Skills here follow **R11** of the Agent Operations Guide (`AGENT-OPERATIONS-GUIDE.md`, in the botguide repo):
automation graduates through demonstrated reliability — manual task → corrected
task → frozen skill → scheduled routine → team. Never skip a rung, and never
schedule attempt #1. A method is frozen into a skill only after it has survived
correction.

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

## Adding to this repo

A new skill goes in `skills/<name>/` with a `SKILL.md` that covers all six R11
fields. A new tool goes in `tools/<name>/` with an installer and a README that
states its requirements. In both cases add a row to the Contents index above —
an unindexed entry is one nobody will find.
