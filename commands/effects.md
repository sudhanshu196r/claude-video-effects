---
description: Apply a video effect to a clip (run with no arguments to see all effects)
argument-hint: <effect> [clip.mp4] [--text "..."] [--items "a|b|c"] [--broll other.mp4]
allowed-tools: Bash(python3:*), Bash(python:*), Bash(ffmpeg:*), Bash(ffprobe:*), Bash(ls:*), Read
---

Use the **video-effects** skill to handle this request: `$ARGUMENTS`

Locate the script:

- Plugin install: `${CLAUDE_PLUGIN_ROOT}/skills/video-effects/scripts/effects.py`
- Manual install: `~/.claude/skills/video-effects/scripts/effects.py`

If `$ARGUMENTS` is empty, run `effects.py list`, show the menu, and ask which effect and which clip.
Otherwise follow the skill's workflow: check ffmpeg, resolve the clip, run the effect,
verify a frame, and reply with the output path.
