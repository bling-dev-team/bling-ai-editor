#!/usr/bin/env python3
"""Read a timeline back from an FCP7 XML export (Resolve: Timeline:Export(path, 3)).

When Python scripting or the bridge cannot reach Resolve, the Lua Scripts menu still runs and
Timeline:Export still writes files. So a timeline can be READ BACK by exporting it to xmeml and
parsing that file offline. The output matches what GetItemListInTrack gives: per track a list of
{start, end, dur, in, out, name, path, enabled}, with start/end in TIMELINE frames relative to the
sequence start (0 based, exclusive end).

    python3 scripts/xmeml_readback.py <export.xml> [-o readback.json] [--fps N]

--fps defaults to video.fps in config.yaml and is only used to warn when the export's timebase
does not match it. No ffmpeg needed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def parse(path):
    root = ET.parse(path).getroot()
    seq = root.find("sequence") if root.tag != "sequence" else root
    if seq is None:
        sys.exit(f"no <sequence> in {path}. Is this an FCP7 XML export?")
    out = {"name": seq.findtext("name"), "duration": int(seq.findtext("duration") or 0),
           "timebase": int(seq.findtext("rate/timebase") or 0), "tracks": {}}
    files = {}
    for kind in ("video", "audio"):
        media = seq.find(f"media/{kind}")
        if media is None:
            continue
        for ti, track in enumerate(media.findall("track"), start=1):
            items = []
            for ci in track.findall("clipitem"):
                f = ci.find("file")
                fpath = None
                if f is not None:
                    fid = f.get("id")
                    url = f.findtext("pathurl")
                    if url:
                        files[fid] = urllib.parse.unquote(urllib.parse.urlparse(url).path)
                    fpath = files.get(fid)
                s, e = int(ci.findtext("start")), int(ci.findtext("end"))
                items.append({"start": s, "end": e, "dur": e - s,
                              "in": int(ci.findtext("in")), "out": int(ci.findtext("out")),
                              "name": ci.findtext("name"), "path": fpath,
                              "enabled": (ci.findtext("enabled") or "TRUE") == "TRUE"})
            items.sort(key=lambda x: x["start"])
            out["tracks"][f"{'V' if kind == 'video' else 'A'}{ti}"] = items
    return out


def main():
    ap = argparse.ArgumentParser(description="Parse an FCP7 XML timeline export into a per-track "
                                             "readback (JSON).")
    ap.add_argument("xml", help="the .xml file written by Timeline:Export(path, 3)")
    ap.add_argument("-o", "--out", help="write the readback JSON here")
    ap.add_argument("--fps", type=float, default=config.FPS,
                    help="expected timeline fps (default video.fps from config.yaml)")
    a = ap.parse_args()
    rb = parse(a.xml)
    if rb["timebase"] and round(a.fps) != rb["timebase"]:
        print(f"warning: export timebase {rb['timebase']} does not match fps {a.fps}",
              file=sys.stderr)
    for t, items in rb["tracks"].items():
        tail = max((i["end"] for i in items), default=0)
        missing = sum(1 for i in items if i["path"] and not Path(i["path"]).exists())
        print(f"{t}: {len(items)} items, tail {tail}"
              + (f", {missing} missing on disk" if missing else ""))
    if a.out:
        Path(a.out).write_text(json.dumps(rb, indent=1))
        print("wrote", a.out)


if __name__ == "__main__":
    main()
