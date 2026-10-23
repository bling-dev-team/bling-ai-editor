# Troubleshooting: the twelve most common snags

Start every fix the same way: run `.venv/bin/python doctor.py` and fix any FAIL line it prints. If Resolve is involved, also run `.venv/bin/python scripts/verify_resolve.py`. If your snag is not on this list, copy the exact error text, paste it into Claude Code, and say "fix this."

## 1. Your scripts are missing from Resolve's Workspace > Scripts menu, with no error

- **Symptom:** the menu is empty, or shows only one entry with "canary" in its name.
- **Cause:** Resolve cannot find Python. It needs a folder whose `bin` holds a file named exactly `python3`, set through `PYTHON3HOME`, and Homebrew only ships `python3.12`. Resolve can also lose the variable after it crashes and relaunches itself. An empty menu can also just mean no project is open (the menu is always empty on the project chooser).
- **Fix:** open a project first. Run `scripts/verify_resolve.py`; if it warns `PYTHON3HOME unset`, set it with a LaunchAgent (a shell export never reaches Resolve when it starts from the Dock), then quit and reopen Resolve. Run `doctor.py` again to confirm.

## 2. Everything worked, then suddenly nothing can reach Resolve

- **Symptom:** commands fail, sometimes with an error mentioning Studio or external scripting.
- **Cause:** opening or creating a Resolve project restarts its scripting engine, which kills the bridge. The Studio wording is misleading; ignore it.
- **Fix:** run `scripts/start_bridge.sh`, then `scripts/verify_resolve.py` until it says the bridge is listening on the port in `resolve.bridge_port`. The start script drives Resolve's menus, so your terminal needs Accessibility permission (System Settings, Privacy and Security).

## 3. Every command hangs and Resolve has a dialog open

- **Symptom:** nothing responds; a Save dialog is sitting in Resolve.
- **Cause:** something tried to save a project still called "Untitled Project".
- **Fix:** click the dialog away. Set `resolve.project` in `config.yaml` to a real project name and open that project before the first save.

## 4. Playback is chopped, or looks like slow motion

- **Symptom:** the timeline plays badly, but the cuts look right.
- **Cause:** Resolve's Timeline frame rate and Playback frame rate disagree. Software can set the first but never the second.
- **Fix:** in Project Settings > Master Settings set BOTH by hand to the rate of the clip that carries the voice, and make `video.fps` in `config.yaml` match. The rate cannot change once a timeline holds media, so a wrong one means a new project.

## 5. Every clip is exactly one frame short

- **Symptom:** a steady one-frame loss on every clip.
- **Cause:** something rounded to nearest instead of down, or read the frame rate from ffprobe instead of from Resolve.
- **Fix:** make sure `video.fps` matches the Resolve project, then rebuild the timeline with `scripts/build_timeline_lua.py` (clip lengths use floor). Never fix it by nudging clips one at a time. Read it back with `scripts/verify_resolve.py`.

## 6. You changed the caption style and nothing changed, but every check passed

- **Symptom:** new `captions.*` settings in `config.yaml`, same old cards on screen.
- **Cause:** cached cards were reused, or new renders were written under their old filenames, so Resolve kept showing the old frames.
- **Fix:** the cache key must include every visual setting, and every new render needs a new filename. Rebuild with `scripts/build_caption_clips.py`, then place them again with `scripts/place_caption_clips.py`. Never overwrite a file Resolve already has in a timeline.

## 7. Little black flashes at every b-roll cut, or an insert comes out pure black

- **Symptom:** one-frame black at cuts, or a fully black insert.
- **Cause:** b-roll placed at a different frame rate from the timeline, or a grade applied to 10-bit footage without converting the pixel format first.
- **Fix:** pre-render every insert at the timeline's rate and size (`video.fps`, `video.width`, `video.height`) with any grade baked in, then place them again with `scripts/place_inserts.py`. Check them with `scripts/audit_broll.py`.

## 8. A word you can clearly hear is missing, or a repeated word will not show up

- **Symptom:** the transcript reads clean but the audio has a stammer or a restart.
- **Cause:** speech recognition merges words that repeat back to back.
- **Fix:** find the silences by measuring the sound, then transcribe each burst on its own in non-overlapping windows with `scripts/transcribe.py`. See `docs/principles/alignment.md`, rules 8 to 12.

## 9. The cut slices into the middle of words, or a whole phrase went missing

- **Symptom:** `scripts/tighten.py` or `scripts/carve_silence.py` cuts inside a word.
- **Cause:** the word file still holds the transcript's guessed times instead of the aligned ones, or a number written in digits confused the aligner.
- **Fix:** run `scripts/align_words.py` and rewrite the word file from the aligned times, spell numbers out before aligning, then tighten again. See `docs/principles/alignment.md`, rules 2 and 7.

## 10. The exported video is silent

- **Symptom:** the timeline plays with sound; the export has none.
- **Cause:** the audio track was enabled while its timeline was not current, so the command did nothing and still reported success.
- **Fix:** make the timeline current, enable the track, read the flag back with `scripts/verify_resolve.py`, and measure the export's loudness before it leaves.

## 11. iPhone footage looks pale and washed out, or too bright

- **Symptom:** phone clips look nothing like they do on the phone.
- **Cause:** it is HLG footage that was not converted with Apple's own converter.
- **Fix:** do not grade it. Convert the source file with Apple's converter, put the converted file in `paths.footage_dir` or `paths.broll_dir`, and rebuild.

## 12. An upload or a transcription hangs, or every request fails with a quota error

- **Symptom:** transfers stall, or each one fails with a rate or quota message.
- **Cause:** several transfers run at once and share one quota. For transcription, Groq's free tier caps audio at 7200 seconds per hour.
- **Fix:** stop them all, run one, and wait for it. `scripts/transcribe.py` already waits out the "try again in" hint on its own. For a long file, budget the hour or set `transcription.engine: whisperx` in `config.yaml` (slow on CPU). Check `GROQ_API_KEY` with `doctor.py`.

## Still stuck

Run `.venv/bin/python doctor.py`, and if Resolve is involved `.venv/bin/python scripts/verify_resolve.py`, and send both outputs to your Bling contact. If setup itself looks broken, run `./setup.sh` again; it is safe to rerun.
