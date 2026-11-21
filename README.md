# claude-video-effects

One-command video effects for **Claude Code**. Drop in a clip and type:

```
/effects neon-title my-clip.mp4 --text "CLAUDE"
```

Claude runs the effect, checks a frame of the result, and gives you the finished `.mp4`.
Everything runs through **ffmpeg**: no editor, no timeline, no subscriptions.

## Install

**As a Claude Code plugin (recommended)**, inside Claude Code:

```
/plugin marketplace add sudhanshu196r/claude-video-effects
/plugin install video-effects@claude-video-effects
```

**Manual install**

```bash
git clone https://github.com/sudhanshu196r/claude-video-effects.git
cd claude-video-effects && ./install.sh
```

**Requirements:** Python 3.8+ and ffmpeg built with libfreetype (the standard builds from
`brew install ffmpeg`, `winget install ffmpeg` and `sudo apt install ffmpeg` all include it).

## Effects

| `/effects …` | Look | Options |
|---|---|---|
| `documentary` | Chunky pixel mosaic | `--strength` block size |
| `dot-matrix` | LED dot grid in your accent color | `--strength`, `--color` |
| `split` | Talking head on top, b-roll below | `--broll` |
| `neon-title` | Glowing neon headline | `--text`, `--color` |
| `glass-widget` | Frosted-glass card | `--text`, `--subtitle` |
| `checklist` | Items tick off one by one | `--text`, `--items "a\|b\|c"` |
| `timeline` | Progress bar + chapters | `--items "Hook\|Demo\|CTA"` |
| `vhs` | Chroma shift, scanlines, REC timecode | |
| `film` | B&W grain + flicker | |
| `cinematic` | Letterbox + teal/orange grade | |
| `punch-zoom` | Rhythmic punch-in zooms | `--strength` seconds |
| `pip` | B-roll full screen, you in the corner | `--broll` (required) |
| `lower-third` | Sliding name/role bar | `--text`, `--subtitle` |
| `countdown` | 3-2-1 intro | |
| `spotlight` | Sharp center, blurred edges | |

All effects keep your clip's resolution (vertical or horizontal) and audio.
Use `--color "#7C5CFF"` to change the accent and `-o out.mp4` to set the output name.

## Use it without Claude

```bash
python3 skills/video-effects/scripts/effects.py list
python3 skills/video-effects/scripts/effects.py checklist clip.mp4 --items "Record|Run /effects|Post"
```

## Add your own effect

Each effect is one small Python function in `skills/video-effects/scripts/effects.py` that
returns an ffmpeg filter graph. Copy an existing one, rename it, and it appears in `/effects`
automatically. You can also just ask Claude Code to "add a new effect that …".

## Layout

```
.claude-plugin/        plugin + marketplace manifests
commands/effects.md    the /effects slash command
skills/video-effects/  the skill Claude follows + scripts/effects.py
install.sh             manual installer (copies into ~/.claude)
```

## License

MIT
