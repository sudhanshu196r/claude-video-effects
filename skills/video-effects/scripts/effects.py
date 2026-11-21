#!/usr/bin/env python3
"""
claude-video-effects — one-command video effects powered by ffmpeg.

Usage:
  effects.py list
  effects.py <effect> <input.mp4> [-o out.mp4] [--text "..."] [--subtitle "..."]
                                   [--items "a|b|c"] [--broll other.mp4]
                                   [--color "#FF7A1A"] [--strength N]

Every effect keeps the input's resolution and audio. Works on vertical (9:16)
and horizontal clips. Requires ffmpeg with libfreetype (drawtext).
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------- helpers

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/DejaVuSans-Bold.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
]


def find_font():
    env = os.environ.get("EFFECTS_FONT")
    if env and os.path.exists(env):
        return env
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f
    if shutil.which("fc-match"):
        try:
            out = subprocess.check_output(
                ["fc-match", "-f", "%{file}", "sans:bold"], text=True
            ).strip()
            if out and os.path.exists(out):
                return out
        except subprocess.CalledProcessError:
            pass
    return None


def ff_path(p):
    """Escape a path for use inside an ffmpeg filter argument."""
    p = p.replace("\\", "/")
    if platform.system() == "Windows" and len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p.replace("'", "\\'")


def probe(path):
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,width,height,r_frame_rate:format=duration",
            "-of", "json", path,
        ],
        text=True,
    )
    data = json.loads(out)
    v = next(s for s in data["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])
    num, den = v.get("r_frame_rate", "30/1").split("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    return {
        "w": int(v["width"]),
        "h": int(v["height"]),
        "fps": fps or 30.0,
        "dur": float(data["format"].get("duration", 0) or 0),
        "audio": has_audio,
    }


class Ctx:
    def __init__(self, args, info):
        self.args = args
        self.w, self.h = info["w"], info["h"]
        self.dur = info["dur"] or 10.0
        self.fps = info["fps"]
        self.font = find_font()
        self.tmp = tempfile.mkdtemp(prefix="fx_")
        self.color = (args.color or "#FF7A1A").lstrip("#")
        self.s = min(self.w, self.h)  # base unit for sizing
        # DejaVu has ✓ and ▶; most system fonts don't, so we fall back gracefully.
        self.has_glyphs = bool(self.font and "dejavu" in self.font.lower())

    def textfile(self, text):
        fd, path = tempfile.mkstemp(dir=self.tmp, suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return ff_path(path)

    def dt(self, text, **kw):
        """Build a drawtext filter. Text is passed via a file, so no escaping issues."""
        opts = [f"textfile='{self.textfile(text)}'"]
        if self.font:
            opts.append(f"fontfile='{ff_path(self.font)}'")
        for k, v in kw.items():
            opts.append(f"{k}={v}")
        return "drawtext=" + ":".join(opts)


def even(n):
    n = int(round(n))
    return n - (n % 2)


# ---------------------------------------------------------------- effects
# Each effect returns (filter_complex, extra_inputs). The graph reads [0:v]
# and must output [v].

EFFECTS = {}


def effect(name, help_text, uses=""):
    def deco(fn):
        EFFECTS[name] = {"fn": fn, "help": help_text, "uses": uses}
        return fn
    return deco


@effect("documentary", "Chunky pixel-mosaic look (retro doc / censor vibe)", "--strength (block size, default 24)")
def fx_documentary(c):
    b = c.args.strength or 24
    sw, sh = max(2, c.w // b), max(2, c.h // b)
    return (
        f"[0:v]scale={sw}:{sh}:flags=area,scale={c.w}:{c.h}:flags=neighbor,"
        f"eq=contrast=1.15:saturation=1.2[v]"
    ), []


@effect("dot-matrix", "LED dot-matrix / halftone grid in an accent color", "--strength (cell px, default 14), --color")
def fx_dotmatrix(c):
    cell = c.args.strength or 14
    on = max(2, int(cell * 0.72))
    r, g, b = (int(c.color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    sw, sh = max(2, c.w // cell), max(2, c.h // cell)
    return (
        f"[0:v]scale={sw}:{sh}:flags=area,scale={c.w}:{c.h}:flags=neighbor,"
        f"format=gray,eq=contrast=1.4,"
        f"geq=lum='if(lt(mod(X\\,{cell})\\,{on})*lt(mod(Y\\,{cell})\\,{on})\\,lum(X\\,Y)\\,0)',"
        f"format=rgb24,colorchannelmixer=rr={r:.3f}:rg=0:rb=0:gr=0:gg={g:.3f}:gb=0:br=0:bg=0:bb={b:.3f},"
        f"format=yuv420p[v]"
    ), []


@effect("split", "Kallaway-style split: talking head on top, b-roll below", "--broll other.mp4 (optional; else a zoomed crop)")
def fx_split(c):
    half = even(c.h / 2)
    top = f"[0:v]scale={c.w}:-2,crop={c.w}:{half}[top]"
    if c.args.broll:
        bottom = (f"[1:v]scale={c.w}:{half}:force_original_aspect_ratio=increase,"
                  f"crop={c.w}:{half},setsar=1[bot]")
        extra = ["-stream_loop", "-1", "-i", c.args.broll]
    else:
        bottom = (f"[0:v]crop=iw*0.6:ih*0.3:iw*0.2:ih*0.45,scale={c.w}:{half},"
                  f"eq=saturation=1.3,setsar=1[bot]")
        extra = []
    line = max(4, even(c.s * 0.008))
    return (
        f"{top};{bottom};[top][bot]vstack=inputs=2,scale={c.w}:{even(c.h)},"
        f"drawbox=x=0:y={half - line // 2}:w=iw:h={line}:color=0x{c.color}@1:t=fill[v]"
    ), extra


@effect("neon-title", "Big glowing neon title over the clip", "--text (default 'CLAUDE'), --color")
def fx_neon(c):
    text = c.args.text or "CLAUDE"
    size = int(c.w / max(4, len(text)) * 1.5)
    size = min(size, int(c.h * 0.12))
    y = int(c.h * 0.10)
    base = dict(fontsize=size, x="(w-text_w)/2", y=y)
    glow = c.dt(text, fontcolor=f"0x{c.color}", **base)
    core = c.dt(text, fontcolor="white", borderw=max(2, size // 30),
                bordercolor=f"0x{c.color}", **base)
    blur = max(6, size // 5)
    return (
        f"[0:v]eq=brightness=-0.05[bg];"
        f"color=black@0:s={c.w}x{c.h},format=rgba,{glow},gblur=sigma={blur},"
        f"colorchannelmixer=aa=1.0[g1];"
        f"[g1]split[g1a][g1b];[g1b]gblur=sigma={blur * 2}[g2];"
        f"[bg][g2]overlay=shortest=1[b1];[b1][g1a]overlay[b2];"
        f"[b2]{core}[v]"
    ), []


@effect("glass-widget", "Frosted-glass card with a headline + subtitle", "--text, --subtitle")
def fx_glass(c):
    text = c.args.text or "Built with Claude"
    sub = c.args.subtitle or "one command, zero editing"
    cw, ch = even(c.w * 0.82), even(c.h * 0.16)
    cx, cy = even((c.w - cw) / 2), even(c.h * 0.62)
    t_size = int(min(ch * 0.30, cw * 0.9 / (max(1, len(text)) * 0.6)))
    s_size = int(min(ch * 0.18, t_size * 0.65, cw * 0.9 / (max(1, len(sub)) * 0.55)))
    radius = max(8, int(ch * 0.18))
    # rounded-rect alpha mask
    mask = (
        f"color=white:s={cw}x{ch},format=gray,"
        f"geq=lum='if(gt(pow(max(0\\,max({radius}-X\\,X-({cw}-{radius})))\\,2)+"
        f"pow(max(0\\,max({radius}-Y\\,Y-({ch}-{radius})))\\,2)\\,{radius * radius})\\,0\\,255)'[m]"
    )
    title = c.dt(text, fontsize=t_size, fontcolor="white",
                 x=f"{cx}+(({cw})-text_w)/2", y=f"{cy}+{int(ch * 0.18)}")
    subt = c.dt(sub, fontsize=s_size, fontcolor="white@0.85",
                x=f"{cx}+(({cw})-text_w)/2", y=f"{cy}+{int(ch * 0.62)}")
    return (
        f"[0:v]split[a][b];"
        f"[b]crop={cw}:{ch}:{cx}:{cy},gblur=sigma=18,eq=brightness=0.12:saturation=0.8,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.12:t=fill[glass];"
        f"{mask};[glass][m]alphamerge[gm];"
        f"[a][gm]overlay={cx}:{cy}:enable='gte(t,0.3)',{title}:enable='gte(t,0.5)',"
        f"{subt}:enable='gte(t,0.8)'[v]"
    ), []


@effect("checklist", "Checklist card; items tick off one by one", "--text (title), --items 'a|b|c'")
def fx_checklist(c):
    title = c.args.text or "Today's plan"
    items = [i.strip() for i in (c.args.items or "Record the clip|Run /effects|Post it").split("|") if i.strip()]
    n = len(items)
    pad = int(c.w * 0.07)
    row = int(c.h * 0.045)
    t_size, i_size = int(row * 0.75), int(row * 0.55)
    bw, bh = even(c.w - 2 * pad), even(row * (n + 1.6))
    bx, by = pad, even(c.h * 0.12)
    span = max(1.0, c.dur * 0.8)
    step = span / (n + 1)
    f = [
        f"[0:v]drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black@0.55:t=fill",
        f"drawbox=x={bx}:y={by}:w={bw}:h={max(4, row // 8)}:color=0x{c.color}@1:t=fill",
        c.dt(title, fontsize=t_size, fontcolor="white", x=bx + pad // 2, y=by + int(row * 0.4)),
    ]
    box = int(i_size * 1.1)
    for k, item in enumerate(items):
        y = by + int(row * (1.5 + k))
        t_on = step * (k + 1)
        bx2 = bx + pad // 2
        f.append(f"drawbox=x={bx2}:y={y}:w={box}:h={box}:color=white@0.9:t={max(2, box // 10)}")
        f.append(f"drawbox=x={bx2}:y={y}:w={box}:h={box}:color=0x{c.color}@1:t=fill:enable='gte(t,{t_on:.2f})'")
        if c.has_glyphs:
            f.append(c.dt("✓", fontsize=int(box * 0.9), fontcolor="white",
                          x=bx2 + box // 5, y=y + box // 20, enable=f"'gte(t,{t_on:.2f})'"))
        f.append(c.dt(item, fontsize=i_size, x=bx2 + int(box * 1.6), y=y + (box - i_size) // 2,
                      fontcolor="white"))
        # strike-through once ticked
        f.append(f"drawbox=x={bx2 + int(box * 1.6)}:y={y + box // 2}:w={int(len(item) * i_size * 0.55)}:"
                 f"h={max(2, i_size // 12)}:color=white@0.8:t=fill:enable='gte(t,{t_on:.2f})'")
    return ",".join(f) + "[v]", []


@effect("timeline", "Progress bar with chapter markers along the bottom", "--items 'Intro|Demo|Outro' (chapters)")
def fx_timeline(c):
    chapters = [i.strip() for i in (c.args.items or "Hook|Demo|Result").split("|") if i.strip()]
    n = len(chapters)
    pad = int(c.w * 0.06)
    bar_h = max(6, even(c.h * 0.008))
    y = even(c.h * 0.90)
    bw = c.w - 2 * pad
    size = int(c.h * 0.018)
    D = max(c.dur, 0.1)
    f = [
        f"[0:v]drawbox=x={pad}:y={y}:w={bw}:h={bar_h}:color=white@0.3:t=fill",
    ]
    base = ",".join(f)
    for k, name in enumerate(chapters):
        x = pad + int(bw * k / n)
        t0 = D * k / n
        base += f",drawbox=x={x}:y={y - bar_h}:w={max(3, bar_h // 2)}:h={bar_h * 3}:color=white@0.9:t=fill"
        base += "," + c.dt(name, fontsize=size, x=x + bar_h, y=y - int(size * 1.9),
                           fontcolor="white",
                           alpha=f"'if(gte(t,{t0:.2f}),1,0.45)'")
    # A full-width fill bar slides into a transparent strip, which clips it.
    fill = (f"color=black@0:s={bw}x{bar_h}:r={c.fps:.3f}:d={D:.3f},format=rgba[strip];"
            f"color=0x{c.color}:s={bw}x{bar_h}:r={c.fps:.3f}:d={D:.3f},format=rgba[fill];"
            f"[strip][fill]overlay=x='-W+W*t/{D:.3f}':y=0[fc]")
    return f"{base}[b];{fill};[b][fc]overlay={pad}:{y}:eof_action=pass[v]", []


@effect("vhs", "VHS tape: chroma shift, noise, scanlines, REC timestamp")
def fx_vhs(c):
    sh = max(2, c.w // 180)
    size = int(c.h * 0.03)
    rec = c.dt("● REC", fontsize=size, fontcolor="red", x=int(c.w * 0.06), y=int(c.h * 0.05),
               alpha="'if(lt(mod(t,1),0.6),1,0)'")
    play = c.dt("PLAY ▶" if c.has_glyphs else "PLAY", fontsize=size,
                fontcolor="white", x=f"w-text_w-{int(c.w * 0.06)}", y=int(c.h * 0.05))
    stamp = c.dt("%{pts:hms}", fontsize=size, fontcolor="white",
                 x=int(c.w * 0.06), y=f"h-{int(c.h * 0.08)}")
    return (
        f"[0:v]rgbashift=rh=-{sh}:bh={sh},eq=saturation=1.35:contrast=1.1,"
        f"noise=alls=18:allf=t,gblur=sigma=0.8,"
        f"drawgrid=w=iw:h=4:t=1:c=black@0.25,vignette=PI/5,{rec},{play},"
        f"{stamp}[v]"
    ), []


@effect("film", "Black & white film: grain, vignette, flicker")
def fx_film(c):
    return (
        "[0:v]format=gray,eq=contrast=1.25:brightness='0.02*sin(t*23)':eval=frame,"
        "noise=alls=22:allf=t+u,vignette=PI/4,format=yuv420p[v]"
    ), []


@effect("cinematic", "Letterbox bars + teal/orange grade")
def fx_cinematic(c):
    bar = even(c.h * 0.11) if c.h > c.w else even(c.h * 0.12)
    return (
        f"[0:v]colorbalance=rs=0.08:bs=-0.06:rh=-0.05:bh=0.08,eq=contrast=1.12:saturation=1.1,"
        f"drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
        f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill[v]"
    ), []


@effect("punch-zoom", "Rhythmic punch-in zooms every N seconds", "--strength (seconds between punches, default 2)")
def fx_punch(c):
    every = c.args.strength or 2
    z = f"(1+0.18*lt(mod(t\\,{every})\\,{every / 2}))"
    return (
        f"[0:v]crop=w='iw/{z}':h='ih/{z}':x='(iw-ow)/2':y='(ih-oh)/2.4',"
        f"scale={c.w}:{c.h},setsar=1[v]"
    ), []


@effect("pip", "Picture-in-picture: b-roll full screen, you in a corner bubble", "--broll other.mp4 (required)")
def fx_pip(c):
    if not c.args.broll:
        sys.exit("pip needs --broll <file>")
    pw = even(c.w * 0.38)
    m = int(c.w * 0.05)
    return (
        f"[1:v]scale={c.w}:{c.h}:force_original_aspect_ratio=increase,crop={c.w}:{c.h},setsar=1[bg];"
        f"[0:v]scale={pw}:-2,drawbox=x=0:y=0:w=iw:h=ih:color=white:t={max(4, pw // 60)}[fg];"
        f"[bg][fg]overlay=W-w-{m}:H-h-{int(c.h * 0.12)}:shortest=1[v]"
    ), ["-stream_loop", "-1", "-i", c.args.broll]


@effect("lower-third", "Name + title bar that slides in at the bottom", "--text (name), --subtitle (role)")
def fx_lowerthird(c):
    name = c.args.text or "Your Name"
    role = c.args.subtitle or "Builder · Claude Code"
    size = int(c.h * 0.032)
    bh = int(size * 2.8)
    by = int(c.h * 0.74)
    bw = even(c.w * 0.75)
    slide = f"'-{bw}+min(1,t/0.5)*{bw + int(c.w * 0.05)}'"
    return (
        f"color=black@0.7:s={bw}x{bh},format=rgba[card];"
        f"[card]drawbox=x=0:y=0:w={max(6, bw // 60)}:h=ih:color=0x{c.color}:t=fill,"
        + c.dt(name, fontsize=size, fontcolor="white", x=int(bw * 0.06), y=int(bh * 0.14)) + ","
        + c.dt(role, fontsize=int(size * 0.65), fontcolor="white@0.8", x=int(bw * 0.06), y=int(bh * 0.6))
        + f"[c2];[0:v][c2]overlay=x={slide}:y={by}[v]"
    ), []


@effect("countdown", "3-2-1 countdown intro over a dimmed clip")
def fx_countdown(c):
    size = int(c.s * 0.45)
    parts = ["[0:v]eq=brightness='if(lt(t,3),-0.35,0)':eval=frame"]
    for k in range(3):
        parts.append(c.dt(str(3 - k), fontsize=size, fontcolor="white",
                          x="(w-text_w)/2", y="(h-text_h)/2",
                          alpha=f"'if(between(t,{k},{k + 1}),1-(t-{k})*0.7,0)'",
                          enable=f"'between(t,{k},{k + 1})'"))
    return ",".join(parts) + "[v]", []


@effect("spotlight", "Focus on the center: strong vignette + blurred, desaturated edges")
def fx_spotlight(c):
    return (
        f"[0:v]split[a][b];[b]gblur=sigma=14,eq=saturation=0.4:brightness=-0.15[bl];"
        f"color=black:s={c.w}x{c.h},format=gray,"
        f"geq=lum='255*clip(1-hypot((X-W/2)/(W*0.42),(Y-H*0.45)/(H*0.32)),0,1)',gblur=sigma=40[m];"
        f"[a][m]alphamerge[fg];[bl][fg]overlay,vignette=PI/3.5[v]"
    ), []


# ---------------------------------------------------------------- runner

def run(args):
    if args.effect in ("list", "ls"):
        print("Available effects:\n")
        for name, meta in EFFECTS.items():
            print(f"  {name:<13} {meta['help']}")
            if meta["uses"]:
                print(f"  {'':<13}   options: {meta['uses']}")
        return 0

    if args.effect not in EFFECTS:
        sys.exit(f"Unknown effect '{args.effect}'. Run: effects.py list")
    if not args.input or not os.path.exists(args.input):
        sys.exit("Input file not found.")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it: brew install ffmpeg / winget install ffmpeg / apt install ffmpeg")

    info = probe(args.input)
    ctx = Ctx(args, info)
    graph, extra = EFFECTS[args.effect]["fn"](ctx)

    stem, _ = os.path.splitext(args.input)
    out = args.output or f"{stem}_{args.effect}.mp4"

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", args.input, *extra,
           "-filter_complex", graph, "-map", "[v]"]
    if info["audio"]:
        cmd += ["-map", "0:a:0", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{info['dur']:.3f}", out]

    if args.dry_run:
        print(" ".join(f'"{x}"' if " " in x or ";" in x else x for x in cmd))
        return 0
    r = subprocess.run(cmd)
    shutil.rmtree(ctx.tmp, ignore_errors=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed for effect '{args.effect}'.")
    print(out)
    return 0


def main():
    p = argparse.ArgumentParser(description="One-command video effects (ffmpeg).")
    p.add_argument("effect", help="effect name, or 'list'")
    p.add_argument("input", nargs="?", help="input video")
    p.add_argument("-o", "--output")
    p.add_argument("--text")
    p.add_argument("--subtitle")
    p.add_argument("--items", help="pipe-separated list, e.g. 'one|two|three'")
    p.add_argument("--broll", help="second clip for split / pip")
    p.add_argument("--color", help="accent hex color, default #FF7A1A")
    p.add_argument("--strength", type=float, help="effect-specific intensity")
    p.add_argument("--dry-run", action="store_true", help="print the ffmpeg command only")
    args = p.parse_args()
    if args.strength is not None and args.strength == int(args.strength):
        args.strength = int(args.strength)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
