#!/usr/bin/env python3
"""Check that this computer is ready to run the editor scripts.

    python3 doctor.py

Prints PASS, FAIL or WARN for each check, with a plain fix. Exits 1 if a required check fails.
"""
import argparse
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

results = []   # (status, name, fix)


def check(name, passed, fix, required=True, detail=""):
    status = "PASS" if passed else ("FAIL" if required else "WARN")
    results.append((status, name, fix))
    line = f"[{status}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not passed:
        print(f"       Fix: {fix}")


def run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[:1]
    except Exception as e:
        return False, [str(e)]


def main():
    argparse.ArgumentParser(description="Check that this computer is ready to run the scripts.").parse_args()
    print(f"Doctor for {ROOT}\n")

    # python
    v = sys.version_info
    check("Python 3.10 or newer", v >= (3, 10),
          "Run ./setup.sh. It makes a .venv with Python 3.12. Then use .venv/bin/python.",
          detail=f"{v.major}.{v.minor}.{v.micro} at {sys.executable}")

    # requirements
    mods = {"PyYAML": "yaml", "python-dotenv": "dotenv", "numpy": "numpy", "Pillow": "PIL"}
    for pkg, mod in mods.items():
        try:
            importlib.import_module(mod)
            ok = True
        except Exception:
            ok = False
        check(f"Python package {pkg}", ok,
              "Run: .venv/bin/python -m pip install -r requirements.txt")

    # tools on PATH
    for t in ("ffmpeg", "ffprobe"):
        p = shutil.which(t)
        check(f"{t} on PATH", bool(p), "Run: brew install ffmpeg", detail=p or "")
    node = shutil.which("node")
    npx = shutil.which("npx")
    check("node and npx", bool(node and npx), "Run: brew install node",
          detail=f"{node or '-'} / {npx or '-'}")
    node_major = 0
    if node:
        try:
            node_major = int(subprocess.run([node, "-p", "process.versions.node.split('.')[0]"],
                                            capture_output=True, text=True).stdout.strip() or 0)
        except Exception:
            node_major = 0
    check("Node.js 22 or newer (for hyperframes)", node_major >= 22, "Run: brew upgrade node",
          detail=f"node {node_major or '-'}", required=False)
    hf = shutil.which("hyperframes")
    if hf:
        check("hyperframes CLI", True, "", detail=hf)
    else:
        check("hyperframes CLI", False,
              "Run: npm install -g hyperframes  (or use npx hyperframes each time)", required=False)

    # whisperx (optional)
    try:
        has_wx = importlib.util.find_spec("whisperx") is not None
    except Exception:
        has_wx = False
    check("whisperx (only for local transcription)", has_wx,
          "Optional. Run: .venv/bin/python -m pip install whisperx", required=False)

    # config
    cfg_file = ROOT / "config.yaml"
    check("config.yaml exists", cfg_file.is_file(),
          "Copy config.example.yaml to config.yaml and fill it in.")
    try:
        import config
        for key, required in (("paths.jobs_dir", True), ("paths.fonts_dir", True),
                              ("paths.footage_dir", False), ("paths.broll_dir", False),
                              ("paths.music_dir", False)):
            p = config.path(key)
            if p is None:
                check(f"{key} is set", not required, f"Set {key} in config.yaml.", required)
                continue
            check(f"{key} folder exists", p.is_dir(),
                  f"Make the folder {p}, or change {key} in config.yaml.", required, str(p))
        f = config.font_file()
        check("caption font file exists", bool(f and f.is_file()),
              "Put your font file in paths.fonts_dir and set brand.font_file in config.yaml.",
              detail=str(f) if f else "brand.font_file not set")
        fps = config.get("video.fps")
        check("video.fps is a number", isinstance(fps, (int, float)) and fps > 0,
              "Set video.fps in config.yaml, for example 30.", detail=str(fps))
        engine = config.get("transcription.engine", "groq")
    except SystemExit as e:
        check("config loads", False, str(e))
        engine = "groq"
    except Exception as e:
        check("config loads", False, f"Fix config.yaml. Error: {e}")
        engine = "groq"

    # secrets (never print the value)
    key = os.environ.get("GROQ_API_KEY", "").strip()
    check("GROQ_API_KEY is set", bool(key),
          "Open the .env file and paste your Groq key after GROQ_API_KEY=",
          required=(engine == "groq"))

    # Resolve
    app = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
    check("DaVinci Resolve installed", app.exists() or Path("/Applications/DaVinci Resolve").exists(),
          "Download DaVinci Resolve from blackmagicdesign.com and install it.",
          detail=str(app))
    try:
        import resolve_client
        resolve_client.import_native_module()
        mod_ok = True
    except Exception:
        mod_ok = False
    check("Resolve scripting module importable", mod_ok,
          "Install DaVinci Resolve. The module lives in /Library/Application Support/"
          "Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules.", required=False)

    # bridge / live connection, with a short timeout
    out = {}

    def _try():
        try:
            from resolve_client import connect_resolve
            res = connect_resolve()
            out["ok"] = bool(res)
        except Exception as e:
            out["err"] = str(e)[:160]

    t = threading.Thread(target=_try, daemon=True)
    t.start()
    t.join(8)
    if t.is_alive():
        out["err"] = "timed out after 8 s"
    check("Resolve reachable (bridge or scripting)", out.get("ok", False),
          "Open Resolve and a project, then run scripts/start_bridge.sh. "
          "Run scripts/verify_resolve.py for details.", required=False,
          detail=out.get("err", ""))

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print(f"\n{len(results) - len(fails) - len(warns)} pass, {len(warns)} warn, {len(fails)} fail")
    if fails:
        print("Fix the FAIL lines above, then run python3 doctor.py again.")
        sys.exit(1)
    print("Ready.")


if __name__ == "__main__":
    main()
