#!/bin/bash
# claude-statusline installer/updater
# From a checkout:   ./install.sh
# From anywhere:     curl -fsSL https://raw.githubusercontent.com/Dhinc1/agent-skills/main/tools/claude-statusline/install.sh | bash
# Re-running updates the script in place. Your config is never overwritten.
set -euo pipefail

REPO_RAW="${STATUSLINE_REPO:-https://raw.githubusercontent.com/Dhinc1/agent-skills/main/tools/claude-statusline}"
DEST="$HOME/.claude/statusline"
SETTINGS="$HOME/.claude/settings.json"

command -v jq >/dev/null 2>&1 || {
    echo "ERROR: jq is required. Install it first:"
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install -y jq"
    echo "  Windows: winget install jqlang.jq  (run installer from Git Bash after)"
    exit 1
}

mkdir -p "$DEST"

# Prefer local files when running from a checkout; otherwise fetch from the repo
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"
if [ -n "$SRC_DIR" ] && [ -f "$SRC_DIR/statusline.sh" ]; then
    cp "$SRC_DIR/statusline.sh" "$DEST/statusline.sh"
    [ -f "$DEST/statusline-config.json" ] || cp "$SRC_DIR/statusline-config.json" "$DEST/statusline-config.json"
    echo "Installed from local checkout."
else
    curl -fsSL "$REPO_RAW/statusline.sh" -o "$DEST/statusline.sh"
    if [ ! -f "$DEST/statusline-config.json" ]; then
        curl -fsSL "$REPO_RAW/statusline-config.json" -o "$DEST/statusline-config.json"
    fi
    echo "Installed from $REPO_RAW"
fi
chmod +x "$DEST/statusline.sh"

# Wire up ~/.claude/settings.json (backup first, merge with jq)
mkdir -p "$HOME/.claude"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
cp "$SETTINGS" "$SETTINGS.bak"
# Windows shells (PowerShell) will not execute a bare .sh path, so prefix bash there.
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
        SL_PATH="$DEST/statusline.sh"
        command -v cygpath >/dev/null 2>&1 && SL_PATH="$(cygpath -m "$SL_PATH")"
        SL_CMD="bash \"$SL_PATH\""
        ;;
    *)                    SL_CMD="$DEST/statusline.sh" ;;
esac

jq --arg cmd "$SL_CMD" \
   '.statusLine = {type: "command", command: $cmd, padding: 0}' \
   "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"

VER=$(grep -m1 '^VERSION=' "$DEST/statusline.sh" | cut -d'"' -f2)
echo "claude-statusline v${VER} -> $DEST/statusline.sh"
echo "settings.json updated (backup at $SETTINGS.bak)"
echo "Restart Claude Code or open a new session to see it."
