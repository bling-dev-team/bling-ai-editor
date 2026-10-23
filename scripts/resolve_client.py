#!/usr/bin/env python3
"""Direct native-API client for DaVinci Resolve.

Two ways in, tried in order:
  1. The in-app bridge from a davinci-resolve-mcp checkout (set resolve.mcp_dir in config.yaml).
     Works on the free edition, once the bridge script is running inside Resolve.
  2. Blackmagic's own scripting module (DaVinciResolveScript). External scripting needs
     Resolve Studio, or "Local" scripting turned on in Preferences > General.

`R().project`, `R().timeline("VO Cut v1")` return live Resolve objects, so anything the
scripting API can do is reachable.

**The bridge drops whenever Resolve restarts its scripting host** (a project create/load does
that), and every call after the drop fails with NOT_CONNECTED. `R.call()` retries through
`scripts/start_bridge.sh` once.

Engineering rules this repo follows on top of the API:
  * Build into an EMPTY timeline with AppendToTimeline. Never CreateTimelineFromClips: it places
    items in the wrong timebase when the source rate differs from the timeline rate.
  * Item duration is floor(span * tl_fps / src_fps), not round. Walk the span until the floor
    lands on the frame count you want, then read the item back.
  * Frame rate follows the AUDIO clip: GetClipProperty('FPS') beats ffprobe.
  * Read every write back. AppendToTimeline reports success generously.

    from resolve_client import R
    r = R()
    tl = r.timeline("VO Cut v1")
    print(r.call(tl, "GetTrackCount", "audio"))

    python3 scripts/resolve_client.py          # connect once and print the project name
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

BRIDGE_SH = Path(__file__).resolve().parent / "start_bridge.sh"
os.environ.setdefault("DAVINCI_RESOLVE_BRIDGE", "1")

# Standard locations of Blackmagic's scripting module.
RESOLVE_API_DIRS = [
    os.environ.get("RESOLVE_SCRIPT_API", ""),
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
    str(Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/"
        "Developer/Scripting"),
    "C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting",
    "/opt/resolve/Developer/Scripting",
]
RESOLVE_LIB_DEFAULT = ("/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/"
                       "Fusion/fusionscript.so")


def import_native_module():
    """Import DaVinciResolveScript from the standard RESOLVE_SCRIPT_API paths. Returns the module."""
    os.environ.setdefault("RESOLVE_SCRIPT_LIB", RESOLVE_LIB_DEFAULT)
    try:
        import DaVinciResolveScript as dvr  # type: ignore
        return dvr
    except ImportError:
        pass
    for d in RESOLVE_API_DIRS:
        mods = Path(d) / "Modules" if d else None
        if mods and mods.is_dir():
            sys.path.insert(0, str(mods))
            try:
                import DaVinciResolveScript as dvr  # type: ignore
                return dvr
            except ImportError:
                continue
    raise ImportError("DaVinciResolveScript not found in the standard Resolve scripting paths")


def _bridge_client():
    mcp = config.path("resolve.mcp_dir")
    if not mcp or not mcp.is_dir():
        return None
    if str(mcp) not in sys.path:
        sys.path.insert(0, str(mcp))
    from src.utils import resolve_bridge_client as bc  # type: ignore
    return bc


def connect_resolve():
    """Return a live `resolve` object, via the bridge if configured, else the native module."""
    errors = []
    try:
        bc = _bridge_client()
        if bc is not None:
            return bc.connect()
    except Exception as exc:
        errors.append(f"bridge: {exc}")
    try:
        dvr = import_native_module()
        res = dvr.scriptapp("Resolve")
        if res:
            return res
        errors.append("native: scriptapp('Resolve') returned None (is Resolve open? external "
                      "scripting needs Studio, or Local scripting on)")
    except Exception as exc:
        errors.append(f"native: {exc}")
    raise ConnectionError("could not reach DaVinci Resolve. " + " | ".join(errors))


class R:
    def __init__(self):
        self.connect()

    def connect(self):
        self.resolve = connect_resolve()
        self.pm = self.resolve.GetProjectManager()
        self.project = self.pm.GetCurrentProject()
        return self

    def _restart_bridge(self):
        subprocess.run([str(BRIDGE_SH)], capture_output=True, text=True, timeout=180)
        self.connect()

    def call(self, obj, method, *args):
        """Invoke a method, healing one bridge drop. `obj` may be a live proxy or a
        zero-arg callable that re-derives one (proxies are invalid after a reconnect)."""
        try:
            target = obj() if callable(obj) and not hasattr(obj, method) else obj
            return getattr(target, method)(*args)
        except Exception as exc:
            if "NOT_CONNECTED" not in str(exc) and "not connected" not in str(exc).lower():
                raise
            self._restart_bridge()
            target = obj() if callable(obj) else obj
            return getattr(target, method)(*args)

    #, convenience -------------------------------------------------------

    def timeline(self, name):
        """Fetch a timeline BY NAME. Never operate on 'the current timeline', the user
        switches timelines in the GUI while a script is running."""
        n = int(self.project.GetTimelineCount())
        for i in range(1, n + 1):
            tl = self.project.GetTimelineByIndex(i)
            if tl.GetName() == name:
                return tl
        raise KeyError(f"no timeline named {name!r} (have: "
                       f"{[self.project.GetTimelineByIndex(i).GetName() for i in range(1, n + 1)]})")

    def media_pool(self):
        return self.project.GetMediaPool()

    def pool_items(self, folder=None):
        """Flatten the media pool to {name: MediaPoolItem}."""
        folder = folder or self.media_pool().GetRootFolder()
        out = {}
        for c in (folder.GetClipList() or []):
            out[c.GetName()] = c
        for sub in (folder.GetSubFolderList() or []):
            out.update(self.pool_items(sub))
        return out

    def set_project_fps_from(self, media_pool_item, width=None, height=None):
        """Set the project rate from the clip that carries the AUDIO, the standing rule is that
        frame rate follows the audio, and `GetClipProperty('FPS')` is authority over ffprobe.

        Returns (fps, playback_ok). **`timelinePlaybackFrameRate` cannot be written by any script
        path**, project SetSetting, timeline SetSetting and videoMonitorFormat were all tried and
        all return False. If it disagrees with the timeline rate the GUI plays back at
        playback/timeline speed (24 against 60 = 0.4x, which reads as slow motion), so this
        reports the mismatch loudly instead of leaving it to be discovered by eye.
        """
        fps = float(media_pool_item.GetClipProperty("FPS"))
        self.project.SetSetting("timelineFrameRate", str(int(fps) if fps == int(fps) else fps))
        if width and height:
            self.project.SetSetting("timelineResolutionWidth", str(width))
            self.project.SetSetting("timelineResolutionHeight", str(height))
        got = float(self.project.GetSetting("timelineFrameRate"))
        pb = self.project.GetSetting("timelinePlaybackFrameRate")
        ok = abs(float(pb) - got) < 0.01 if pb else False
        if not ok:
            print(f"  !! PLAYBACK FRAME RATE IS {pb}, TIMELINE IS {got:g}, playback will run at "
                  f"{float(pb)/got:.2f}x (slow motion).")
            print( "     Not scriptable. Fix by hand: Project Settings > Master Settings > "
                   "Playback frame rate.")
        return got, ok

    def save(self):
        # SaveProject lives on the ProjectManager, not the Project, in this build.
        return self.pm.SaveProject()


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(description="Connect to DaVinci Resolve once and print the current "
                                        "project and its timelines.").parse_args()
    r = R()
    print("project:", r.project.GetName() if r.project else None)
    if r.project:
        n = int(r.project.GetTimelineCount())
        print("timelines:", [r.project.GetTimelineByIndex(i).GetName() for i in range(1, n + 1)])
