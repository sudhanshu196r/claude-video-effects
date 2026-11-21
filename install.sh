#!/usr/bin/env bash
# Manual install: copies the skill and the /effects command into ~/.claude
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_HOME:-$HOME/.claude}"

mkdir -p "$DEST/skills" "$DEST/commands"
rm -rf "$DEST/skills/video-effects"
cp -R "$ROOT/skills/video-effects" "$DEST/skills/video-effects"
cp "$ROOT/commands/effects.md" "$DEST/commands/effects.md"
chmod +x "$DEST/skills/video-effects/scripts/effects.py"

echo "Installed video-effects to $DEST"
command -v ffmpeg >/dev/null || echo "Note: ffmpeg not found. Install it (brew install ffmpeg / winget install ffmpeg / sudo apt install ffmpeg)."
echo "Open Claude Code and type /effects"
