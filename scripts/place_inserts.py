#!/usr/bin/env python3
"""Place b-roll / insert clips on V2 of a longform timeline, one trimmable item each.

`media_type: 1` (video only) so an insert is silent and the VO stays the only audio.

Inserts are pre-rendered at the TIMELINE's frame rate and resolution (render them that way),
so source frames map 1:1 and the whole floor(span * tl_fps / src_fps) class of bug disappears.
Read every item back, `AppendToTimeline` computes duration and reports success generously.

    python3 scripts/place_inserts.py --job <job> --timeline "<timeline name>"
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Place insert clips from work/insert_plan.json on a "
                                             "video track, then read every item back.")
    ap.add_argument("--job", required=True, help="job name (under paths.jobs_dir) or folder path")
    ap.add_argument("--timeline", required=True, help="timeline name")
    ap.add_argument("--plan", default="work/insert_plan.json", help="plan file, relative to the job")
    ap.add_argument("--track", type=int, default=2, help="video track (default 2)")
    a = ap.parse_args()

    from resolve_client import R
    job = config.job_dir(a.job)
    plan = json.load(open(job / a.plan))
    r = R()
    proj = r.project
    mp = proj.GetMediaPool()

    tl = r.timeline(a.timeline)
    proj.SetCurrentTimeline(tl)
    start = int(tl.GetStartFrame())
    while int(tl.GetTrackCount("video")) < a.track:
        tl.AddTrack("video")
        print(f"  added video track {int(tl.GetTrackCount('video'))}")

    # import any insert not already in the pool, restore the current folder afterwards, it is sticky
    root = mp.GetRootFolder()
    prev = mp.GetCurrentFolder()
    mp.SetCurrentFolder(root)
    pool = r.pool_items()
    missing = [str(job / "inserts" / p["clip"]) for p in plan
               if Path(p["clip"]).name not in pool]
    if missing:
        print(f"importing {len(missing)} inserts…")
        mp.ImportMedia(sorted(set(missing)))
        pool = r.pool_items()
    mp.SetCurrentFolder(prev or root)

    infos = []
    for p in plan:
        item = pool.get(Path(p["clip"]).name)
        if item is None:
            sys.exit(f"not in media pool: {p['clip']}")
        infos.append({"mediaPoolItem": item,
                      "startFrame": int(p["sf"]), "endFrame": int(p["ef"]),
                      "mediaType": 1, "trackIndex": a.track,
                      "recordFrame": start + int(p["rec"])})
    out = mp.AppendToTimeline(infos)
    print(f"placed {len(out) if out else 0}/{len(infos)}")

    # POP-UPS: zoom/pan a 9:16 clip into a card beside the speaker, instead of letting it fill the
    # frame. Put the card where the speaker's hands point (often the empty third of the frame), so
    # it reads as the speaker presenting it. Set zoom/pan/tilt per plan entry.
    placed = {it.GetName(): it for it in (tl.GetItemListInTrack("video", a.track) or [])}
    for p in plan:
        if not any(k in p for k in ("zoom", "pan", "tilt")):
            continue
        it = placed.get(Path(p["clip"]).name)
        if it is None:
            continue
        for prop, key in (("ZoomX", "zoom"), ("ZoomY", "zoom"), ("Pan", "pan"), ("Tilt", "tilt")):
            if key in p:
                it.SetProperty(prop, float(p[key]))
        got = (round(float(it.GetProperty("ZoomX")), 3), round(float(it.GetProperty("Pan")), 1))
        print(f"  pop-up {it.GetName()}: zoom/pan read back {got}")

    got = tl.GetItemListInTrack("video", a.track) or []
    print(f"\nV{a.track}: {len(got)} items on the track, {len(plan)} in this plan")
    # match by NAME, not by position, a partial plan (adding to an existing track) would otherwise
    # compare item 0 against plan entry 0 and report a false mismatch
    by_name = {it.GetName(): it for it in got}
    bad = []
    for p in plan:
        it = by_name.get(Path(p["clip"]).name)
        if it is None:
            bad.append((p["clip"], "MISSING")); continue
        rec, dur = int(it.GetStart()) - start, int(it.GetDuration())
        want = int(p["ef"]) - int(p["sf"])
        if rec != int(p["rec"]) or dur != want:
            bad.append((it.GetName(), rec, p["rec"], dur, want))
    print(f"  mismatched (rec,dur): {len(bad)}   {bad[:5]}")
    for x, y in zip(got, got[1:]):
        if int(y.GetStart()) < int(x.GetEnd()):
            print(f"  !! overlap at {int(x.GetEnd())-start}")
    print("  names:", [it.GetName() for it in got])
    print("  saved:", r.save())


if __name__ == "__main__":
    main()
