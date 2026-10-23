#!/usr/bin/env python3
"""One small alpha CLIP per caption, instead of one long flattened overlay.

Each 2-3 word card is its own clip, aligned to the VO and b-roll cuts, instead of one long render
that keeps drifting. Never flatten what should stay trimmable: a single overlay means a card's
timing can only be changed by rebuilding the whole file, and a mistimed card is invisible until
playback.

As separate clips each card is a real timeline item: an editor can slip or extend any single one by
hand, nothing has to be re-rendered, and the "never overwrite a file Resolve has linked" hazard
disappears.

**Stills cannot be used.** A PNG imports with `Frames = 1` and `AppendToTimeline` ignores
`endFrame` for it, handing back the project's default still duration (120 frames) every time;
the duration is a *user preference*, not a project setting, so it is not scriptable either. A
clip of real frames honours `endFrame` normally.

Each unique caption is rendered once at HANDLE_FRAMES so every card has room to be extended by
hand; the timeline item takes only the frames it needs. QuickTime Animation (qtrle) keeps alpha
losslessly and keeps the whole set smaller than one flattened overlay.
"""
from __future__ import annotations

import os

import hashlib, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                         # noqa: E402

if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="Render one small alpha clip per caption card and "
                                              "write work/caption_clip_plan.json.")
    _ap.add_argument("--job", help="job name or folder; default $JOB_DIR")
    _a = _ap.parse_args()
    if _a.job:
        os.environ["JOB_DIR"] = str(config.job_dir(_a.job))

import render_caption_frames as rendercaps            # noqa: E402
from captions import build, FPS                       # noqa: E402
from render_caption_frames import STYLE, STYLE_DIR    # noqa: E402

JOB   = Path(os.environ.get("JOB_DIR", "."))
# The style is part of the cache key. Without it, switching border<->shadow silently
# reuses the previous style's clips, because the filename is only a hash of the TEXT.
OUT   = JOB / f"graphics/caption-clips-{int(FPS)}-{STYLE_DIR}"
FRAMES_DIR = JOB / "graphics/caption-frames"
FFMPEG = config.FFMPEG
# Sized from the actual cards plus ~1s of headroom to extend one by hand. A fixed constant broke
# the moment the timeline rate changed: 64 frames is 2.7s at 24 fps but only 1.1s at 60.
HANDLE_FRAMES = None      # computed in main()


def slug(text, plate=None, shadow=None):
    """The filename is a hash of the TEXT, so anything else that changes the pixels has to be
    hashed in too. `plate` is the per-card plate colour (one colour per speaker)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "blank"
    key = (text + ("|" + ",".join(map(str, plate)) if plate else "")
                + ("|s" + ",".join(map(str, shadow)) if shadow else ""))
    return f"{s}__{hashlib.sha1(key.encode()).hexdigest()[:6]}"


def main():
    cards = build()
    if not cards:
        sys.exit("no caption cards. Check --job / JOB_DIR and work/tl_words.json.")
    OUT.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    texts = sorted({(c["text"], tuple(c.get("plate") or ()), tuple(c.get("shadow") or ()))
                    for c in cards})
    longest = max(c["ef"] - c["sf"] for c in cards)
    handle = longest + int(round(FPS))          # longest card + 1s of room to extend
    print(f"{len(cards)} cards, {len(texts)} unique, longest {longest}f, clips {handle}f @{FPS:g}")

    for i, (t, plate, shadow) in enumerate(texts):
        name = slug(t, plate, shadow)
        mov = OUT / f"{name}.mov"
        if mov.exists():
            continue
        png = FRAMES_DIR / f"{name}__{STYLE}.png"
        rendercaps.render(t, str(png), plate=list(plate) or None,
                          shadow=list(shadow) or None)
        subprocess.run([FFMPEG, "-v", "error", "-y", "-loop", "1", "-framerate", str(int(FPS)),
                        "-i", str(png), "-frames:v", str(handle),
                        "-c:v", "qtrle", "-pix_fmt", "argb", "-r", str(int(FPS)), str(mov)], check=True)
        if (i + 1) % 40 == 0:
            print(f"  {i+1}/{len(texts)}")

    plan = [{"text": c["text"],
             "clip": slug(c["text"], tuple(c.get("plate") or ()),
                          tuple(c.get("shadow") or ())) + ".mov",
             "rec": c["sf"], "dur": c["ef"] - c["sf"], "held": bool(c.get("held"))}
            for c in cards]
    json.dump(plan, open(JOB / "work/caption_clip_plan.json", "w"), indent=1)
    # place_caption_clips.py runs on the Resolve venv, which has no PIL and therefore cannot
    # import this module to recompute STYLE_DIR. Hand it the directory name instead.
    json.dump({"dir": OUT.name, "style_dir": STYLE_DIR, "fps": int(FPS)},
              open(JOB / "work/caption_clip_dir.json", "w"), indent=1)
    total = sum(f.stat().st_size for f in OUT.glob("*.mov"))
    print(f"wrote {len(list(OUT.glob('*.mov')))} clips, {total/1e6:.1f} MB -> work/caption_clip_plan.json")


if __name__ == "__main__":
    main()
