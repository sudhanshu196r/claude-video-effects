---
name: video-effects
description: Apply a named visual effect to a video clip (pixel mosaic, dot-matrix, split screen, neon title, glass widget, checklist, timeline, VHS, film, cinematic, punch-zoom, picture-in-picture, lower-third, countdown, spotlight). Use when the user types /effects, asks to add an effect/overlay/look to a video, or names one of these effects.
---

# Video effects

All effects run through one script that wraps ffmpeg:

```
python3 <this skill's folder>/scripts/effects.py <effect> <input> [options]
```

`<this skill's folder>` is the directory this SKILL.md lives in. That's usually
`${CLAUDE_PLUGIN_ROOT}/skills/video-effects` when installed as a plugin, or
`~/.claude/skills/video-effects` when installed with `install.sh`.

## Workflow

1. **Check ffmpeg** with `ffmpeg -version`. If it's missing, tell the user the install command
   for their OS (`brew install ffmpeg`, `winget install ffmpeg`, `sudo apt install ffmpeg`)
   and stop.
2. **Find the clip.** Use the path the user gave. If none was given, look for the newest
   `.mp4`/`.mov` in the current folder and confirm it with the user.
3. **Pick the effect.** If the user gave no effect name, run `effects.py list` and show the
   menu. If their wording is fuzzy ("make it look old"), map it to the closest effect
   (old → `film` or `vhs`) and say which one you picked.
4. **Fill in options from the request.** Text the user mentions goes to `--text` /
   `--subtitle`, lists go to `--items "a|b|c"`, and a second clip goes to `--broll`.
   Don't ask for options that have sensible defaults.
5. **Run it.** The script prints the output path (`<input>_<effect>.mp4` by default).
6. **Verify.** Grab a frame from the middle of the output
   (`ffmpeg -ss <mid> -i out.mp4 -frames:v 1 check.png`), look at it, and fix anything wrong
   before reporting back. Give the user the output path in one line.

Effects can be chained by running the script again on the previous output,
e.g. `cinematic`, then `lower-third`.

## Effects

| Effect | What it does | Options |
|---|---|---|
| `documentary` | Chunky pixel mosaic | `--strength` block size (24) |
| `dot-matrix` | LED dot grid in the accent color | `--strength` cell px (14), `--color` |
| `split` | Talking head on top, b-roll below | `--broll` (optional) |
| `neon-title` | Glowing neon headline | `--text`, `--color` |
| `glass-widget` | Frosted-glass card with title + subtitle | `--text`, `--subtitle` |
| `checklist` | Card whose items tick off over time | `--text` title, `--items` |
| `timeline` | Progress bar with chapter markers | `--items` chapters |
| `vhs` | Chroma shift, noise, scanlines, REC + timecode | — |
| `film` | B&W grain, flicker, vignette | — |
| `cinematic` | Letterbox + teal/orange grade | — |
| `punch-zoom` | Rhythmic punch-in zooms | `--strength` seconds (2) |
| `pip` | B-roll full screen, you in a corner | `--broll` (required) |
| `lower-third` | Sliding name/role bar | `--text` name, `--subtitle` role |
| `countdown` | 3-2-1 intro | — |
| `spotlight` | Sharp center, blurred dark edges | — |

Global options: `-o out.mp4`, `--color "#FF7A1A"`, `--dry-run` (prints the ffmpeg command
without running it).

## Adding a new effect

Add a function decorated with `@effect("name", "help", "options")` in `scripts/effects.py`.
It gets a context `c` (`c.w`, `c.h`, `c.dur`, `c.args`, `c.color`, and `c.dt(text, **drawtext_opts)`
for safe text). It returns `(filter_complex, extra_ffmpeg_inputs)`, where the graph reads `[0:v]`
and writes `[v]`. Audio is handled automatically. Then add a row to the table above.
