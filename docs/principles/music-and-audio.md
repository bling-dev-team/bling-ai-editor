# Music and audio principles

The voice is the star. Music sits under it to add energy, never to compete. These rules set how loud the bed is, how to prove that level with a measurement, how to clean a voice without making it sound underwater, and how to catch a raw recording that is missing sound before it ever reaches the edit.

Scripts: `scripts/build_music_bed.py` cuts and fades a song into a bed, `scripts/fit_bed.py` fits a bed to the picture length, `scripts/mix_music_bed.py` solves the bed gain against a measurement, `scripts/epidemic.py` fetches tracks from Epidemic Sound (optional), `scripts/verify_resolve.py` reads the timeline back. Levels come from `music.shortform_db_under_voice` and `music.longform_db_under_voice` in `config.yaml`. The format comes from `video.format`, the frame rate from `video.fps`, and your own music folder from `paths.music_dir`.

## The music bed

1. **The bed level is chosen by format, one number per format.**
   Why: on shortform the bed is a foreground element that adds energy. On longform it is subliminal and must never compete. Using the shortform number on a longform makes the music read as a foreground track.
   Numbers: shortform about 12 dB under the voice (median). Longform 26 to 30 dB under; measured longform references sat at a median of 25.8 dB under, p10 20.2 dB, and one sat 35 dB under and still did its job. On longform, the 4 to 10 kHz band sits 48 to 53 dB under the voice and the 40 to 120 Hz band 30 to 42 dB under.
   How to check: read the target from `music.*_db_under_voice` for the `video.format` you are on. On a longform, if you can clearly hear the bed as music, it is already too loud.

2. **A shortform bed set too low is silent, not subtle.**
   Why: a bed 19.8 dB under a -16 LUFS voice was inaudible; its loudest sample was -26.9 dBFS, about 5 percent of full scale. An "18 to 20 dB under" shortform target measures clean and ships silence.
   Numbers: at about 12 dB median separation, p10 lands near 9 dB and p1 near 5 dB, where the speaker drops their voice.
   How to check: measure it, then listen to it. Both.

3. **A recognisable song (not a drone) on shortform sits closer, about 8 dB under.**
   Why: at 12 dB under, a real song is too quiet to feel. The goal is loud enough to hear and feel it, never so loud it drowns the voice.
   Numbers: about 8 dB under integrated (example: song -26.5 LUFS against voice -18.8 LUFS, 7.7 dB apart).
   How to check: measure both with ffmpeg `ebur128` integrated loudness and report the gap. Every word still clear on a phone speaker.

4. **Longform beds are a drone, not a track.**
   Why: references had no drum kit anywhere across an hour of footage. The drive comes from the cut rate, not the music.
   How to check: the bed has no beat that fights the voice's rhythm.

5. **A bed needs energy above 120 Hz.**
   Why: a sub-only bed measures fine on a meter and is inaudible on a phone.
   How to check: look at the bed's spectrum; there must be real content above 120 Hz.

6. **Measure the level, never declare it.**
   Why: a chain of `loudnorm=I=-24`, then `sidechaincompress`, then `alimiter` landed a bed 3.4 dB under the voice instead of about 19, because the compressor's makeup gain and the limiter undid loudnorm, and nothing was measured.
   How to check: set one explicit master gain and solve it against a measurement. `scripts/mix_music_bed.py` iterates the gain until `ebur128` says the target is hit, with no compressor and no limiter in the path, so nothing downstream can undo it.

7. **Report the separation curve, not just two integrated numbers.**
   Why: an integrated LUFS pair can look right while the bed still swamps one loud musical moment.
   Numbers: voice momentary loudness minus bed momentary loudness every 100 ms, reported as percentiles (p1, p10, median, p90) plus the tightest moments.
   How to check: in the mix report, look at p10 and the tightest moments, not only the median.

8. **Watch two ffmpeg traps when you measure.**
   Why: both fail silently and give you NaNs instead of numbers.
   How to check: `ebur128=framelog=verbose` prints nothing unless ffmpeg runs with `-v verbose`. Its lines read `t: 1.699  TARGET:-23 LUFS  M: -18.3 S: ...`, so a regex expecting `M:` right after the timestamp matches nothing. Parse `M:` anywhere on the line.

9. **Never pad silence in front of the bed to line up a drop.**
   Why: prepending silence opens the video on dead air.
   Numbers: start the song EARLIER by the same amount instead, so the drop lands on the same frame and there is music from frame 0. Fade in about 0.6 s.
   How to check: music is audible from the first frame. Use `build_music_bed.py --anchor-in-song <drop seconds> --anchor-on-timeline <seconds>` rather than adding silence.

