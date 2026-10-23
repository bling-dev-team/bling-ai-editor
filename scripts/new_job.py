#!/usr/bin/env python3
"""Intake: copy a raw clip into a new job folder. Never moves or modifies the original.

    python3 scripts/new_job.py ~/Movies/raw-footage/take1.mov "morning routine breakdown"

Makes <paths.jobs_dir>/<kebab-title>/{raw,transcript,work,graphics,audio,inserts,outputs} and a
job.json with the ffprobe read. A bare clip name is looked up in paths.footage_dir.
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def kebab(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-+", "-", s) or "untitled"


def ffprobe(path):
    out = subprocess.run(
        [config.FFPROBE, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate,avg_frame_rate,width,height,duration",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser(description="Copy a raw clip into a new job folder and probe it.")
    ap.add_argument("clip", help="path to the raw clip, or a file name inside paths.footage_dir")
    ap.add_argument("title", help="short content-based title, e.g. 'morning routine breakdown'")
    a = ap.parse_args()

    src = Path(a.clip).expanduser()
    if not src.is_file():
        fd = config.path("paths.footage_dir")
        if fd and (fd / a.clip).is_file():
            src = fd / a.clip
    src = src.resolve()
    if not src.is_file():
        sys.exit(f"no such file: {src}")

    job = config.jobs_dir() / kebab(a.title)
    for sub in ("raw", "transcript", "work", "graphics", "audio", "inserts", "outputs"):
        (job / sub).mkdir(parents=True, exist_ok=True)

    dest = job / "raw" / src.name
    if dest.exists():
        print(f"already present: {dest}")
    else:
        shutil.copy2(src, dest)   # copy2, never move: the original is untouched

    probe = ffprobe(dest)
    st = probe["stream"][0] if "stream" in probe else probe["streams"][0]
    meta = {
        "job": job.name,
        "raw": str(dest),
        "source_original": str(src),
        "ffprobe_r_frame_rate": st.get("r_frame_rate"),
        "ffprobe_avg_frame_rate": st.get("avg_frame_rate"),
        "width": st.get("width"), "height": st.get("height"),
        "duration_sec": float(probe.get("format", {}).get("duration") or st.get("duration") or 0),
        "config_fps": config.FPS,
        "fps_authority": "UNRESOLVED: read GetClipProperty('FPS') after importing to the media pool",
    }
    (job / "job.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    print(f"\njob folder: {job}")
    print("NOTE: ffprobe fps is the FIRST read only. After importing to the Resolve media pool,")
    print("      read GetClipProperty('FPS') and treat THAT as authority for project fps + frame math.")
    print("      Frame rate follows the AUDIO clip.")


if __name__ == "__main__":
    main()
