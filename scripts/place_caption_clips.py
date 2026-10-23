#!/usr/bin/env python3
"""Place one caption clip per card on V3, so every caption is a trimmable timeline item.

Replaces the single flattened `captions_overlay_vN.mov`: each 2-3 word card is its own clip,
aligned to the VO and b-roll cuts.

    python3 scripts/place_caption_clips.py --job <job> "<timeline name>" [track]

Clips (not stills, not Fusion titles) because only a clip of real frames honours `endFrame` , 
see `scripts/build_caption_clips.py` for why the other two routes do not work.
"""
from __future__ import annotations

import os as _os

import os

import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config                                         # noqa: E402

if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Place one caption clip per card on a video track "
                                              "of a Resolve timeline, then read it back.")
    _ap.add_argument("timeline", help="timeline name (always by name, never 'the current one')")
    _ap.add_argument("track", nargs="?", type=int, default=4, help="video track (default 4)")
    _ap.add_argument("--job", help="job name or folder; default $JOB_DIR")
    ARGS = _ap.parse_args()
    if ARGS.job:
        os.environ["JOB_DIR"] = str(config.job_dir(ARGS.job))

from resolve_client import R                          # noqa: E402

JOB   = Path(os.environ.get("JOB_DIR", "."))
import json as _j
_cfg_p = JOB / "work" / _os.environ.get("CAPTION_CONFIG", "caption_config.json")
_cfg = _j.load(open(_cfg_p)) if _cfg_p.exists() else {}
# The cache directory carries the font/size/position/plate variant, not just `style`.
# build_caption_clips.py writes its name here, this script runs on the Resolve venv, which has
# no PIL, so it cannot import render_caption_frames to recompute it.
_dirf = JOB / "work/caption_clip_dir.json"
_STYLE_DIR = _j.load(open(_dirf))["style_dir"] if _dirf.exists() else _cfg.get("style", "border")
CLIPS = JOB / f"graphics/caption-clips-{int(_cfg.get('fps', config.FPS))}-{_STYLE_DIR}"
BIN   = f"Captions {int(_cfg.get('fps', config.FPS))} {_STYLE_DIR}"
BATCH = 40


def bin_folder(r):
    mp = r.media_pool(); root = mp.GetRootFolder()
    for f in (root.GetSubFolderList() or []):
        if f.GetName() == BIN:
            return f
    return mp.AddSubFolder(root, BIN)


def run(timeline, track=4):
    """Captions go on V4 by default.

    The track is CLEARED before placing. If V3 holds text elements, placing captions on V3 wipes
    them, and the readback still reports clean because it only looks at the track it was given.
    Pass the track explicitly.
    """
    plan = json.load(open(JOB / "work/caption_clip_plan.json"))
    r = R(); mp = r.media_pool(); tl = r.timeline(timeline)
    r.project.SetCurrentTimeline(tl)
    S = int(tl.GetStartFrame())

    # Resolve creates NEW TIMELINES inside whatever the pool's current folder is, so leaving it
    # pointed at the captions bin silently nests later timelines in there. Restore it at the end.
    prev_folder = mp.GetCurrentFolder()
    folder = bin_folder(r)
    mp.SetCurrentFolder(folder)
    # Look the clips up by REALPATH across the WHOLE pool, not by name inside one bin.
    # Two reasons, both of which have bitten: (1) a caption clip's filename is a hash of its
    # TEXT only, so style variants collide by basename and a by-name hit can be the stale
    # entry from another directory, which puts items Media Offline; (2) a previous session
    # can leave the clips at the pool ROOT rather than in this bin, and then this scan of one
    # folder finds nothing, tries to re-import, and Resolve REFUSES a file already in the pool
    #, so the import "fails" with every file present and correct on disk.
    def by_path() -> dict:
        out = {}
        def walk(f):
            for c in (f.GetClipList() or []):
                fp = c.GetClipProperty("File Path")
                if fp:
                    out[os.path.realpath(fp)] = c
            for sub in (f.GetSubFolderList() or []):
                walk(sub)
        walk(mp.GetRootFolder())
        return out

    want = sorted({p["clip"] for p in plan})
    have = by_path()
    missing = [str((CLIPS / n).resolve()) for n in want
               if str((CLIPS / n).resolve()) not in have]
    if missing:
        print(f"importing {len(missing)} clips…")
        for i in range(0, len(missing), 50):
            mp.ImportMedia(missing[i:i + 50])
        have = by_path()
    pool = {n: have[str((CLIPS / n).resolve())] for n in want
            if str((CLIPS / n).resolve()) in have}
    absent = [n for n in want if n not in pool]
    assert not absent, f"some caption clips did not import: {absent[:5]}"

    # AppendToTimeline silently places NOTHING when the target track does not exist, and the
    # readback then compares two empty lists and reports success. Create the tracks first.
    while int(tl.GetTrackCount("video")) < track:
        print(f"  adding video track {int(tl.GetTrackCount('video'))+1}")
        tl.AddTrack("video")

    old = tl.GetItemListInTrack("video", track) or []
    if old:
        print(f"clearing V{track}: {len(old)} items ->", tl.DeleteClips(old))

    for i in range(0, len(plan), BATCH):
        chunk = plan[i:i + BATCH]
        mp.AppendToTimeline([{"mediaPoolItem": pool[p["clip"]], "startFrame": 0,
                              "endFrame": p["dur"], "mediaType": 1, "trackIndex": track,
                              "recordFrame": S + p["rec"]} for p in chunk])
        print(f"  placed {min(i+BATCH, len(plan))}/{len(plan)}")

    items = sorted(tl.GetItemListInTrack("video", track) or [], key=lambda x: int(x.GetStart()))
    got = [(int(x.GetStart()) - S, int(x.GetDuration())) for x in items]
    want_ = [(p["rec"], p["dur"]) for p in plan]
    bad = [(a, b) for a, b in zip(want_, got) if a != b]
    gaps = [(got[k - 1][0] + got[k - 1][1], got[k][0])
            for k in range(1, len(got)) if got[k][0] != got[k - 1][0] + got[k - 1][1]]
    print(f"\nV{track}: {len(items)} items (planned {len(plan)})")
    if len(items) != len(plan):
        print(f"  FAIL: placed {len(items)} of {len(plan)}, an empty track is not a pass")
    print(f"  mismatched (rec,dur): {len(bad)}   {bad[:5]}")
    print(f"  gaps/overlaps: {len(gaps)}   {gaps[:5]}")
    print(f"  head {got[0][0] if got else None}  tail {got[-1][0]+got[-1][1] if got else None}")
    if prev_folder:
        mp.SetCurrentFolder(prev_folder)          # restore the pool's current folder
    print("  saved:", r.save())
    return not bad and not gaps and len(items) == len(plan)


if __name__ == "__main__":
    ok = False
    for attempt in range(4):
        try:
            ok = run(ARGS.timeline, ARGS.track); break
        except Exception as e:
            print("retry:", str(e)[:100]); time.sleep(8)
    sys.exit(0 if ok else 1)
