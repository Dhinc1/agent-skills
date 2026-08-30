#!/bin/bash
# claude-statusline v2.0.0
# Reads Claude Code's statusline JSON from stdin, prints one line.
# No external usage tools: session/weekly limits come from Claude Code's
# own .rate_limits fields, which match claude.ai/settings/usage.
# Requires: bash, jq. Optional: git.
set -uo pipefail

VERSION="2.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/statusline-config.json"

# Debug only when explicitly enabled: STATUSLINE_DEBUG=1 claude
DEBUG_LOG="${STATUSLINE_DEBUG_LOG:-/tmp/statusline_debug.log}"
_dbg() { [ "${STATUSLINE_DEBUG:-0}" = "1" ] && echo "$(date '+%H:%M:%S') $*" >> "$DEBUG_LOG"; return 0; }

input=$(cat)
_dbg "invoked, ${#input} chars in"

# ---------------------------------------------------------------- config ----
CFG='{}'
[ -f "$CONFIG_FILE" ] && CFG=$(cat "$CONFIG_FILE" 2>/dev/null || echo '{}')

IFS=$'\x1f' read -r BAR_LENGTH CTX_WARN_PCT CTX_CRIT_PCT SESS_WARN_PCT WEEK_WARN_PCT \
    ACTIVITY_MIN PROJECTS_PATH NOTIFY_CRIT \
    SHOW_DIR SHOW_MODEL SHOW_EFFORT SHOW_GIT SHOW_CTX SHOW_SESSION SHOW_WEEKLY \
    SHOW_LINES SHOW_COUNT <<EOF
