#!/usr/bin/env python3
"""Rebuild kept ranges from the WAVEFORM, the last word on shortform tightness.

Rule: anywhere there is no sound, cut it; where a sound is dying off, cut a tiny bit more than
you think.

`tighten.py` splits on ALIGNER word gaps, and that is structurally not enough: wav2vec2 marks a word
as over where the phoneme model loses confidence, ~20-80 ms INSIDE the word, so the 100-200 ms of
audible decay that follows never appears as a gap. An aligner-driven pass can leave seconds of
silent runs inside a short cut and still report itself clean.

So: measure the 300-6000 Hz envelope at 5 ms and carve every kept range into sound bursts, with a
permissive ONSET bar (never clip a consonant) and a tail bar that depends on WHERE the burst sits , 
At the end of a sentence, phrase or question every millisecond counts. Inside a phrase the tail bar just closes the silence; at the phrase, sentence
or question END it is harder, and relative to that burst's own peak, so the cut lands inside the
decay. Applying the hard bar everywhere shreds the delivery.

    python3 scripts/carve_silence.py --audio <enhanced master> \
        --cuts jobs/<job>/transcript/cuts.json -o jobs/<job>/transcript/cuts_carved.json

**Always verify by re-transcribing the rebuilt edit**, the word content must be IDENTICAL. That is
the only check that proves the harder tail bar has not eaten a syllable.
"""
from __future__ import annotations

import argparse, json, subprocess, sys, tempfile, wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FFMPEG  # noqa: E402

H = 0.005          # envelope hop, 5 ms


