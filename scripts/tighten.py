#!/usr/bin/env python3
"""Shortform 'every millisecond counts' pass.

Takes approved keep-ranges and tightens them at the WORD level:
  - collapses intra-phrase pauses down to a floor
  - trims lead/tail padding to the audibility minimum
The floor exists because aligner word boundaries sit slightly INSIDE the real word;
cutting to literal zero clips consonant onsets.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import job_dir  # noqa: E402

def main():
    ap = argparse.ArgumentParser(description="Tighten keep-ranges at the word level (collapse pauses, trim pads).")
    ap.add_argument("--job", required=True, help="job name (under paths.jobs_dir) or folder path")
    ap.add_argument("--cuts", default="transcript/cuts_annotated.json", help="cuts file relative to --job")
    ap.add_argument("--gap", type=float, default=0.15, help="pauses longer than this get collapsed")
    ap.add_argument("--floor", type=float, default=0.06, help="pause length left behind")
    ap.add_argument("--lead", type=float, default=0.04)
    ap.add_argument("--tail", type=float, default=0.06)
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    job = job_dir(a.job)
    words = json.load(open(job/"transcript/words.json"))["words"]
    approved = json.load(open(job/a.cuts))

    out = []
    for c in approved:
        ws = [w for w in words if w["start"] >= c["start"]-0.02 and w["end"] <= c["end"]+0.02]
        if not ws:
            out.append({"start": c["start"], "end": c["end"]}); continue
        # split this phrase wherever an internal pause exceeds --gap
        runs, cur = [], [ws[0]]
        for prev, nxt in zip(ws, ws[1:]):
            if nxt["start"] - prev["end"] > a.gap:
                runs.append(cur); cur = [nxt]
            else:
                cur.append(nxt)
        runs.append(cur)
        for r in runs:
            s = max(0.0, r[0]["start"] - a.lead)
            e = r[-1]["end"] + a.tail
            out.append({"start": round(s,3), "end": round(e,3)})

    # merge anything now closer than the floor, and enforce ordering
    merged = [out[0]]
    for c in out[1:]:
        if c["start"] - merged[-1]["end"] < a.floor:
            merged[-1]["end"] = max(merged[-1]["end"], c["end"])
        else:
            merged.append(c)
    for i in range(1, len(merged)):
        assert merged[i]["start"] >= merged[i-1]["end"], f"overlap at {i}"

    dest = Path(a.out) if a.out else job/"transcript/cuts_tight.json"
    json.dump(merged, open(dest,"w"), indent=1)
    kept = sum(c["end"]-c["start"] for c in merged)
    prev = sum(c["end"]-c["start"] for c in approved)
    print(json.dumps({
        "segments_before": len(approved), "segments_after": len(merged),
        "seconds_before": round(prev,2), "seconds_after": round(kept,2),
        "saved_seconds": round(prev-kept,2), "out": str(dest)}, indent=2))

if __name__ == "__main__":
    main()