$(jq -r '[
    (.display.bar_length // 10),
    (.thresholds.context_warn_pct // 40),
    (.thresholds.context_critical_pct // 50),
    (.thresholds.session_warn_pct // 70),
    (.thresholds.weekly_warn_pct // 60),
    (.display.session_activity_threshold_minutes // 5),
    (.paths.claude_projects // "~/.claude/projects/"),
    (.alerts.notify_on_critical // true),
    (.sections.directory // true),
    (.sections.model // true),
    (.sections.effort // true),
    (.sections.git_branch // true),
    (.sections.context // true),
    (.sections.session // true),
    (.sections.weekly // true),
    (.sections.lines_changed // true),
    (.sections.active_sessions // true)
] | map(tostring) | join("\u001f")' <<< "$CFG")
EOF

# Colors (config .colors.* overrides; values are raw ANSI escape text like \033[35m)
_color() { jq -r --arg k "$1" --arg d "$2" '.colors[$k] // $d' <<< "$CFG"; }
C_ORANGE=$(printf '%b' "$(_color orange '\033[1;38;5;208m')")
C_RED=$(printf '%b'    "$(_color red    '\033[1;31m')")
C_PINK=$(printf '%b'   "$(_color pink   '\033[38;5;225m')")
C_GREEN=$(printf '%b'  "$(_color green  '\033[38;5;194m')")
C_PURPLE=$(printf '%b' "$(_color purple '\033[35m')")
C_CYAN=$(printf '%b'   "$(_color cyan   '\033[96m')")
C_YELLOW=$(printf '%b' "$(_color yellow '\033[33m')")
C_INVRED=$(printf '%b' '\033[1;97;41m')
C_RESET=$(printf '%b'  '\033[0m')

# ----------------------------------------------------------- input (1 jq) ----
IFS=$'\x1f' read -r CWD MODEL_NAME EFFORT_LEVEL CTX_SIZE CTX_PCT_RAW IN_TOK CC_TOK CR_TOK \
    S5_PCT_RAW S5_RESET W7_PCT_RAW W7_RESET LINES_ADD LINES_DEL SESSION_ID <<EOF
$(jq -r '[
    (.workspace.current_dir // "~"),
    (.model.display_name // ""),
    (.effort.level // ""),
    (.context_window.context_window_size // 200000),
    (.context_window.used_percentage // ""),
    (.context_window.current_usage.input_tokens // 0),
    (.context_window.current_usage.cache_creation_input_tokens // 0),
    (.context_window.current_usage.cache_read_input_tokens // 0),
    (.rate_limits.five_hour.used_percentage // ""),
    (.rate_limits.five_hour.resets_at // ""),
    (.rate_limits.seven_day.used_percentage // ""),
    (.rate_limits.seven_day.resets_at // ""),
    (.cost.total_lines_added // 0),
    (.cost.total_lines_removed // 0),
    (.session_id // "unknown")
] | map(tostring) | join("\u001f")' <<< "$input")
EOF

# Safe defaults if the JSON parse failed or fields were absent
CWD="${CWD:-~}"; MODEL_NAME="${MODEL_NAME:-}"; EFFORT_LEVEL="${EFFORT_LEVEL:-}"
CTX_SIZE="${CTX_SIZE:-200000}"; CTX_PCT_RAW="${CTX_PCT_RAW:-}"
IN_TOK="${IN_TOK:-0}"; CC_TOK="${CC_TOK:-0}"; CR_TOK="${CR_TOK:-0}"
S5_PCT_RAW="${S5_PCT_RAW:-}"; S5_RESET="${S5_RESET:-}"
W7_PCT_RAW="${W7_PCT_RAW:-}"; W7_RESET="${W7_RESET:-}"
LINES_ADD="${LINES_ADD:-0}"; LINES_DEL="${LINES_DEL:-0}"
SESSION_ID="${SESSION_ID:-unknown}"

# Normalize Windows backslashes (printf %b would eat \c etc.), sanitize ANSI
CWD="${CWD//\\//}"
DIR_NAME="${CWD##*/}"
DIR_NAME=$(printf '%s' "$DIR_NAME" | tr -d '\000-\037\177')

# --------------------------------------------------------------- helpers ----
_abbrev_model() {
    local n="$1" p="" v=""
    case "$n" in
        *[Oo]pus*)   p="o" ;;
        *[Ss]onnet*) p="s" ;;
        *[Hh]aiku*)  p="h" ;;
        *[Ff]able*)  p="f" ;;
        *) echo "$n"; return ;;
    esac
    v=$(grep -oE '[0-9]+\.[0-9]+' <<< "$n" | head -1)
    [ -z "$v" ] && v=$(grep -oE '[0-9]+' <<< "$n" | tail -1)
    local sfx=""
    [ "${CTX_SIZE:-0}" -ge 900000 ] 2>/dev/null && sfx="(1m)"
    echo "${p}${v}${sfx}"
}

_abbrev_effort() {
    case "$1" in
        low) echo "lo" ;; medium) echo "md" ;; high) echo "hi" ;;
        xhigh) echo "xh" ;; max) echo "mx" ;; *) echo "" ;;
    esac
}

_bar() { # $1=pct  -> [███░░░░░░░]
    local pct=$1 filled b="[" i
    filled=$(( (pct * BAR_LENGTH + 50) / 100 ))
    [ "$filled" -gt "$BAR_LENGTH" ] && filled=$BAR_LENGTH
    [ "$filled" -lt 0 ] && filled=0
    for ((i=0; i<filled; i++));           do b+="█"; done
    for ((i=filled; i<BAR_LENGTH; i++));  do b+="░"; done
    echo "${b}]"
}

_countdown() { # $1=epoch -> "3h 12m" / "45m" / ""
    local at=$1 now secs
    [ -z "$at" ] && { echo ""; return; }
    now=$(date +%s); secs=$(( at - now ))
    [ "$secs" -le 0 ] && { echo ""; return; }
    if   [ "$secs" -ge 86400 ]; then echo "$(( secs / 86400 ))d $(( (secs % 86400) / 3600 ))h"
    elif [ "$secs" -ge 3600 ];  then echo "$(( secs / 3600 ))h $(( (secs % 3600) / 60 ))m"
    else echo "$(( secs / 60 ))m"; fi
}

_notify() { # one-shot desktop notification, best effort, never blocks
    local msg="$1"
    if command -v osascript >/dev/null 2>&1; then
        osascript -e "display notification \"$msg\" with title \"Claude Code\"" >/dev/null 2>&1 &
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical "Claude Code" "$msg" >/dev/null 2>&1 &
    elif command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "[System.Media.SystemSounds]::Exclamation.Play()" >/dev/null 2>&1 &
    fi
}

# ------------------------------------------------------------ compute ctx ----
if [ -n "$CTX_PCT_RAW" ]; then
    CTX_PCT=$(printf '%.0f' "$CTX_PCT_RAW")
else
    CTX_PCT=$(awk "BEGIN {printf \"%.0f\", (($IN_TOK + $CC_TOK + $CR_TOK) / $CTX_SIZE) * 100}")
fi
CTX_USED_K=$(awk "BEGIN {printf \"%.0f\", ($IN_TOK + $CC_TOK + $CR_TOK) / 1000}")
CTX_SIZE_K=$(awk "BEGIN {printf \"%.0f\", $CTX_SIZE / 1000}")

if   [ "$CTX_PCT" -ge "$CTX_CRIT_PCT" ]; then CTX_STATE="crit"
elif [ "$CTX_PCT" -ge "$CTX_WARN_PCT" ]; then CTX_STATE="warn"
else CTX_STATE="ok"; fi

# One-shot notification per session per crossing; re-arms after compact/restart
MARKER="/tmp/claude-ctx-alert-${SESSION_ID}"
if [ "$CTX_STATE" = "crit" ]; then
    if [ "$NOTIFY_CRIT" = "true" ] && [ ! -f "$MARKER" ]; then
        touch "$MARKER"
        _notify "Context at ${CTX_PCT}% in ${DIR_NAME} — compact or restart"
    fi
else
    rm -f "$MARKER" 2>/dev/null
fi

# effort fallback to settings.json
if [ -z "$EFFORT_LEVEL" ] && [ -f "$HOME/.claude/settings.json" ]; then
    EFFORT_LEVEL=$(jq -r '.effortLevel // empty' "$HOME/.claude/settings.json" 2>/dev/null)
fi

# git branch
GIT_BRANCH=""
if [ "$SHOW_GIT" = "true" ] && [ -d "${CWD}/.git" ]; then
    GIT_BRANCH=$(cd "$CWD" 2>/dev/null && git --no-optional-locks branch --show-current 2>/dev/null)
fi

# active local sessions (this machine only; each machine sees its own)
ACTIVE_SESSIONS=""
if [ "$SHOW_COUNT" = "true" ]; then
    PP="${PROJECTS_PATH/#\~/$HOME}"
    ACTIVE_SESSIONS=$(find "$PP" -name "*.jsonl" -type f -mmin -"$ACTIVITY_MIN" 2>/dev/null | \
        { xargs -I{} dirname {} 2>/dev/null || true; } | sort -u | wc -l | tr -d ' ')
fi

# ------------------------------------------------------------- assemble ----
PARTS=()
[ "$SHOW_DIR" = "true" ]   && PARTS+=("${C_ORANGE}${DIR_NAME}${C_RESET}")
if [ "$SHOW_MODEL" = "true" ] && [ -n "$MODEL_NAME" ]; then
    PARTS+=("${C_CYAN}$(_abbrev_model "$MODEL_NAME")${C_RESET}")
fi
EFFORT_ABBR=$(_abbrev_effort "$EFFORT_LEVEL")
[ "$SHOW_EFFORT" = "true" ] && [ -n "$EFFORT_ABBR" ] && PARTS+=("${C_YELLOW}${EFFORT_ABBR}${C_RESET}")
[ -n "$GIT_BRANCH" ] && PARTS+=("${C_GREEN}${GIT_BRANCH}${C_RESET}")

if [ "$SHOW_CTX" = "true" ]; then
    case "$CTX_STATE" in
        crit) CTX_SEG="${C_INVRED} ⚠ CTX ${CTX_PCT}% — COMPACT/RESTART ${C_RESET} ${C_RED}${CTX_USED_K}k/${CTX_SIZE_K}k${C_RESET}" ;;
        warn) CTX_SEG="${C_ORANGE}${CTX_USED_K}k/${CTX_SIZE_K}k $(_bar "$CTX_PCT") ${CTX_PCT}% ⚠${C_RESET}" ;;
        *)    CTX_SEG="${C_PINK}${CTX_USED_K}k/${CTX_SIZE_K}k $(_bar "$CTX_PCT") ${CTX_PCT}%${C_RESET}" ;;
    esac
    PARTS+=("$CTX_SEG")
fi

if [ "$SHOW_SESSION" = "true" ] && [ -n "$S5_PCT_RAW" ]; then
    S5_PCT=$(printf '%.0f' "$S5_PCT_RAW")
    S5_LEFT=$(_countdown "$S5_RESET")
    S5_COLOR="$C_PURPLE"; [ "$S5_PCT" -ge "$SESS_WARN_PCT" ] && S5_COLOR="$C_ORANGE"
    [ "$S5_PCT" -ge 90 ] && S5_COLOR="$C_RED"
    SEG="5h ${S5_PCT}%"; [ -n "$S5_LEFT" ] && SEG="${SEG} → ${S5_LEFT}"
    PARTS+=("${S5_COLOR}${SEG}${C_RESET}")
fi

if [ "$SHOW_WEEKLY" = "true" ] && [ -n "$W7_PCT_RAW" ]; then
    W7_PCT=$(printf '%.0f' "$W7_PCT_RAW")
    W7_LEFT=$(_countdown "$W7_RESET")
    W7_COLOR=""; [ "$W7_PCT" -ge "$WEEK_WARN_PCT" ] && W7_COLOR="$C_ORANGE"
    [ "$W7_PCT" -ge 85 ] && W7_COLOR="$C_RED"
    SEG="wk ${W7_PCT}%"; [ -n "$W7_LEFT" ] && SEG="${SEG} → ${W7_LEFT}"
    PARTS+=("${W7_COLOR}${SEG}${C_RESET}")
fi

if [ "$SHOW_LINES" = "true" ] && { [ "$LINES_ADD" != "0" ] || [ "$LINES_DEL" != "0" ]; }; then
    PARTS+=("${C_GREEN}+${LINES_ADD}${C_RESET}/${C_RED}-${LINES_DEL}${C_RESET}")
fi

[ "$SHOW_COUNT" = "true" ] && [ -n "$ACTIVE_SESSIONS" ] && PARTS+=("${C_CYAN}×${ACTIVE_SESSIONS}${C_RESET}")

OUT=""
for p in "${PARTS[@]}"; do
    [ -z "$OUT" ] && OUT="$p" || OUT="$OUT | $p"
done
printf '%s\n' "$OUT"
_dbg "rendered ctx=${CTX_PCT}% state=${CTX_STATE}"