10. **The bed runs to the last frame of the picture.**
    Why: music that stops early leaves a dead ending.
    Numbers: when the source has more music, run the bed to the end of the picture with a 0.5 s fade out.
    How to check: the bed's end equals the picture's end on the readback.

11. **Fit the bed to the real frame rate and assert the sample count.**
    Why: a bed sized for the wrong frame rate drifts off the picture.
    Numbers: length in seconds is picture frames divided by `video.fps`. Example: 2089 frames at 60 fps is 1,671,200 samples at 48 kHz.
    How to check: pass `--frames` and `--fps` to `scripts/fit_bed.py` (or `--duration <frames/fps>` to `build_music_bed.py`), then read the sample count with ffprobe and compare.

12. **A tight shortform cut gets a flat bed, not a ducker.**
    Why: with no real pauses, a sidechain duck with any usable release time never recovers and collapses to a constant offset. The voice's own dynamics give the bed its lift.
    Numbers: in a tight cut, 96 percent of 10 ms frames sat above -42 dBFS and no pause reached 0.3 s.
    How to check: measure the speech mask first. Only build a ducker if real pauses exist.

13. **The creator places song entries by feel, and you keep them.**
    Why: where a song enters is a taste call.
    How to check: when the creator moves the bed, re-level by rendering a NEW file (for example `song_bed_v2.wav`) and place it at the creator's start and length from the readback. Never overwrite a file already linked in a Resolve timeline.

14. **Music must be licensed, and the source recorded.**
    Why: unlicensed music gets videos muted or taken down. Epidemic Sound is optional: it needs `EPIDEMIC_SOUND_API_KEY` in `.env`, and its Partner API wants both an access key id and a secret, so a single key alone returns 401 Unauthorized.
    How to check: every track comes from `paths.music_dir`, Epidemic Sound through `scripts/epidemic.py`, or another licensed library. Record the track id, because Epidemic asset links are signed and expire in about 10 days; re-fetch by id.

15. **Sound effects attach to text moments, never to cuts.**
    Numbers: one 30 ms tick on about half of the text moments, landing just after the word appears.
    How to check: list each effect's frame and confirm a text moment starts just before it.

## Voice cleanup

16. **"Underwater" is diagnosed by the presence number, not the noise floor.**
    Why: a spectral denoiser can measure a beautiful floor and still take the top end out of the voice.
    Numbers: presence is the 2 to 5 kHz RMS minus the 300 Hz to 1 kHz RMS, on speech. One denoise pass dropped presence from -15.2 to -18.6, 3.4 dB lost, and sounded underwater. Refuse any candidate that loses more than 1 dB of presence. Measure on the loud frames only (p70 and up), or room tone drags the numbers down.
    How to check: measure presence on the original and every cleanup candidate before it ships.

17. **On road or engine noise, expand the gaps, never subtract the spectrum.**
    Why: the noise is mostly rumble below 150 Hz, so a highpass plus a gentle downward expander in the gaps beats any spectral subtraction.
    Numbers: the chain that worked: `highpass=f=150,lowpass=f=12000,agate=threshold=0.03:ratio=2:attack=8:release=150:knee=4,equalizer=f=3500:t=q:w=1.5:g=2`, then the normal voice chain (200 Hz cut, 3 kHz boost, compressor, loudnorm, 48 kHz). Result: gap floor -44 dB in the speech band (10 dB under the original) and presence 1.7 dB above the original, every word intact.
    How to check: re-transcribe the cleaned audio with `scripts/transcribe.py` and confirm every word is still there.

18. **Lifting a quiet second voice: denoise for the noise, then EQ the presence back.**
    Why: denoise strength and tone trade off directly, so restoring the band beats picking a point on that curve. Tune against the main speaker's voice in the same recording, not an absolute target.
    Numbers: compare spectral centroid and the share of energy in 2 to 5 kHz. Main voice 1034 Hz and 0.145; the lift underwater 891 Hz and 0.079; the lift fixed 1060 Hz and 0.161. The steps, in order:
    - Highpass about 180 Hz, not 300 (300 takes the body out). Only go to about 220 on a truly windy stretch.
    - Denoise with `afftdn` and move `nf`, not `nr` (`nr=50` and `nr=97` measured byte identical). `nf=-34` was the knee.
    - Put presence back: `equalizer=f=3000:t=q:w=1.0:g=10` plus `treble=g=6:f=6000`.
    - Clean the gaps with a soft downward expander: `agate=threshold=0.014:ratio=3:attack=8:release=180:range=0.10`. `range=0.10` caps attenuation at 20 dB so it never mutes or sounds choppy.
    - Set the gain so the lifted voice's p90 sits 1 dB under the main voice's p90. Landing it 2 to 3 dB over reads as noisy.
    How to check: re-transcribe each lifted window after gating to prove no syllables were eaten.

