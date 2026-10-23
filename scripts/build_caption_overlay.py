#!/usr/bin/env python3
"""SUPERSEDED: use build_caption_clips.py + place_caption_clips.py instead.

Captions now ship as one small alpha clip per card, so any single card can be slipped or
extended by hand in Resolve and nothing has to be re-rendered. This flattened-overlay path is
kept only because it still documents the concat-demuxer trick and the CAP_VER relink rule.

Assemble the caption cards into a transparent ProRes 4444 overlay for V3.

One PNG per card (plus a blank for every gap), fed to ffmpeg through the concat
demuxer with exact per-card durations, so the overlay is frame-accurate against the
timeline without rendering thousands of individual frames.
"""
import argparse, json, os, subprocess, sys, hashlib
SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import config  # noqa: E402

if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Flatten all caption cards into one ProRes 4444 "
                                              "overlay (old path; prefer build_caption_clips.py).")
    _ap.add_argument("--job", help="job name or folder; default $JOB_DIR")
    _a = _ap.parse_args()
    if _a.job:
        os.environ["JOB_DIR"] = str(config.job_dir(_a.job))

import render_caption_frames as rendercaps  # noqa: E402
from captions import build, srt, FPS, TL_END  # noqa: E402

OUTDIR = os.environ.get("JOB_DIR", ".") + "/graphics"
# V1/V2 picture length; a longer overlay renders a black frame past the end
TOTAL  = int(round(TL_END * FPS))

def main():
    cards = build()
    os.makedirs(OUTDIR + "/caption-frames", exist_ok=True)
    for f in os.listdir(OUTDIR + "/caption-frames"): os.remove(OUTDIR + "/caption-frames/" + f)

    # expand into a gap-free sequence of (png, frames)
    seq, pos, cache = [], 0, {}
    def png(text):
        key = hashlib.sha1(text.encode()).hexdigest()[:12]
        p = f"{OUTDIR}/caption-frames/c_{key}.png"
        if key not in cache:
            rendercaps.render(text, p); cache[key] = p
        return p
    blank = png("")
    for c in cards:
        if c["sf"] > pos: seq.append((blank, c["sf"] - pos))
        seq.append((png(c["text"]), c["ef"] - c["sf"]))
        pos = c["ef"]
    if pos < TOTAL: seq.append((blank, TOTAL - pos))

    assert sum(n for _, n in seq) == TOTAL, sum(n for _, n in seq)

    lst = OUTDIR + "/overlay_list.txt"
    with open(lst, "w") as f:
        for p, n in seq:
            f.write(f"file '{p}'\nduration {n/FPS:.6f}\n")
        f.write(f"file '{seq[-1][0]}'\n")   # concat demuxer needs the last file repeated

    # Always write a NEW filename. Resolve holds a handle on a linked file, and overwriting
    # one in place made a render fail with "Error decoding full resolution media" at exactly
    # the frame whose caption had changed.
    ver = os.environ.get("CAP_VER", "v2")
    out = f"{OUTDIR}/captions_overlay_{ver}.mov"
    subprocess.run([config.FFMPEG, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", lst,
        "-vf", f"fps={int(FPS)},format=yuva444p10le",
        "-c:v", "prores_ks", "-profile:v", "4444", "-alpha_bits", "8", "-vendor", "apl0",
        "-r", str(int(FPS)), "-frames:v", str(TOTAL), out], check=True)

    with open(OUTDIR + f"/captions_{ver}.srt", "w") as f: f.write(srt(cards))
    json.dump(cards, open(OUTDIR + f"/captions_{ver}.json", "w"), indent=1)
    print("cards:", len(cards), "unique pngs:", len(cache))
    print(out, os.path.getsize(out) / 1e6, "MB")

if __name__ == "__main__":
    main()
