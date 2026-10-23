# AI Video Editor

This repo lets Claude Code edit your talking-head videos for you. It cuts the dead air, adds
captions, b-roll, text and music, and builds a real DaVinci Resolve timeline you can still change
by hand. It follows a proven set of editing rules, so you do not have to build the system yourself.

Background (the long version): [Editing SOP Google Doc](https://docs.google.com/document/d/1DK7yLDrB4Vk9oZKReWtQ_GQnqRH5dZVIv6CNW4fTaK4)

## What you need

- A Mac
- [Claude Code](https://claude.com/claude-code)
- [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) (free or Studio)
- [Homebrew](https://brew.sh)
- A free Groq API key from [console.groq.com](https://console.groq.com) (this makes the transcript)

## 10 minute quickstart

1. **Get the code.** Open Terminal and run:
   ```
   git clone https://github.com/bling-dev-team/bling-ai-editor.git
   cd bling-ai-editor
   ```
2. **Set it up.** Run `./setup.sh`. It installs ffmpeg, Python 3.12, WhisperX and the HyperFrames
   tool. Then it checks everything. This takes about 5 minutes.
3. **Add your key.** Open the `.env` file. Paste your Groq key after `GROQ_API_KEY=`. Save it.
4. **Add your settings.** Open `config.yaml`. Set where your raw clips live (`footage_dir`), your
   Resolve project name, your brand colors and your font. Put your font file in `assets/fonts/`.
5. **Open Resolve.** Open DaVinci Resolve and your project.
6. **Check again.** Run `.venv/bin/python doctor.py`. Every line should say PASS. If one says FAIL,
   do what the line tells you.
7. **Edit.** Run `claude` in this folder. Type `/edit-video`. Tell it which clip. It does the rest.
8. **Look at it.** Watch the new timeline in Resolve. Tell Claude what to change. Say "render" when
   you like it.

## What is inside

- `CLAUDE.md` tells Claude how this repo works.
- `docs/principles/` holds the editing rules: b-roll, cuts and pacing, captions, text and graphics,
  music and audio, word timing.
- `scripts/` holds the tools that do the work.
- `.claude/skills/` holds the skills. Start with `/edit-video`.
- `doctor.py` checks your computer and tells you how to fix what is missing.

## Keep it private

Your `.env`, `config.yaml`, videos and renders never get uploaded. The `.gitignore` file blocks
them. Never paste a key into any other file.

## Stuck?

Look up your problem in [docs/troubleshooting.md](docs/troubleshooting.md) first.

Run `.venv/bin/python doctor.py` and send the output to your Bling contact.