19. **Decide who said what from the picture, not the pitch.**
    Why: over car noise, pitch could not separate two speakers.
    How to check: one contact sheet of frames settles every line.

20. **Swap cleaned audio without moving a single cut.**
    Why: re-encoding the picture can shift frames.
    How to check: mux the new audio against the same video stream with `-c:v copy`, then swap the master in Resolve with `MediaPoolItem.ReplaceClip(path)`. After a ReplaceClip the media pool item takes the new file's name, so find it by `GetClipProperty('File Path')`, not the old name.

21. **B-roll is silent.**
    Why: b-roll sound fights the voice and the music.
    How to check: b-roll is placed as video only. Read the timeline back with `scripts/verify_resolve.py` and confirm no b-roll audio.

22. **Read back that the audio track is enabled, and measure the export.**
    Why: enabling a track on a timeline that is not current does nothing and still reports success, so the export ships silent.
    How to check: make the timeline current, enable the track, read the flag back, and measure the export's loudness before it leaves.

## Recording health

23. **A run of bit-exact zeros 120 ms or longer is a recording dropout.**
    Why: those samples are gone and no later step brings them back. Nothing in the edit makes true zeros: room tone, denoise, a closed gate and a soft phrase end all sit around -40 to -80 dB, never exactly 0.0. (The silence bars in `scripts/carve_silence.py` are relative dB and never make zeros.)
    How to check: scan every raw take for runs of exact `0.0` of 120 ms or more before editing, and flag any take that has them.

24. **Once the recorder grows its audio buffer, relaunch it before the next take.**
    Why: screen recorders such as OBS grow a source's audio buffer when an input misses its deadline, and the buffer never shrinks for the life of the process. From then on every stall drops about one buffer length of silence into the mix, in every take of that session. A fresh launch is clean.
    Numbers: a 597 ms buffer gave 619 to 693 ms holes; a 661 ms buffer gave holes up to 1449 ms. "Low latency audio buffering" is the wrong fix: it pins the buffer at 20 ms and makes a jittery device drop out more.
    How to check: read the recorder's log for a line like `adding N milliseconds of audio buffering`. If one appears, relaunch before shooting again.

25. **Check the TOTAL audio buffer, from every source.**
    Why: several small growths from picture-only sources add up and cause the same dropout.
    Numbers: three small steps (149 + 85 + 85 ms) took the total to 320 ms and dropped 1.42 s of zeros. Treat a total of 200 ms or more from any source as a fail.
    How to check: read the `total audio buffering is now N milliseconds` lines. Mute or drop audio on capture sources that only need picture.

26. **Keep the recording at one clock: 48 kHz, no virtual or "default" desktop audio device.**
    Why: a "default" desktop capture can follow the system onto a virtual meeting driver or a 44.1 kHz output against a 48 kHz mix, adding clock domains that make the mic stall.
    How to check: disable global desktop audio capture unless needed (capture one app instead), and confirm the system output is 48 kHz. Setting the sample rate is asynchronous: an immediate read can return the old rate, so poll for it. Keep any deliberate mic sync offset that matches camera latency.

27. **The picture freezes for the same reason the audio drops: no headroom.**
    Why: when the recorder's render thread stalls, it keeps writing a steady stream whose content stops changing, and one stall can freeze picture and punch audio holes together. Disk speed is rarely the cause.
    Numbers: over 1 percent lagged frames means the take has visible freezing. A scene switch is a small version of the same stall. More than about 3 GB of swap in use before a shoot is a reason to reboot first.
    How to check, before and after every take:
    - One capture source per physical device; reuse it, never a second copy.
    - Capture at the size you will show (a picture in picture gets 1280x720, not the device's maximum).
    - No per-frame shader filters on a 4K source; bake corners and shadows into a static image.
    - Mute every picture-only capture source.
    - Read the lagged and skipped frame counts after every take, and reshoot on the spot if over 1 percent.
    - Do not switch scenes mid-sentence; switch on a pause you will cut.
    - Check total frames output divided by the frame rate against the wall clock. A take that does not match has lost material.
    - Keep free disk above 25 GB.

28. **Listen to the final mix on a phone.**
    Why: most viewers hear it on a phone speaker, where music masks words more easily.
    How to check: play the export on a phone at normal volume. Every word should be clear.

29. **No clicks at audio cuts.**
    Why: cutting audio can leave a pop at each join.
    How to check: add a very short fade at every join, then listen to a few.
