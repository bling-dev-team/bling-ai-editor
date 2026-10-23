#!/usr/bin/env python3
"""Minimal client for the Epidemic Sound MCP server (streamable HTTP + SSE).

The server lives at EPIDEMIC_SOUND_MCP_URL and authenticates with a plain
`Authorization: Bearer <EPIDEMIC_SOUND_API_KEY>` header, it is an Apollo MCP
server fronting their GraphQL API, NOT the Partner Content API. The Partner
Content API (partner-content-api.epidemicsound.com) rejects this kind of key, so
do not use it here.

Optional: only needed if you license music from Epidemic Sound. Put
EPIDEMIC_SOUND_API_KEY in the repo .env.

Usage:
    python3 scripts/epidemic.py tools
    python3 scripts/epidemic.py call <tool_name> '<json args>'
"""
import json
import os
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _env() -> dict:
    env = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


class Epidemic:
    def __init__(self):
        env = _env()
        self.key = os.environ.get("EPIDEMIC_SOUND_API_KEY") or env.get("EPIDEMIC_SOUND_API_KEY")
        self.url = (os.environ.get("EPIDEMIC_SOUND_MCP_URL")
                    or env.get("EPIDEMIC_SOUND_MCP_URL")
                    or "https://www.epidemicsound.com/a/mcp-service/mcp")
        if not self.key:
            raise SystemExit("EPIDEMIC_SOUND_API_KEY not set (repo .env)")
        self.session = None
        self._id = 0
        self._initialize()

    def _post(self, payload, notify=False):
        self._id += 1
        payload.setdefault("jsonrpc", "2.0")
        if not notify:
            payload.setdefault("id", self._id)
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            if self.session is None:
                self.session = r.headers.get("mcp-session-id")
            body = r.read().decode()
        # streamable HTTP replies as SSE: pull the last `data:` JSON frame
        out = None
        for line in body.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    try:
                        out = json.loads(chunk)
                    except json.JSONDecodeError:
                        pass
        if out is None and body.strip():
            try:
                out = json.loads(body)
            except json.JSONDecodeError:
                out = {"raw": body}
        return out

    def _initialize(self):
        self._post({
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "editor-repo", "version": "1.0"},
            },
        })
        self._post({"method": "notifications/initialized"}, notify=True)

    def tools(self):
        return self._post({"method": "tools/list", "params": {}})

    def call(self, name, args=None):
        return self._post({"method": "tools/call",
                           "params": {"name": name, "arguments": args or {}}})


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    e = Epidemic()
    cmd = sys.argv[1]
    if cmd == "tools":
        res = e.tools()
        for t in res.get("result", {}).get("tools", []):
            print(f"\n### {t['name']}\n{t.get('description','').strip()[:400]}")
            print("  schema:", json.dumps(t.get("inputSchema", {}))[:800])
    elif cmd == "call":
        args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(e.call(sys.argv[2], args), indent=2)[:20000])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
