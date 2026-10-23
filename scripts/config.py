#!/usr/bin/env python3
"""Shared settings for every script in this folder.

Loads <repo>/config.yaml (falls back to config.example.yaml with a warning) and <repo>/.env.
The repo root is found relative to this file, so the scripts work from any folder.

    from config import CFG, get, path, FFMPEG, FFPROBE, FPS
    fps = get("video.fps", 30)
    footage = path("paths.footage_dir")

Run it directly to print the settings it found:  python3 scripts/config.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / "config.yaml"
EXAMPLE_FILE = ROOT / "config.example.yaml"
ENV_FILE = ROOT / ".env"


def _load_env():
    if not ENV_FILE.is_file():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=False)
        return
    except ImportError:
        pass
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and v and k not in os.environ:
            os.environ[k] = v


def _load_cfg():
    src = CONFIG_FILE
    if not src.is_file():
        src = EXAMPLE_FILE
        if src.is_file():
            print(f"warning: no config.yaml, using {EXAMPLE_FILE.name}. "
                  f"Copy it to config.yaml and fill it in.", file=sys.stderr)
        else:
            print("warning: no config.yaml or config.example.yaml found, using defaults.",
                  file=sys.stderr)
            return {}, None
    try:
        import yaml
    except ImportError:
        sys.exit("pyyaml is missing. Run: pip install -r requirements.txt")
    data = yaml.safe_load(src.read_text()) or {}
    return data, src


_load_env()
CFG, CFG_SOURCE = _load_cfg()


def get(key: str, default=None):
    """Dotted lookup, e.g. get('video.fps', 30)."""
    cur = CFG
    for part in key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return default if cur is None else cur


def path(key: str, default=None) -> Path | None:
    """A config value as an absolute Path. Relative paths resolve against the repo root."""
    v = get(key, default)
    if v in (None, ""):
        return None
    p = Path(os.path.expanduser(str(v)))
    return p if p.is_absolute() else (ROOT / p).resolve()


def tool(name: str) -> str:
    """Find a command on PATH (ffmpeg, ffprobe, ...). Falls back to the bare name."""
    return shutil.which(name) or name


FFMPEG = tool("ffmpeg")
FFPROBE = tool("ffprobe")
FPS = float(get("video.fps", 30))
WIDTH = int(get("video.width", 1080))
HEIGHT = int(get("video.height", 1920))


def jobs_dir() -> Path:
    return path("paths.jobs_dir", "./jobs")


def job_dir(name_or_path: str | None = None) -> Path:
    """Resolve a job folder: an explicit path, a job name under paths.jobs_dir, or $JOB_DIR."""
    v = name_or_path or os.environ.get("JOB_DIR")
    if not v:
        sys.exit("no job given. Pass --job <name> or set JOB_DIR.")
    p = Path(os.path.expanduser(v))
    if p.is_absolute() or p.exists():
        return p.resolve()
    return jobs_dir() / v


def font_file() -> Path | None:
    d = path("paths.fonts_dir", "./assets/fonts")
    f = get("brand.font_file")
    return (d / f) if (d and f) else None


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description="Print the settings the scripts will use.").parse_args()
    print(f"repo root : {ROOT}")
    print(f"config    : {CFG_SOURCE}")
    print(f"ffmpeg    : {FFMPEG}")
    print(f"ffprobe   : {FFPROBE}")
    print(f"fps       : {FPS:g}  ({WIDTH}x{HEIGHT})")
    print(f"jobs_dir  : {jobs_dir()}")
    print(f"font      : {font_file()}")
