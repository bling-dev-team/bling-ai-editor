#!/usr/bin/env python3
"""The six b-roll rules, run against Resolve's READBACK.

The plan being right is not evidence that the timeline is, every one of these has been
violated by a timeline that was built from a correct plan. So this reads V1/V2 back out of
Resolve and audits the real items:

  1. every VO cut starts a new b-roll clip
  2. a transition word means the picture is ALREADY at the next place
  3. never reuse a source RANGE (reusing a clip is fine)
  4. a reused clip runs FORWARD, source in-points strictly increase down the timeline
  5. a slot under ~12 frames stays on a NEIGHBOUR's clip, later non-overlapping part
  6. chronological after the intro, by capture time + in-clip offset

Plus the mechanical checks: no gaps, no overlaps, nothing overruns its source.

**Two formats, two shapes.** A b-roll voiceover edit lays b-roll wall-to-wall over a voiceover, so
V2 covers the whole timeline and a gap is a bug. A longform edit places SPARSE INSERTS over a talking
head, the reference band is 18-30 % coverage, so V2 is *mostly* gap and the continuity checks are
meaningless. Pass `--sparse` for the insert shape: it drops the coverage checks and re-reads rule 1
the only way it makes sense there, every INSERT must start on a VO cut, or be deliberately
word-anchored inside a segment longer than ~2.2 s (required anyway, since no audio
cut exists inside such a segment). Rules 2-5 apply unchanged in both shapes.

`GetLeftOffset()` reports source position in TIMELINE frames, not source frames, that is the
unit this script works in throughout, so a 59.94 fps clip and a 24 fps clip compare directly.

Run:  python3 scripts/audit_broll.py --job <job> --timeline "<timeline name>"
"""
from __future__ import annotations

import argparse, json, os, re, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

JOB = None              # set from --job in main()
TL_FPS = config.FPS     # --fps overrides; must match the timeline rate
SHORT_SLOT = 12          # frames; under this, rule 5 replaces rule 1
TRANSITIONS = ("then", "after that", "finally", "once we finished up", "but yeah",
               "after", "so we")


