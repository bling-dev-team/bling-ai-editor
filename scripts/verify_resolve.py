#!/usr/bin/env python3
"""End-to-end check: can the scripts reach DaVinci Resolve right now?

Run this whenever a Resolve call errors. On the FREE edition the usual answer is
"the in-app bridge isn't running": Workspace > Scripts > resolve_bridge (needs a project open),
or run scripts/start_bridge.sh.

    python3 scripts/verify_resolve.py
"""
import argparse, json, socket, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

RT = Path.home() / ("Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/"
                    ".davinci_mcp_runtime/bridge.json")


def ok(m):   print(f"  \033[32mok\033[0m    {m}")
def bad(m):  print(f"  \033[31mFAIL\033[0m  {m}")
def warn(m): print(f"  \033[33mwarn\033[0m  {m}")


def main():
    argparse.ArgumentParser(description="Check that Resolve is running and reachable from the "
                                        "scripts (bridge or native API).").parse_args()
    fails = []
    print("\nResolve preflight\n")

    running = subprocess.run(["pgrep", "-f", "DaVinci Resolve.app/Contents/MacOS/Resolve"],
                             capture_output=True).returncode == 0
    (ok if running else bad)("Resolve is running" if running else "Resolve is NOT running. Open it.")
    if not running:
        fails.append("resolve")

    mcp = config.path("resolve.mcp_dir")
    if mcp:
        p3h = subprocess.run(["launchctl", "getenv", "PYTHON3HOME"], capture_output=True,
                             text=True).stdout.strip()
        if p3h:
            ok(f"PYTHON3HOME = {p3h}")
        else:
            warn("PYTHON3HOME unset. The bridge script may not appear in Workspace > Scripts.")
        if RT.is_file():
            cfg = json.loads(RT.read_text())
            host, port = cfg.get("host", "127.0.0.1"), cfg.get("port")
        else:
            host, port = "127.0.0.1", int(config.get("resolve.bridge_port", 8765))
            warn("bridge.json missing. Install the bridge from your davinci-resolve-mcp checkout.")
        with socket.socket() as s:
            s.settimeout(1.5)
            listening = s.connect_ex((host, int(port))) == 0
        if listening:
            ok(f"bridge listening on {host}:{port}")
        else:
            bad(f"bridge NOT listening on {host}:{port}")
            print("        -> open a project, then run scripts/start_bridge.sh")
            fails.append("bridge")
    else:
        warn("resolve.mcp_dir not set; using Blackmagic's native scripting module only")

    try:
        from resolve_client import R
        r = R()
        ok(f"connected; project = {r.project.GetName() if r.project else None}")
    except Exception as e:
        bad(f"could not connect: {str(e)[:200]}")
        fails.append("connect")

    print()
    if fails:
        print(f"NOT READY: {', '.join(fails)}\n")
        sys.exit(1)
    print("READY: Resolve scripting works.\n")


if __name__ == "__main__":
    main()
