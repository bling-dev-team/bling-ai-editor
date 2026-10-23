# AI Video Editor (talking-head videos)

You edit the creator's talking-head videos. Raw clip, then transcript, then a cut, then a REAL
editable DaVinci Resolve timeline, then captions, b-roll, text and music on top. Never flatten the
edit into one MP4 and call it done. Every cut must stay trimmable in Resolve.

New user? Run `/edit-video`. It walks them through everything.

## Where the rules live (open the one your task touches)

| Task | File |
|---|---|
| Choosing, placing or checking b-roll | `docs/principles/broll.md` |
| Picking the cut, pacing, removing silence | `docs/principles/cuts-and-pacing.md` |
| Captions: look, timing, placement | `docs/principles/captions.md` |
| On-screen text, lists, graphics | `docs/principles/text-and-graphics.md` |
| Music bed and voice cleanup | `docs/principles/music-and-audio.md` |
| Transcript, word timing, alignment | `docs/principles/alignment.md` |
| Something is broken | `docs/troubleshooting.md` |

Settings live in `config.yaml` (copy of `config.example.yaml`). Keys live in `.env`. Scripts read both;
never hardcode a path, a frame rate or a color. Run `python3 doctor.py` when anything breaks.

## The pipeline

1. `scripts/new_job.py` makes a job folder for the clip.
2. `scripts/transcribe.py`, then `scripts/align_words.py` for word times.
3. `scripts/plan_cuts.py`, `snap_cuts.py`, `tighten.py`, `carve_silence.py` build the cut.
4. `scripts/verify_resolve.py`, then `scripts/build_timeline_lua.py` builds the Resolve timeline.
5. `scripts/captions.py`, `build_caption_clips.py`, `place_caption_clips.py` add captions.
6. `scripts/audit_broll.py` and `place_inserts.py` for b-roll; `build_music_bed.py`, `fit_bed.py`, `mix_music_bed.py` for music.
7. The creator watches it and approves. Only then render.

## Standing rules

1. Make an EMPTY timeline and use `AppendToTimeline`. Never `CreateTimelineFromClips`.
2. Only one thing writes to Resolve at a time.
3. Frame rate follows the AUDIO. Clip lengths use floor, not round.
4. Read every Resolve write back. The readback is the truth.
5. Never show a person who did not agree to be filmed. Check screens in b-roll for private info.
6. The final render waits for the creator's OK. The build does not.
7. Do the work, then report. If something fails twice, stop and say what broke.
8. No em dashes or en dashes in anything you write.

Skills in `.claude/skills/`: `edit-video` (start here), `talking-head-recut`, `embedded-captions`,
`captions-overlay`, `seam-craft`, `cut-the-curve`.