def capture_times(paths, cache=None):
    """creation_time per source file, cached, ffprobe on 50 4K clips is not free."""
    cache = cache or (JOB / "work/capture_times.json")
    known = json.load(open(cache)) if cache.exists() else {}
    for name, path in paths.items():
        if name in known or not path or not os.path.exists(path):
            continue
        out = subprocess.run(
            [config.FFPROBE, "-v", "error", "-show_entries",
             "format_tags=creation_time", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True).stdout.strip()
        known[name] = out or None
    cache.parent.mkdir(parents=True, exist_ok=True)
    json.dump(known, open(cache, "w"), indent=1)
    return known


def read_track(tl, ttype, idx, start):
    items = []
    for it in (tl.GetItemListInTrack(ttype, idx) or []):
        items.append(dict(name=it.GetName(), rec=int(it.GetStart()) - start,
                          dur=int(it.GetDuration()), src_in=int(it.GetLeftOffset()),
                          path=(it.GetMediaPoolItem().GetClipProperty("File Path")
                                if it.GetMediaPoolItem() else None)))
    items.sort(key=lambda d: d["rec"])
    for d in items:
        d["src_out"] = d["src_in"] + d["dur"]
        d["rec_out"] = d["rec"] + d["dur"]
    return items


def main():
    global JOB, TL_FPS
    ap = argparse.ArgumentParser(description="Audit a Resolve timeline's b-roll against the six "
                                             "rules, from the READBACK.")
    ap.add_argument("--timeline", required=True, help="timeline name")
    ap.add_argument("--job", required=True, help="job name (under paths.jobs_dir) or folder path")
    ap.add_argument("--fps", type=float, default=config.FPS, help="timeline fps (default video.fps)")
    ap.add_argument("--shots", default=None, help="default <job>/work/shots.json")
    ap.add_argument("--words", default=None, help="default <job>/work/tl_words.json")
    ap.add_argument("--sparse", action="store_true",
                    help="insert shape (longform): V2 is 18-30%% coverage by design, so skip the "
                         "coverage checks and require each INSERT to start on a VO cut or be "
                         "word-anchored inside a segment over ~2.2 s")
    ap.add_argument("--intro-slots", type=int, default=None,
                    help="slots before this index are the montage and are exempt from rule 6")
    a = ap.parse_args()
    job = JOB = config.job_dir(a.job)
    TL_FPS = a.fps
    a.shots = a.shots or str(job / "work/shots.json")
    a.words = a.words or str(job / "work/tl_words.json")
    if a.intro_slots is None:                 # a persisted boundary beats a re-derived guess
        cfg = job / "work/audit_config.json"
        if cfg.exists():
            a.intro_slots = json.load(open(cfg)).get("intro_slots")

    from resolve_client import R
    r = R()
    tl = r.timeline(a.timeline)
    start = int(tl.GetStartFrame())
    vo = read_track(tl, "video", 1, start)
    br = read_track(tl, "video", 2, start)
    length = int(tl.GetEndFrame()) - start
    fails, notes = [], []

    print(f"{a.timeline}: {length} frames  V1={len(vo)}  V2={len(br)}")

    #, mechanical: gaps / overlaps / overrun -----------------------------
    # An OVERLAP is a bug in both shapes. A GAP is a bug only when V2 is meant to be
    # continuous, on an insert timeline V2 is mostly gap by design.
    for i, d in enumerate(br[1:], 1):
        prev = br[i - 1]
        if d["rec"] > prev["rec_out"]:
            if not a.sparse:
                fails.append(f"GAP on V2: {prev['rec_out']}-{d['rec']} ({d['rec']-prev['rec_out']}f)")
        elif d["rec"] < prev["rec_out"]:
            fails.append(f"OVERLAP on V2 at {d['rec']}: {prev['name']} / {d['name']}")
    picture_end = vo[-1]["rec_out"] if vo else length
    if not a.sparse:
        if br and br[0]["rec"] != 0:
            fails.append(f"V2 head is {br[0]['rec']}f, not 0")
        if br and br[-1]["rec_out"] != picture_end:
            fails.append(f"V2 tail ends at {br[-1]['rec_out']}f, V1 ends at {picture_end}f")
    else:
        cov = sum(d["dur"] for d in br)
        band = "inside" if 0.18 <= cov / length <= 0.30 else "OUTSIDE"
        msg = f"insert coverage {cov}f = {cov/length:.1%} of {length}f, {band} the 18-30% band"
        (notes if band == "inside" else fails).append(msg)
    if picture_end != length:
        notes.append(f"V1/V2 end at {picture_end}f but the timeline is {length}f, V3's caption "
                     f"overlay is {length-picture_end}f longer than the footage (harmless)")

    #, rule 1 ------------------------------------------------------------
    vo_cuts = {d["rec"] for d in vo[1:]}
    br_cuts = {d["rec"] for d in br}
    if a.sparse:
        # Read the other way round: an INSERT must land on a VO cut, or be word-anchored
        # inside a segment too long to hold one (CLAUDE.md: add an internal cut only when a
        # VO clip runs longer than ~2.2 s, since no audio cut exists inside it).
        LONG = int(2.2 * TL_FPS)
        starts = {d["rec"] for d in vo} | vo_cuts
        for d in br:
            if d["rec"] in starts:
                continue
            if d["name"].startswith("CARD_"):
                # A pop-up card is a GRAPHIC keyed to the word the speaker gestures at, not a
                # picture cut. It is meant to appear mid-shot, that is what the reference
                # does with its floating photos, so cut-alignment does not apply. Rules
                # 3/4 (no reused range, forward only) and the overlap check still do.
                notes.append(f"rule1: {d['name']} at {d['rec']}f is a pop-up card, "
                             f"gesture-keyed graphic, exempt from cut alignment")
                continue
            seg = next((v for v in vo if v["rec"] <= d["rec"] < v["rec_out"]), None)
            if seg is None:
                fails.append(f"rule1: insert {d['name']} at {d['rec']}f sits outside every VO segment")
            elif seg["dur"] >= LONG:
                notes.append(f"rule1: {d['name']} at {d['rec']}f is word-anchored inside a "
                             f"{seg['dur']}f segment (>{LONG}f), allowed, no audio cut exists there")
            else:
                fails.append(f"rule1: insert {d['name']} at {d['rec']}f neither starts on a VO cut "
                             f"nor sits in a segment over {LONG}f ({seg['dur']}f)")
    else:
        for c in sorted(vo_cuts - br_cuts):
            seg = next(d for d in vo if d["rec"] == c)
            notes.append(f"rule1: VO cut at {c}f ({c/TL_FPS:.2f}s, {seg['dur']}f segment) "
                         f"has no b-roll cut{', sub-8f fragment, cutting there would strobe'
                                              if seg['dur'] < 8 else ''}")
            if seg["dur"] >= 8:
                fails.append(f"rule1: VO cut at {c}f starts a {seg['dur']}f segment with no b-roll cut")

    #, rule 2: transition words --------------------------------------------
    if os.path.exists(a.words):
        words = json.load(open(a.words))
        text = " ".join(w["w"].lower().strip(".,!?") for w in words)
        for phrase in TRANSITIONS:
            toks = phrase.split()
            for i in range(len(words) - len(toks) + 1):
                if [w["w"].lower().strip(".,!?") for w in words[i:i + len(toks)]] == toks:
                    t = words[i]["t"]
                    f = t * TL_FPS
                    near = [c for c in br_cuts if -12 <= c - f <= 4]
                    if not near:
                        fails.append(f"rule2: '{phrase}' at {t:.2f}s has no b-roll cut in "
                                     f"[-0.50s,+0.17s], picture is still in the old place")
        _ = text

    #, effective time, and where the intro montage ends --------------------
    paths = {d["name"]: d["path"] for d in br}
    caps = capture_times(paths)
    shots = json.load(open(a.shots)) if os.path.exists(a.shots) else {}

    def capture_of(name):
        """A re-render loses its creation_time; fall back to the clip it was made from."""
        for key in (name, re.sub(r"_blurred(?=\.)", "", name)):
            if caps.get(key):
                return datetime.fromisoformat(caps[key].replace("Z", "+00:00"))
        return None                       # sourced footage: not ours, no capture time

    eff = []
    for i, d in enumerate(br):
        entry = shots.get(str(i))
        off = entry[1] if entry else d["src_in"] / TL_FPS
        c = capture_of(d["name"])
        eff.append(None if c is None else c + timedelta(seconds=off))

    def monotonic_from(s_idx):
        seq = [e for e in eff[s_idx:] if e is not None]
        return all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))

    intro = a.intro_slots
    if intro is None:
        intro = next((s_idx for s_idx in range(len(eff)) if monotonic_from(s_idx)), len(eff))
    notes.append(f"intro montage = slots 0-{intro-1} (to {br[intro]['rec']/TL_FPS:.2f}s); "
                 f"rules 4 and 6 apply from slot {intro} on")

    #, rule 3 / 4: source ranges ------------------------------------------
    by_clip = {}
    for i, d in enumerate(br):
        by_clip.setdefault(d["name"], []).append((i, d))
    for name, uses in by_clip.items():
        for j in range(len(uses)):
            for k in range(j + 1, len(uses)):
                (_, x), (_, y) = uses[j], uses[k]
                if x["src_in"] < y["src_out"] and y["src_in"] < x["src_out"]:
                    fails.append(f"rule3: {name} reuses source range, slot@{x['rec']}f "
                                 f"[{x['src_in']}-{x['src_out']}] vs slot@{y['rec']}f "
                                 f"[{y['src_in']}-{y['src_out']}]")
        for lo, hi, where in ((0, intro, "intro"), (intro, len(br), "body")):
            ins = [d["src_in"] for i, d in uses if lo <= i < hi]
            if ins != sorted(ins):
                fails.append(f"rule4: {name} runs BACKWARD within the {where}: {ins}")

    #, rule 5: short slots ------------------------------------------------
    for i, d in enumerate(br):
        if d["dur"] >= SHORT_SLOT:
            continue
        nb = [br[i - 1]["name"] if i else None, br[i + 1]["name"] if i + 1 < len(br) else None]
        if d["name"] not in nb:
            fails.append(f"rule5: {d['dur']}f slot at {d['rec']}f is {d['name']}, "
                         f"neighbours are {nb}, a hard cut this short reads as a glitch")

    #, rule 6: chronological after the intro ------------------------------
    for i in range(intro, len(eff) - 1):
        if eff[i] and eff[i + 1] and eff[i] > eff[i + 1]:
            fails.append(f"rule6: slot {i} ({br[i]['name']} @{eff[i]:%H:%M:%S}) is later than "
                         f"slot {i+1} ({br[i+1]['name']} @{eff[i+1]:%H:%M:%S}) but plays first")
    unknown = sorted({br[i]['name'] for i in range(len(eff)) if eff[i] is None})
    if unknown:
        notes.append(f"rule6: no capture time for {len(unknown)} sourced clips "
                     f"({', '.join(unknown[:3])}{'...' if len(unknown) > 3 else ''}), exempt")

    for n in notes:
        print("  note  " + n)
    for f in fails:
        print("  FAIL  " + f)
    print(f"\n{'PASS, all six rules hold on the readback' if not fails else f'{len(fails)} FAILURES'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