def envelope(audio: str) -> np.ndarray:
    """dBFS of the 300-6000 Hz band at 5 ms. Band-limiting matters: full-band RMS is dominated by
    room rumble and swallows an unvoiced /ʃ/ or /p/ entirely."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        wav = t.name
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", audio,
                    "-af", "highpass=f=300,lowpass=f=6000", "-ac", "1", "-ar", "48000",
                    "-c:a", "pcm_s16le", wav], check=True)
    w = wave.open(wav, "rb"); sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    hop = int(sr * H)
    rms = np.sqrt(np.array([np.mean(a[i:i + hop] ** 2) for i in range(0, len(a) - hop, hop)]) + 1e-12)
    Path(wav).unlink(missing_ok=True)
    return 20 * np.log10(rms + 1e-12)


def carve(db, cuts, on, off, lead, tail, merge, drop_under, off_rel=None, off_floor=-40.0,
          on_rel=None):
    """Kept ranges -> sound bursts, with a different bar at each edge.

    Merging is decided on the UNTRIMMED burst gaps, then the trimmed edges are applied to the
    outside of each merged group. Trimming first and merging after would pull previously-merged
    bursts apart and add picture cuts (roughly 12 cuts per 10 s instead of a healthy 7).
    """
    out = []
    for c in cuts:
        lo, hi = int(c["start"] / H), int(c["end"] / H)
        seg = db[lo:hi]
        loud = seg >= on
        k, bursts = 0, []
        while k < len(loud):
            if loud[k]:
                j = k
                while j < len(loud) and loud[j]:
                    j += 1
                bursts.append([k, j]); k = j
            else:
                k += 1
        if not bursts:
            continue

        rows = []
        for bi, (s, e) in enumerate(bursts):
            peak = float(seg[s:e].max())
            ts, te = s, e
            # Dead space BEFORE a word counts too. A flat -42 dB onset bar fires on a word's quiet
            # ramp-in (and on breaths), which leaves ~100 ms of near-silence at a segment head. So the ONSET gets the same relative treatment as the
            # tail, clamped never gentler than `on`.
            if on_rel is not None:
                bar_on = max(peak - on_rel, on)
                while ts < e and seg[ts] < bar_on:
                    ts += 1
            # The HARDER tail bar belongs at the end of a PHRASE, not at every micro-burst inside
            # one; applying it everywhere shreds the delivery.
            # It is relative to the burst's own peak because speakers trail off: a flat -30 dB bar ate
            # the last word of a softly delivered line. -10 dB relative is measurably too far (it
            # turned "captions" into "caps"); -12 is the floor.
            last = bi == len(bursts) - 1
            bar_off = off
            if last and off_rel is not None:
                bar_off = max(peak - off_rel, off)
            while te > ts and seg[te - 1] < bar_off:
                te -= 1
            if te <= ts:
                continue
            pad_tail = 0.0 if last else tail
            rows.append({
                "raw_s":  c["start"] + max(0, s - int(lead / H)) * H,
                "raw_e":  c["start"] + min(len(seg), e + int(pad_tail / H)) * H,
                "trim_s": c["start"] + max(0, ts - int(lead / H)) * H,
                "trim_e": c["start"] + min(len(seg), te + int(pad_tail / H)) * H,
            })

        # merge on the UNTRIMMED gaps, keep the trimmed outer edges
        group = [rows[0]]
        for r in rows[1:]:
            if r["raw_s"] - group[-1]["raw_e"] < merge:
                group[-1] = {**group[-1], "raw_e": r["raw_e"], "trim_e": r["trim_e"]}
            else:
                group.append(r)
        for g in group:
            out.append({"start": round(g["trim_s"], 3), "end": round(g["trim_e"], 3)})

    return [x for x in out if x["end"] - x["start"] >= drop_under]


def main():
    ap = argparse.ArgumentParser(description="Carve kept ranges into sound bursts from the waveform.")
    ap.add_argument("--audio", required=True, help="the enhanced master the cut is taken from")
    ap.add_argument("--cuts", required=True, help="approved keep-ranges, in seconds")
    ap.add_argument("-o", "--out", required=True, help="where to write the carved cuts")
    ap.add_argument("--on", type=float, default=-42.0, help="onset bar, permissive, never clip a consonant")
    ap.add_argument("--off", type=float, default=-36.0, help="TAIL bar, harder, so the cut lands inside the decay")
    ap.add_argument("--lead", type=float, default=0.020, help="below ~0.015 a splice starts eating 'if' / 'the'. 0.020 with --on-rel 16")
    ap.add_argument("--tail", type=float, default=0.010, help="'a tiny bit more than you think'")
    ap.add_argument("--merge", type=float, default=0.060, help="closer than this and a picture cut buys nothing")
    ap.add_argument("--min", dest="drop_under", type=float, default=0.060)
    ap.add_argument("--off-rel", type=float, default=12.0,
                    help="PHRASE-END tail bar, as dB below that burst's own peak, 'cut a tiny bit "
                         "more than you think' at the end of a sentence, phrase or question. Applies "
                         "ONLY to the last burst of each approved range. 12 is the measured floor: at "
                         "10 the ASR heard 'captions' as 'caps'. Set to 0 to use the flat --off")
    ap.add_argument("--on-rel", type=float, default=16.0,
                    help="onset bar as dB below the burst's own peak, clamped never gentler than --on. "
                         "Kills the dead space a flat -42 dB bar leaves on a word's quiet ramp-in. "
                         "0 disables")
    ap.add_argument("--off-floor", type=float, default=-40.0,
                    help="unused since the phrase-end bar is clamped to --off; kept for compatibility")
    a = ap.parse_args()

    cuts = json.load(open(a.cuts))
    db = envelope(a.audio)
    m = carve(db, cuts, a.on, a.off, a.lead, a.tail, a.merge, a.drop_under,
              a.off_rel or None, a.off_floor, a.on_rel or None)

    before = sum(c["end"] - c["start"] for c in cuts)
    after = sum(c["end"] - c["start"] for c in m)
    json.dump(m, open(a.out, "w"), indent=1)
    short = [(i, round(x["end"] - x["start"], 3)) for i, x in enumerate(m) if x["end"] - x["start"] < 0.25]
    print(json.dumps({"segments_before": len(cuts), "segments_after": len(m),
                      "seconds_before": round(before, 3), "seconds_after": round(after, 3),
                      "saved_seconds": round(before - after, 3),
                      "slivers_under_0.25s": short, "out": a.out}, indent=2))
    if short:
        print("  !! probe every sliver on its own, a burst that carries no word should be DROPPED,\n"
              "     and one that does must not be split across a picture cut.")
    print("  NOW VERIFY: rebuild the edit audio, re-transcribe it, and diff the word content.")


if __name__ == "__main__":
    sys.exit(main())
