#!/bin/bash
# Start the Resolve in-app bridge without doing the Workspace > Scripts menu dance by hand.
# Launches Resolve if needed, clicks Workspace > Scripts > resolve_bridge, waits for the port.
#
# The bridge itself comes from a davinci-resolve-mcp checkout (config.yaml resolve.mcp_dir) and
# must already be installed into Resolve (that project's install_resolve_bridge.py).
#
# Requires: Terminal (or whatever runs this) allowed under
#   System Settings > Privacy & Security > Accessibility
#
#   scripts/start_bridge.sh          start it
#   scripts/start_bridge.sh --help   this text
set -uo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n 2,13p "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HERE/../.venv/bin/python"; [[ -x "$PY" ]] || PY=python3
BRIDGE_JSON="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/.davinci_mcp_runtime/bridge.json"
CFG_PORT=$(cd "$HERE" && "$PY" -c "import config;print(config.get('resolve.bridge_port', 8765))" 2>/dev/null || echo 8765)
PORT=$("$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['port'])" "$BRIDGE_JSON" 2>/dev/null || echo "$CFG_PORT")

listening() { nc -z 127.0.0.1 "$PORT" 2>/dev/null; }

if listening; then echo "bridge already listening on 127.0.0.1:$PORT"; exit 0; fi

if ! pgrep -f "DaVinci Resolve.app/Contents/MacOS/Resolve" >/dev/null; then
  echo "launching DaVinci Resolve..."
  open -a "DaVinci Resolve"
  for i in $(seq 1 90); do
    pgrep -f "DaVinci Resolve.app/Contents/MacOS/Resolve" >/dev/null && break
    sleep 1
  done
  echo "waiting for the UI to settle..."
  sleep 25
fi

echo "clicking Workspace > Scripts > resolve_bridge..."
RESULT=$(osascript <<'AS' 2>&1
tell application "System Events"
  tell process "DaVinci Resolve"
    try
      click menu item "resolve_bridge" of menu 1 of menu item "Scripts" of menu 1 of menu bar item "Workspace" of menu bar 1
      return "clicked"
    on error e
      return "ERR: " & e
    end try
  end tell
end tell
AS
)
echo "  $RESULT"

case "$RESULT" in
  ERR*)
    echo
    echo "Could not click the menu. Two usual causes:"
    echo "  1. Accessibility permission not granted to this terminal"
    echo "     -> System Settings > Privacy & Security > Accessibility"
    echo "  2. 'resolve_bridge' is not in the menu at all -> Python not detected."
    echo "     Check: launchctl getenv PYTHON3HOME   (it must point at a Python 3 install)"
    echo "     and that \$PYTHON3HOME/bin/python3 exists by that exact name."
    exit 1 ;;
esac

for i in $(seq 1 30); do
  listening && { echo "bridge listening on 127.0.0.1:$PORT after ${i}s"; exit 0; }
  sleep 1
done

echo "clicked, but the bridge never opened the port."
echo "Open a project first. The Scripts menu does nothing from the Project Manager."
exit 1
