#!/usr/bin/env python3
"""Snap keep-range boundaries to the MEASURED speech envelope, not the aligner's word times.

Why this exists: wav2vec2 places a word
boundary where the phoneme model is confident, which is 20-80 ms INSIDE the real word, and
the error is not constant. A flat "40 ms lead / 60 ms tail" pad is therefore right on average
and wrong on individual cuts: it can leave room tone at one head, clip the onset of a short
word at another, and cut the final vowel off a word.

So: take the aligned word boundary as the SEED, then walk the actual envelope outward to where
the energy really crosses the local floor, and pad from THERE.

The envelope is band-limited to 300-6000 Hz. Full-band RMS is dominated by wind and traffic
rumble on outdoor phone audio, which swallows the
low-energy onsets this pass exists to find, an unvoiced /S/ or /p/ lives at 2-8 kHz.

Boundaries are clamped so a pad can never reach a word that was CUT (same guarantee as
clamp_pads.py, re-checked here because snapping moves the boundary after that ran).
"""
from __future__ import annotations

import argparse, json, subprocess, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FFMPEG  # noqa: E402

SR = 16000
STEP = 0.005


def band_envelope(audio: Path) -> np.ndarray:
    """dBFS per 5 ms of the 300-6000 Hz band."""
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(audio), "-vn",
         "-af", "highpass=f=300,lowpass=f=6000",
         "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32)
    n = int(STEP * SR)
    usable = (len(x) // n) * n
    frames = x[:usable].reshape(-1, n)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)


def floor_db(env: np.ndarray, i: int, span: float = 1.0) -> float:
    """Local noise floor: the 20th percentile of the second either side of frame i."""
    h = int(span / STEP)
    return float(np.percentile(env[max(0, i - h): i + h], 20))


def walk(env: np.ndarray, seed: float, direction: int, limit: float, margin: float) -> float:
    """From `seed`, walk `direction` while the band energy stays above floor+margin.

    Returns the time where it drops to the floor, i.e. the true edge of the sound.
    Never travels further than `limit` seconds.
    """
    i = int(round(seed / STEP))
    if not (0 <= i < len(env)):
        return seed
    thr = floor_db(env, i) + margin
    steps = int(limit / STEP)
    quiet_needed = int(0.020 / STEP)          # 20 ms below threshold ends the run
    quiet = 0
    j = i
    for _ in range(steps):
        k = j + direction
        if not (0 <= k < len(env)):
            break
        quiet = quiet + 1 if env[k] < thr else 0
        j = k
        if quiet >= quiet_needed:
            j -= direction * quiet
            break
    return max(0.0, j * STEP)


def main() -> None:
    ap = argparse.ArgumentParser(description="Snap keep-range edges to the measured speech envelope.")
    ap.add_argument("--audio", required=True, help="the enhanced master the cut is taken from")
    ap.add_argument("--words", required=True, help="words.json (ALIGNED timings)")
    ap.add_argument("--cuts", required=True, help="keep-ranges json, seconds")
    ap.add_argument("-o", "--out", required=True, help="where to write the snapped cuts")
    ap.add_argument("--lead", type=float, default=0.035, help="silence kept before the measured onset")
    ap.add_argument("--tail", type=float, default=0.055, help="silence kept after the measured offset")
    ap.add_argument("--margin", type=float, default=6.0, help="dB above the local floor that counts as sound")
    ap.add_argument("--reach", type=float, default=0.30, help="furthest the walk may travel from the seed")
    a = ap.parse_args()

    env = band_envelope(Path(a.audio))
    words = json.load(open(a.words))["words"]
    cuts = json.load(open(a.cuts))

    # A word counts as kept when the MAJORITY of it lies inside the range, not only when it
    # is wholly inside. Strict containment silently drops any word an incoming boundary
    # bisects, and since this pass exists to move boundaries, a boundary landing mid-word is
    # the normal case on a re-snap. Strict containment drops the last word of a segment:
    # the word leaves the core, the walk seeds from the PREVIOUS word, and the line is cut short.
    def overlap(w, c):
        return max(0.0, min(w["end"], c["end"]) - max(w["start"], c["start"]))

    kept_ids = set()
    for w in words:
        dur = max(w["end"] - w["start"], 1e-6)
        for c in cuts:
            if overlap(w, c) >= 0.5 * dur:
                kept_ids.add(id(w)); break
    removed = [w for w in words if id(w) not in kept_ids]

    out, moved = [], []
    for c in cuts:
        core = [w for w in words if id(w) in kept_ids and overlap(w, c) >= 0.5 * max(w["end"] - w["start"], 1e-6)]
        if not core:
            out.append(dict(c)); continue

        s = walk(env, core[0]["start"], -1, a.reach, a.margin) - a.lead
        e = walk(env, core[-1]["end"], +1, a.reach, a.margin) + a.tail

        # a pad must never reach into a word that was cut
        before = [w["end"] for w in removed if w["end"] <= core[0]["start"] + 1e-9]
        after = [w["start"] for w in removed if w["start"] >= core[-1]["end"] - 1e-9]
        if before: s = max(s, max(before))
        if after:  e = min(e, min(after))
        s, e = max(0.0, min(s, core[0]["start"])), max(e, core[-1]["end"])

        moved.append((round((s - c["start"]) * 1000), round((e - c["end"]) * 1000)))
        out.append({"start": round(s, 3), "end": round(e, 3)})

    for i in range(1, len(out)):
        if out[i]["start"] < out[i - 1]["end"]:
            sys.exit(f"snap produced an overlap at segment {i}")

    json.dump(out, open(a.out, "w"), indent=1)
    before_s = sum(c["end"] - c["start"] for c in cuts)
    after_s = sum(c["end"] - c["start"] for c in out)
    print(json.dumps({
        "segments": len(out),
        "before_s": round(before_s, 3),
        "after_s": round(after_s, 3),
        "delta_ms": round((after_s - before_s) * 1000),
        "moved_ms_head_tail": moved,
        "out": a.out,
    }, indent=1))


if __name__ == "__main__":
    main()
