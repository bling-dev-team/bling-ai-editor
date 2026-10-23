---
name: edit-video
description: Beginner entry point. Edit a talking-head video end to end with the house editing principles. Use when the user says /edit-video, "edit my video", "cut this clip", or is new to this repo and does not know where to start.
---

# /edit-video

Talk to the user in plain, short words. Ask one thing at a time. Do the work yourself.

## Step 0: Is the computer ready?
Run `python3 doctor.py`. If anything FAILs, read the fix line to the user and do the fixes you can
(`./setup.sh`, copy config files). Only ask the user for things you cannot do, like pasting their
GROQ_API_KEY into `.env` or opening DaVinci Resolve.

## Step 1: Which video?
Ask for the clip (a file path, or a file in `paths.footage_dir` from `config.yaml`). Ask: shortform
(vertical, under 90 seconds) or longform? Set `video.format` and size to match.

## Step 2: Make the job and the transcript
`python3 scripts/new_job.py <clip> --title "<short title>"`, then `scripts/transcribe.py` and
`scripts/align_words.py`. Read `docs/principles/alignment.md` and fix hidden repeats and numbers.

## Step 3: Cut it
Read `docs/principles/cuts-and-pacing.md`. Choose the best take of each line, cut the restarts and
dead air (`plan_cuts.py`, `snap_cuts.py`, `tighten.py`, `carve_silence.py`). Do not ask for approval
of the cut list; make the call and note it in your report.

## Step 4: Build the Resolve timeline
`python3 scripts/verify_resolve.py` (Resolve must be open with the project from `resolve.project`),
then `scripts/build_timeline_lua.py`. Read it back and check the length.

## Step 5: Dress it
Captions (`docs/principles/captions.md`), b-roll (`docs/principles/broll.md`), text
(`docs/principles/text-and-graphics.md`), music (`docs/principles/music-and-audio.md`). Use the other
skills when they fit: `embedded-captions` and `captions-overlay` for styled captions, `seam-craft` for
clean joins, `cut-the-curve` for pacing, `talking-head-recut` for card style recuts.

## Step 6: Hand it over
Tell the user the timeline name, what you cut and why, and anything to check by eye. Wait for their OK
before rendering.
