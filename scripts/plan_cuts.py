#!/usr/bin/env python3
"""cuts.json (seconds) -> clip_infos (frames) for AppendToTimeline into an EMPTY timeline.

Never feed these to CreateTimelineFromClips: it places items in the wrong timebase when the
source rate differs from the timeline rate. Create an empty timeline, then AppendToTimeline.

The three invariants that cost an hour if you get them wrong:
  1. start/end_frame are SOURCE frames at the raw's frame rate, not timeline frames.
  2. end_frame is EXCLUSIVE -> duration = end_frame - start_frame.
  3. record_frame is timeline-relative and cumulative; readback carries a
     01:00:00:00 offset (add 3600*fps to compare against a readback timecode).

FPS AUTHORITY: pass --fps from GetClipProperty('FPS') *after* the clip is in the
media pool. ffprobe is only a first read, iPhone .MOV is VFR and ffprobe says
29.97 where Resolve ingests a flat 30.00.
"""
import argparse, json, sys
from fractions import Fraction
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="Turn cuts.json (seconds) into clip_infos.json (source frames).")
    ap.add_argument("cuts", help="path to cuts.json: [{start,end}, ...] in seconds")
    ap.add_argument("--fps", required=True, help="authority fps from GetClipProperty('FPS'), e.g. 30 or 29.97")
    ap.add_argument("--clip-id", required=True, help="media pool clip id")
    ap.add_argument("-o", "--out", help="default: alongside cuts.json as clip_infos.json")
    a = ap.parse_args()

    fps = float(Fraction(a.fps)) if "/" in a.fps else float(a.fps)
    if fps <= 0:
        sys.exit("fps must be positive")

    cuts = json.loads(Path(a.cuts).read_text())
    if isinstance(cuts, dict):
        cuts = cuts.get("cuts", cuts.get("segments", []))

    infos, record, warnings = [], 0, []
    prev_end = None
    for i, c in enumerate(cuts):
        s, e = float(c["start"]), float(c["end"])
        if e <= s:
            sys.exit(f"cut {i}: end ({e}) must be after start ({s})")
        if prev_end is not None and s < prev_end:
            warnings.append(f"cut {i} starts at {s} before cut {i-1} ended at {prev_end} (overlap)")
        prev_end = e
        start_f = int(round(s * fps))
        end_f = int(round(e * fps))          # exclusive
        if end_f <= start_f:
            end_f = start_f + 1              # never emit a zero-length clip
        infos.append({
            "clip_id": a.clip_id,
            "start_frame": start_f,
            "end_frame": end_f,
            "record_frame": record,
        })
        record += end_f - start_f            # duration = end - start, exclusive

    out = Path(a.out) if a.out else Path(a.cuts).parent / "clip_infos.json"
    out.write_text(json.dumps(infos, indent=1))

    total_f = record
    print(json.dumps({
        "fps_used": fps,
        "clips": len(infos),
        "timeline_frames": total_f,
        "timeline_seconds": round(total_f / fps, 3),
        "readback_offset_frames": int(round(3600 * fps)),
        "readback_start_timecode": "01:00:00:00",
        "warnings": warnings,
        "out": str(out),
    }, indent=2))
    if warnings:
        print("\nWARNING: overlapping cuts above, fix cuts.json before building.", file=sys.stderr)
    print("\nAfter building: verify with get_items_in_track, then SAVE the project immediately.")
    print("If every clip duration reads back off by a uniform 1.001 factor, the frame-rate model")
    print("is wrong -> delete and rebuild the project at the right rate. Never nudge single frames.")

if __name__ == "__main__":
    main()
