#!/usr/bin/env python3
"""Duck a music bed under a voiceover to a MEASURED dB ratio, not a guessed one.

Why this exists: the first attempt chained `loudnorm=I=-24 -> sidechaincompress -> alimiter`
and landed the bed only 3.4 dB under the voice. loudnorm's gain was undone by the compressor's
makeup and the limiter downstream, and nothing in that chain was ever measured.

This script instead:
  1. builds an explicit speech mask from the VO (RMS per 10 ms, hysteresis, lookahead),
  2. multiplies the bed by an explicit attack/release gain envelope (sample-accurate),
  3. MEASURES the result with ebur128 momentary loudness, split into speech vs gap regions,
  4. iterates the master gain until both numbers hit target.

No compressor, no makeup gain, no limiter -> nothing can silently undo the level.

Usage:
  python3 scripts/mix_music_bed.py --vo VO.wav --bed BED.wav --out OUT.wav \
      --under-speech 19 --under-gap 11
"""
import argparse, json, re, subprocess, sys, wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import FFMPEG, get  # noqa: E402


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, f"{path}: expected 16-bit"
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        data = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
    return data.reshape(-1, ch), sr


def write_wav(path, x, sr):
    x = np.clip(x, -1.0, 1.0)
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767.0).astype("<i2").tobytes())


def speech_mask(vo, sr, hop_ms=10, on_db=-42.0, off_db=-48.0):
    """Per-hop boolean speech mask with hysteresis (on/off thresholds differ so a
    breath inside a word doesn't chatter the gate)."""
    hop = int(sr * hop_ms / 1000)
    mono = vo.mean(axis=1)
    nhop = len(mono) // hop
    frames = mono[: nhop * hop].reshape(nhop, hop)
    rms_db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-12)
    mask = np.zeros(nhop, dtype=bool)
    on = False
    for i, d in enumerate(rms_db):
        on = d > on_db if not on else d > off_db
        mask[i] = on
    return mask, hop


def dilate(mask, pre_hops, post_hops):
    """Widen the mask so the duck starts before the first syllable and holds through
    the tail of the last one."""
    out = mask.copy()
    idx = np.flatnonzero(mask)
    for i in idx:
        out[max(0, i - pre_hops): i + post_hops + 1] = True
    return out


def envelope(mask, hop, n, sr, duck_db, attack_ms=40.0, release_ms=450.0):
    """Sample-rate gain envelope: 1.0 in the gaps, 10^(-duck/20) under speech,
    with one-pole attack/release so the transitions are inaudible."""
    target = np.where(mask, 10 ** (-duck_db / 20.0), 1.0)
    target = np.repeat(target, hop)
    target = np.resize(target, n) if len(target) < n else target[:n]
    a_att = np.exp(-1.0 / (sr * attack_ms / 1000.0))
    a_rel = np.exp(-1.0 / (sr * release_ms / 1000.0))
    g = np.empty(n, dtype=np.float32)
    cur = 1.0
    for i in range(n):
        t = target[i]
        a = a_att if t < cur else a_rel
        cur = a * cur + (1 - a) * t
        g[i] = cur
    return g


def momentary(path):
    """(times, momentary-LUFS) from ebur128, one reading per 100 ms."""
    p = subprocess.run(
        [FFMPEG, "-hide_banner", "-nostats", "-v", "verbose", "-i", path,
         "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
        capture_output=True, text=True)
    ts, ms = [], []
    for m in re.finditer(r"t:\s*([\d.]+).*?\bM:\s*(-?[\d.]+|-inf)", p.stderr):
        v = m.group(2)
        if v == "-inf":
            continue
        f = float(v)
        if f <= -70.0:          # ebur128's floor, not a real reading
            continue
        ts.append(float(m.group(1))); ms.append(f)
    return np.array(ts), np.array(ms)


def split_levels(path, mask, hop, sr):
    """Median momentary loudness inside speech vs inside gaps."""
    ts, ms = momentary(path)
    if len(ts) == 0:
        return float("nan"), float("nan")
    hop_idx = np.clip((ts * sr / hop).astype(int), 0, len(mask) - 1)
    sp, gp = ms[mask[hop_idx]], ms[~mask[hop_idx]]
    return (float(np.median(sp)) if len(sp) else float("nan"),
            float(np.median(gp)) if len(gp) else float("nan"))


def main():
    ap = argparse.ArgumentParser(description="Duck a music bed under a voiceover to a measured dB ratio.")
    ap.add_argument("--vo", required=True)
    ap.add_argument("--bed", required=True)
    ap.add_argument("--out", required=True)
    _fmt = get("video.format", "shortform")
    ap.add_argument("--under-speech", type=float,
                    default=float(get(f"music.{_fmt}_db_under_voice", 19.0)),
                    help="dB the bed sits under the VO while the speaker is talking")
    ap.add_argument("--under-gap", type=float, default=11.0,
                    help="dB the bed sits under the VO's speaking level in the gaps")
    ap.add_argument("--iters", type=int, default=6)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    vo, sr = read_wav(a.vo)
    bed, sr_b = read_wav(a.bed)
    assert sr == sr_b, f"sample rate mismatch {sr} vs {sr_b}"

    mask, hop = speech_mask(vo, sr)
    # 120 ms of lookahead, 350 ms of hold: duck arrives before the word, leaves after it.
    mask = dilate(mask, pre_hops=12, post_hops=35)
    n = len(bed)
    mask_full = np.resize(mask, n // hop + 1)

    vo_speech, vo_gap = split_levels(a.vo, mask_full, hop, sr)
    print(f"VO           speech {vo_speech:6.1f} LUFS(M)   gaps {vo_gap:6.1f}")

    duck_db = a.under_speech - a.under_gap
    g = envelope(mask_full, hop, n, sr, duck_db)[:, None]

    tgt_speech = vo_speech - a.under_speech
    tgt_gap = vo_speech - a.under_gap

    # Master gain, solved by measurement. Start from the bed's own speech-region level.
    bed_speech, _ = split_levels(a.bed, mask_full, hop, sr)
    gain_db = tgt_gap - bed_speech
    hist = []
    for it in range(a.iters):
        out = bed * g * (10 ** (gain_db / 20.0))
        peak = float(np.abs(out).max())
        write_wav(a.out, out, sr)
        s, gp = split_levels(a.out, mask_full, hop, sr)
        err = tgt_speech - s
        hist.append(dict(iter=it, gain_db=round(gain_db, 2), speech=round(s, 2),
                         gap=round(gp, 2), peak_dbfs=round(20 * np.log10(peak + 1e-12), 2)))
        print(f"  iter {it}: gain {gain_db:+6.2f} dB -> bed speech {s:6.1f}  gap {gp:6.1f}  "
              f"(target {tgt_speech:.1f} / {tgt_gap:.1f})  peak {20*np.log10(peak+1e-12):.1f} dBFS")
        if abs(err) < 0.25:
            break
        gain_db += err

    s, gp = hist[-1]["speech"], hist[-1]["gap"]
    result = dict(vo_speech_lufs_m=round(vo_speech, 2), bed_speech_lufs_m=s, bed_gap_lufs_m=gp,
                  under_speech_db=round(vo_speech - s, 2), under_gap_db=round(vo_speech - gp, 2),
                  duck_depth_db=round(duck_db, 2), master_gain_db=hist[-1]["gain_db"],
                  peak_dbfs=hist[-1]["peak_dbfs"], iterations=hist, out=a.out)
    print(json.dumps({k: v for k, v in result.items() if k != "iterations"}, indent=2))
    if a.report:
        open(a.report, "w").write(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
