# claude-statusline

One statusline for every machine running Claude Code. No ccusage, no npx, ~60ms per refresh. Session and weekly usage come straight from Claude Code's own `rate_limits` data, so they match claude.ai/settings/usage exactly.

```
coveconstruct | o5(1m) | hi | main | 240k/1000k [██░░░░░░░░] 24% | 5h 44% | wk 62% → 2d
```

## Install (any machine)

```bash
curl -fsSL https://raw.githubusercontent.com/Dhinc1/claude-statusline/main/install.sh | bash
```

Re-run the same command to update. Your local `statusline-config.json` is never overwritten. Requires `jq` (the installer tells you how to get it if missing).

## Context alerts

- **40–60%** context: bar turns orange and says `⚠ COMPACT`.
- **61%+** context: inverted red banner `⚠ CTX 72% — HANDOFF + CLEAR` plus one desktop notification. It fires once per session and re-arms after you compact or restart.

Change thresholds in `~/.claude/statusline/statusline-config.json`:

```json
"thresholds": { "context_warn_pct": 40, "context_critical_pct": 61 }
```

## Segments

| Segment | Source | Notes |
|---|---|---|
| directory | workspace.current_dir | |
| model | model.display_name | `o5(1m)` = Opus 5, 1M context |
| effort | effort.level or settings.json | lo/md/hi/xh/mx |
| git branch | local git | hidden outside repos |
| context | context_window | tokens, bar, %, alerts |
| 5h window | rate_limits.five_hour | % used; orange at 70%, red at 90% |
| weekly | rate_limits.seven_day | % used → whole days to reset; orange at 60%, red at 85% |
| +N/-N | cost.total_lines_* | lines added/removed this session (off by default) |
| ×N | ~/.claude/projects mtimes | active sessions on this machine only (off by default) |

Every segment can be toggled off in `sections`. Rate-limit percentages are shared across all machines on the subscription automatically, because Claude Code reports them per account, not per machine.

## Debugging

```bash
STATUSLINE_DEBUG=1 claude          # logs to /tmp/statusline_debug.log
echo '{}' | ~/.claude/statusline/statusline.sh   # run standalone
```
