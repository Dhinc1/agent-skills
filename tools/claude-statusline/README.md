# claude-statusline

One statusline for every machine running Claude Code. No ccusage, no npx, ~60ms per refresh. Session and weekly usage come straight from Claude Code's own `rate_limits` data, so they match claude.ai/settings/usage exactly.

```
statusline | o5(1m) | hi | main | 240k/1000k [██░░░░░░░░] 24% | 5h 44% | wk 62% → 2d
```

## Install (any machine)

```bash
curl -fsSL https://raw.githubusercontent.com/Dhinc1/agent-skills/main/tools/claude-statusline/install.sh | bash
```

Re-run the same command to update. Your local `statusline-config.json` is never overwritten. Requires `jq` (the installer tells you how to get it if missing).

On Windows, run this from **Git Bash**, not PowerShell or cmd. The installer detects the platform and writes the correct command into `settings.json` for it — see [Windows notes](#windows-notes).

Restart Claude Code, or open a new session, to see it.

## What each segment shows

Using the example above, left to right:

### `statusline` — current folder

The name of the folder you're working in — just the last part of the path, not the whole thing. Useful when several Claude Code windows are open and you need to know which project each one is in.

### `o5(1m)` — model and context size

- `o` = Opus. (`s` = Sonnet, `h` = Haiku, `f` = Fable)
- `5` = version. Sonnet 4.5 shows as `s4.5`.
- `(1m)` = you're on the 1-million-token context window. Only appears on 1M models; a standard 200k model shows just `o5`.

### `hi` — effort level

How hard the model is thinking: `lo` / `md` / `hi` / `xh` / `mx` (low, medium, high, xhigh, max).

This is a usage lever, not just a readout. Anthropic's [usage limits documentation](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work) confirms effort level directly affects how fast you consume your allowance — dropping to `md` for routine work meaningfully slows the burn.

### `main` — git branch

The branch you're on. This segment disappears entirely when you're not in a git repo.

### `240k/1000k [██░░░░░░░░] 24%` — context usage

How full the conversation's memory is: 240,000 tokens used of 1,000,000 available. The bar and the percentage say the same thing, one visually and one exactly.

This is the segment that actually warns you, and it changes appearance in three bands:

| Range | Appearance | Meaning |
|---|---|---|
| 0–39% | pink, plain | fine, ignore it |
| **40–60%** | orange, `⚠ COMPACT` | getting full — compact soon |
| **61–100%** | white on red, `⚠ CTX 74% — HANDOFF + CLEAR` | act now: run handoff, then clear |

At 61% the bar is replaced by the banner, and you also get one desktop notification (a system alert sound on Windows). It fires **once** per session, then re-arms after you compact or restart, so it won't nag.

Why it matters: as context fills, the model loses track of earlier parts of the conversation. It also costs you more — long conversations that trigger automatic context management consume more of your usage limit, so clearing out at the right time protects both answer quality and your weekly budget.

### `5h 44%` — 5-hour usage window

You've used 44% of your rolling 5-hour allowance. Colors: normal → orange at 70% → red at 90%.

### `wk 62% → 2d` — weekly usage window

62% of the 7-day allowance used, resetting in 2 days. Rounded to whole days; under 24 hours it reads `<1d`. Colors: normal → orange at 60% → red at 85%.

Both usage figures come from Claude Code's own account data, so they **match claude.ai/settings/usage exactly** and are shared across all your machines automatically — burn budget on one box and the others show it too. That's why this needs no external usage tooling.

Note that these cover **all** Claude surfaces, not just Claude Code: claude.ai in the browser and Claude Desktop count against the same limit.

## What it looks like

**Fresh session** — everything quiet
```
statusline | o5(1m) | hi | main | 80k/1000k [█░░░░░░░░░] 8% | 5h 12% | wk 34% → 5d
```

**Normal working**
```
statusline | o5(1m) | hi | main | 240k/1000k [██░░░░░░░░] 24% | 5h 44% | wk 62% → 2d
```

**40–60% context** — orange, asking you to compact
```
statusline | o5(1m) | hi | main | 470k/1000k [█████░░░░░] 47% ⚠ COMPACT | 5h 58% | wk 62% → 2d
```

**61%+ context** — bar replaced by a red banner
```
statusline | o5(1m) | hi | main |  ⚠ CTX 74% — HANDOFF + CLEAR  740k/1000k | 5h 71% | wk 88% → 2d
```

In that last one both usage figures have colored up as well — `5h 71%` orange, `wk 88%` red. Banner plus red weekly is the signal to hand off, clear, and consider dropping effort to `md` for a while.

## Colors

| Segment | Colour |
|---|---|
| folder | orange |
| model | bright cyan |
| effort | yellow |
| branch | pale green |
| context | pink → orange (40%) → white on red (61%) |
| 5h | purple → orange (70%) → red (90%) |
| weekly | plain → orange (60%) → red (85%) |

All of these are overridable under `colors` in the config.

## Configuration

Everything lives in `~/.claude/statusline/statusline-config.json`.

Thresholds:

```json
"thresholds": {
  "context_warn_pct": 40,
  "context_critical_pct": 61,
  "session_warn_pct": 70,
  "weekly_warn_pct": 60
}
```

Every segment can be switched off individually under `sections` — set any to `false` and it disappears from the line:

```json
"sections": {
  "directory": true,
  "model": true,
  "effort": true,
  "git_branch": true,
  "context": true,
  "session": true,
  "weekly": true
}
```

Two further segments ship disabled by default: `lines_changed` (`+412/-88`, lines added and removed this session) and `active_sessions` (`×2`, Claude Code sessions running on this machine). Set either to `true` to bring it back.

Desktop notification on critical context can be turned off with `"alerts": { "notify_on_critical": false }`.

## Windows notes

PowerShell will not execute a bare `.sh` path — it treats the file as a document and refuses with *"Cannot run a document in the middle of a pipeline"*, so the statusline silently never renders. The installer handles this: on Windows it writes

```json
"command": "bash \"C:/Users/you/.claude/statusline/statusline.sh\""
```

while Linux and macOS get the bare path, which their shebang handles. You don't need to edit anything per machine — the same curl command does the right thing everywhere.

Git Bash supplies `bash`, `curl`, and `cygpath`, so install [Git for Windows](https://git-scm.com/download/win) first, then `winget install jqlang.jq` for jq.

## Debugging

```bash
STATUSLINE_DEBUG=1 claude          # logs to /tmp/statusline_debug.log
echo '{}' | ~/.claude/statusline/statusline.sh   # run standalone
```

To see how a given state renders, pipe sample JSON in:

```bash
jq -n '{workspace:{current_dir:"/tmp/demo"},
        model:{display_name:"Claude Opus 5"},
        effort:{level:"high"},
        context_window:{context_window_size:1000000, used_percentage:74,
          current_usage:{input_tokens:740000}},
        rate_limits:{five_hour:{used_percentage:71},
                     seven_day:{used_percentage:88}}}' \
  | ~/.claude/statusline/statusline.sh
```

## Requirements

`bash` and `jq`. `git` optional, for the branch segment.
