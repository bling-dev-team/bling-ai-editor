#!/usr/bin/env python3
"""Cut a music bed to length with a chosen moment landing on a chosen frame.

Two traps this exists to avoid, both of which shipped once:

1. **Never `-ss` an mp3.** mp3 seek granularity put the drop 0.38 s out, twice. Decode to WAV
   first, then slice by sample.
2. **Never pad silence in front to build a run-up.** It opens the film on dead air. Move the
   source in-point instead: `song_start = anchor_in_song - anchor_on_timeline`.

And the one this exists to *fix*: a song is usually shorter than it looks. A file can end in many
seconds of digital silence, so a bed cut late in the song runs out and the end of the film has no
music at all. When the
window overruns the music, this loops back a whole number of bars and **phase-aligns the splice
by cross-correlation**, because a bar length derived from an estimated tempo is off by tens of
milliseconds and that lands as an audible flam.
"""
from __future__ import annotations

import argparse, subprocess, sys, wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from mix_music_bed import read_wav, write_wav          # noqa: E402
from config import FFMPEG                              # noqa: E402


def decode(src, cache):
    if not Path(cache).exists():
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src),
                        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(cache)], check=True)
    return read_wav(cache)


def music_end(x, sr, floor_db=-60.0, hop=0.1):
    h = int(sr * hop); n = len(x) // h
    e = 20 * np.log10(np.sqrt((x[:n * h].mean(axis=1).reshape(n, h) ** 2).mean(axis=1)) + 1e-12)
    live = np.flatnonzero(e > floor_db)
    return (live[-1] + 1) * hop if len(live) else 0.0


def bar_seconds(x, sr, upto):
    """Beat period from the autocorrelation of a crude onset envelope; bar = 4 beats."""
    h = int(sr * 0.01); n = min(len(x), int(upto * sr)) // h
    e = np.sqrt((x[:n * h].mean(axis=1).reshape(n, h) ** 2).mean(axis=1))
    o = np.maximum(0, np.diff(e, prepend=e[0]))
    o = (o - o.mean()) / (o.std() + 1e-9)
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    lo, hi = 30, 120                                     # 50-200 BPM at a 10 ms hop
    return (lo + int(np.argmax(ac[lo:hi]))) * 0.01 * 4


def phase_align(x, sr, splice, want, search=0.35, win=2.0):
    """Refine a loop-back distance so the repeat lands in phase with what precedes it."""
    a0 = int((splice - win) * sr); a1 = int(splice * sr)
    ref = x[a0:a1].mean(axis=1)
    best, best_score = want, -1e18
    for cand in np.arange(want - search, want + search, 1 / sr * 8):
        b0 = int((splice - win - cand) * sr)
        if b0 < 0: continue
        seg = x[b0:b0 + (a1 - a0)].mean(axis=1)
        if len(seg) != len(ref): continue
        s = float(np.dot(ref, seg) / (np.linalg.norm(seg) + 1e-9))
        if s > best_score: best_score, best = s, float(cand)
    return best


def main():
    ap = argparse.ArgumentParser(description="Cut a music bed to length with a chosen moment on a "
                                             "chosen timeline time (loops by whole bars if short).")
    ap.add_argument("--song", required=True, help="source song (any format ffmpeg reads)")
    ap.add_argument("--out", required=True, help="output 48 kHz 16-bit WAV")
    ap.add_argument("--cache", default="song48.wav")
    ap.add_argument("--anchor-in-song", type=float, required=True, help="e.g. the drop, in seconds")
    ap.add_argument("--anchor-on-timeline", type=float, required=True, help="seconds")
    ap.add_argument("--duration", type=float, required=True, help="bed length, seconds")
    ap.add_argument("--fade-in", type=float, default=0.6)
    ap.add_argument("--fade-out", type=float, default=1.7)
    ap.add_argument("--xfade", type=float, default=0.18)
    a = ap.parse_args()

    x, sr = decode(a.song, a.cache)
    end = music_end(x, sr)
    start = a.anchor_in_song - a.anchor_on_timeline
    print(f"song {len(x)/sr:.2f}s, music ends {end:.2f}s; window {start:.3f} -> {start+a.duration:.3f}s")
    assert start >= 0, "anchor is earlier on the timeline than in the song"

    need = int(round(a.duration * sr))
    avail = int(round((end - start) * sr))
    if avail >= need:
        bed = x[int(start * sr):int(start * sr) + need].copy()
        print("  no loop needed")
    else:
        bar = bar_seconds(x, sr, end)
        short = (need - avail) / sr
        nbars = int(np.ceil(short / bar))
        back = phase_align(x, sr, end, nbars * bar)
        print(f"  short by {short:.2f}s; bar {bar:.3f}s -> loop back {nbars} bars "
              f"= {nbars*bar:.3f}s, phase-aligned to {back:.3f}s")
        head = x[int(start * sr):int(end * sr)].copy()
        tail = x[int((end - back) * sr):].copy()[:need - len(head) + int(a.xfade * sr)]
        xf = int(a.xfade * sr)
        ramp = np.linspace(0, 1, xf)[:, None]
        bed = np.zeros((need, 2), dtype=np.float32)
        bed[:len(head)] = head
        j = len(head) - xf
        bed[j:j + xf] = head[-xf:] * (1 - ramp) + tail[:xf] * ramp
        rest = tail[xf:][:need - (j + xf)]
        bed[j + xf:j + xf + len(rest)] = rest

    t = np.arange(len(bed)) / sr
    bed *= np.clip(t / max(a.fade_in, 1e-9), 0, 1)[:, None]
    bed *= np.clip((a.duration - t) / max(a.fade_out, 1e-9), 0, 1)[:, None]
    write_wav(a.out, bed, sr)

    h = int(sr * 0.1); n = len(bed) // h
    e = 20 * np.log10(np.sqrt((bed[:n * h].mean(axis=1).reshape(n, h) ** 2).mean(axis=1)) + 1e-12)
    silent = [i * 0.1 for i, v in enumerate(e) if v < -60 and i * 0.1 > a.fade_in]
    print(f"  wrote {a.out}  {len(bed)/sr:.3f}s   silent 100ms buckets after the fade-in: {len(silent)}")
    i0, i1 = int((a.anchor_on_timeline - 0.4) / 0.1), int((a.anchor_on_timeline + 0.1) / 0.1)
    print(f"  anchor lift at {a.anchor_on_timeline}s: {e[i1]-e[i0]:+.1f} dB")


if __name__ == "__main__":
    main()
