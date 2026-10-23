#!/usr/bin/env bash
# One-time setup on macOS. Safe to run again.
#   ./setup.sh
set -uo pipefail
cd "$(dirname "$0")"

say() { printf '\n== %s\n' "$*"; }

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is missing. Install it from https://brew.sh then run ./setup.sh again."
  exit 1
fi

say "ffmpeg"
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "ffmpeg already installed: $(command -v ffmpeg)"
else
  brew install ffmpeg
fi

say "python 3.12"
PY312="$(command -v python3.12 || true)"
if [[ -z "$PY312" ]]; then
  brew install python@3.12
  PY312="$(brew --prefix python@3.12)/bin/python3.12"
fi
echo "using $PY312"

say "virtual env (.venv)"
if [[ ! -x .venv/bin/python ]]; then
  "$PY312" -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt

say "whisperx (optional, local transcription)"
if .venv/bin/python -c "import whisperx" >/dev/null 2>&1; then
  echo "whisperx already installed"
else
  .venv/bin/python -m pip install whisperx \
    || echo "whisperx did not install. That is OK: Groq is the default. Fix it later if you want local transcription."
fi

say "hyperframes CLI (node)"
if ! command -v npm >/dev/null 2>&1; then
  brew install node
fi
if command -v hyperframes >/dev/null 2>&1; then
  echo "hyperframes already installed"
else
  npm i -g hyperframes \
    || echo "global install failed. You can still run it with: npx hyperframes"
fi

say "config files"
[[ -f config.yaml ]] || { cp config.example.yaml config.yaml; echo "made config.yaml. Open it and fill it in."; }
mkdir -p jobs assets/fonts
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then cp .env.example .env; else printf 'GROQ_API_KEY=\nEPIDEMIC_SOUND_API_KEY=\n' > .env; fi
  echo "made .env. Paste your GROQ_API_KEY into it."
fi

say "doctor"
.venv/bin/python doctor.py
