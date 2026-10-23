# Music and audio principles

The voice is the star. Music sits under it to add energy, never to compete. These rules set how loud the music bed is, how to prove it, and how to keep the voice clean.

Scripts: `scripts/build_music_bed.py` builds and levels the bed, `scripts/verify_resolve.py` reads the timeline back. Levels come from the `music.*_db_under_voice` keys in `config.yaml` (one for shortform, one for longform).

## Rules

1. **The music level is chosen by format.**
   Why: shortform needs energy, so the bed sits closer to the voice. Longform is a long listen, so the bed sits far under it.
   How to check: shortform bed about 12 dB under the voice. Longform bed 26 to 30 dB under the voice. Read the exact numbers from `music.*_db_under_voice`, do not hardcode them.

2. **A song with vocals or a strong melody can sit a bit closer on shortform.**
   Why: a real song is part of the feel, not just a pad. Around 8 dB under is a common starting point.
   How to check: listen on a phone speaker. Every word must still be clear.

3. **Measure the level, never declare it.**
   Why: setting a gain number does not tell you what the viewer hears. A bed set "20 dB under" can be totally silent in practice.
   How to check: measure the loudness of the voice and the bed in the final mix, and report the real gap. If the bed's loudest moment is barely audible, it is too low.

4. **No silent lead in before the music.**
   Why: padding silence in front of a track to line up a drop leaves the start of the video dead.
   How to check: music is audible from the first frame. Line up drops by trimming the track, not by adding silence.

5. **A tight shortform does not need ducking.**
   Why: when the voice runs almost the whole time, a ducker just pumps. A steady bed sounds better.
   How to check: if the voice is active almost all the time, use a flat bed level. Ducking is for longform with real pauses.

6. **Music source is optional and must be licensed.**
   Why: unlicensed music gets videos muted or taken down.
   How to check: every track comes from a library the creator has a license for, or is made for them. Keep a note of the source for each track.

7. **The creator places song entries by feel.**
   Why: where the drop lands is a taste call.
   How to check: if the creator has marked where the music enters, keep it on every rebuild.

8. **Normalize the voice first.**
   Why: you can only set the bed relative to a steady voice level.
   How to check: measure voice loudness before setting the bed. Keep the voice level the same across every video so they sound consistent.

9. **Clean a quiet second voice by fixing noise, then adding presence back.**
   Why: noise removal makes a voice thin. A small boost in the presence range brings it back.
   How to check: compare before and after on the quiet speaker. They should be clearer, not hollow.

10. **For steady noise like a car, quiet the gaps, do not strip the sound.**
    Why: heavy noise removal on a voice makes it sound robotic. Turning down the gaps between words keeps the voice natural.
    How to check: listen to the gaps and the words. Gaps should be quieter, words should sound normal.

11. **Watch for dead audio in the raw footage.**
    Why: recording software can drop the voice to total silence for a stretch. If you do not catch it, a whole take is ruined.
    How to check: scan the raw audio for runs of exact zero longer than about 120 ms. Flag them before editing. Before recording, do a short test and play it back.

12. **No clicks at audio cuts.**
    Why: cutting audio can leave a pop at each join.
    How to check: add a very short fade at every join, then listen to a few.

13. **B-roll is silent.**
    Why: b-roll sound fights the voice and the music.
    How to check: b-roll is placed as video only. Read the timeline back with `scripts/verify_resolve.py` and confirm no b-roll audio.

14. **Listen to the final mix on a phone.**
    Why: most viewers hear it on a phone speaker, where music masks words more easily.
    How to check: play the export on a phone at normal volume. Every word should be clear.
