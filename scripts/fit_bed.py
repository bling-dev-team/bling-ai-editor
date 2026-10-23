#!/usr/bin/env python3
"""Trim the chosen music bed to the picture length, exactly, and write its placement plan.

A bed that is even a fraction of a frame long puts audio past the last picture frame, which the
"nothing outlasts the picture" rule forbids, and Resolve will happily place it.
So the trim is done in SAMPLES, not seconds, and the result is asserted.

    python3 scripts/fit_bed.py --job <job> --frames 1800 --bed bed_final.wav
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import config  # noqa: E402

FF = config.FFMPEG
FP = config.FFPROBE
SR = 48000


def main() -> None:
    ap = argparse.ArgumentParser(description="Trim a music bed to an exact frame count and write "
                                             "work/bed_plan.json.")
    ap.add_argument("--job", required=True, help="job name (under paths.jobs_dir) or folder path")
    ap.add_argument("--frames", type=int, required=True, help="picture length in timeline frames")
    ap.add_argument("--bed", required=True, help="bed file name inside <job>/audio")
    ap.add_argument("--fps", type=float, default=config.FPS, help="timeline fps (default video.fps)")
    a = ap.parse_args()
    fps = a.fps
    job = config.job_dir(a.job)
    src = job / "audio" / a.bed
    stem = pathlib.Path(a.bed).stem
    out = job / "audio" / f"{stem}_{a.frames}f.wav"
    n = round(a.frames / fps * SR)
    fade_at = (a.frames / fps) - 0.16
    subprocess.run([FF, "-v", "error", "-y", "-i", str(src),
                    "-af", f"atrim=end_sample={n},afade=t=out:st={fade_at:.4f}:d=0.16",
                    "-c:a", "pcm_s24le", str(out)], check=True)
    dur = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", str(out)], capture_output=True,
                               text=True).stdout)
    got = round(dur * fps, 3)
    assert abs(got - a.frames) < 0.01, f"bed is {got} frames, want {a.frames}"
    (job / "work").mkdir(parents=True, exist_ok=True)
    (job / "work/bed_plan.json").write_text(json.dumps(
        [{"clip": out.name, "rec": 0, "dur": a.frames, "sf": 0, "ef": a.frames,
          "why": "music bed trimmed to the picture length"}], indent=1))
    print(f"   bed {out.name}: {got} frames")


if __name__ == "__main__":
    main()
