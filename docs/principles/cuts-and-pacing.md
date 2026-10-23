# Cuts and pacing principles

Cuts decide how a video feels. Too loose and people scroll. Too tight and words get chopped. These rules tell you where to cut, how tight to go, and how to prove nothing was lost.

Scripts: `scripts/plan_cuts.py` plans the edit, `scripts/snap_cuts.py` moves cuts onto the real sound, `scripts/tighten.py` closes gaps, `scripts/carve_silence.py` cuts from the waveform, `scripts/build_timeline_lua.py` builds the timeline, `scripts/verify_resolve.py` reads it back. Frame rate comes from `video.fps` in `config.yaml`.

## Rules

1. **Cut between phrases, never inside a word.**
   Why: a cut in the middle of a word sounds broken. A cut in the gap between phrases sounds natural.
   How to check: play 1 second on each side of every cut. Each word should be whole.

2. **When two people talk, only cut the creator's phrases.**
   Why: cutting the other person mid thought changes what they said.
   How to check: know who is talking at each cut. Use the picture (whose mouth moves) to tell voices apart, not pitch alone.

3. **Shortform is cut from the waveform, not from word gaps.**
   Why: the transcriber guesses where words start and end. Those guesses leave dead air or clip word endings. The sound wave is the truth.
   How to check: run `scripts/carve_silence.py`, which reads the voice band (about 300 to 6000 Hz) in small steps and keeps only the parts with speech. `scripts/tighten.py` alone is not enough for shortform.

4. **The "end of phrase" bar is relative to each phrase's own peak.**
   Why: a fixed loudness bar eats the quiet last word of a soft phrase and keeps noise after a loud one.
   How to check: set the cut point where energy falls a set amount below that phrase's peak. Listen to the last word of the quietest phrases.

5. **Snap every cut onto the measured sound.**
   Why: a cut a frame or two early clips the first sound of a word.
   How to check: run `scripts/snap_cuts.py`. It walks from the planned cut to where the sound really starts or ends.

6. **Merge away slivers.**
   Why: a cut that saves a tiny bit of time but leaves a piece under about 0.25 seconds reads as a jump.
   How to check: list every kept piece. Merge any piece under about 0.25 seconds into its neighbour.

7. **Remove clicks at the joins.**
   Why: cutting audio can leave a sudden jump in the wave, which you hear as a pop.
   How to check: look at the sample values on both sides of each join. Add a very short fade (a few milliseconds) at every join that jumps.

8. **Match pacing to the creator's own past edits, not to a feeling.**
   Why: "tight" means different things to different people. The creator's best past videos are the target.
   How to check: measure average cut length and longest hold on 2 or 3 past videos the creator likes. Compare your edit's numbers to them.

9. **"An edit every 1 to 2 seconds" means captions, not picture cuts.**
   Why: good references change the caption that often, but the picture can hold longer. Cutting the picture that often feels frantic.
   How to check: count caption changes and picture cuts on your edit separately.

10. **Longform screen shares are paced by jump cuts.**
    Why: on a screen share the picture barely changes, so the pace comes from removing dead time in the talking.
    How to check: count jump cuts per minute and compare to a past longform the creator likes.

11. **Cut retakes, self corrections and hidden repeats.**
    Why: when the creator restarts a sentence, only the last good take should stay. Transcripts often hide these. See `alignment.md`.
    How to check: look for a phrase that takes too long for its words, or a word that shows up twice in a row.

12. **When the creator names the words to cut, cut those words.**
    Why: they know what they said. Do not swap in your own idea of the cut.
    How to check: find the quoted words in the aligned transcript and confirm they are gone, and only they are gone.

13. **A shot can keep its head if it has a reason.**
    Why: sometimes a pause or a look before speaking is the moment. Tight is the default, not a law.
    How to check: if the creator puts a pause back, keep it on every rebuild by writing it into the plan, not only the timeline.

14. **Prove the words did not change.**
    Why: tight cutting can drop a word without anyone noticing.
    How to check: run `scripts/transcribe.py` on the rebuilt edit and compare the words to the plan. They must match exactly. Any word that fell in a cut slice is also missing from the captions, so recount.

15. **Re-cutting settles, so repeat until nothing moves.**
    Why: each trim changes the audio a little, which shifts the next measurement.
    How to check: run plan, snap and carve again. Stop when the cut list stops changing.

16. **Keep the talking head look consistent.**
    Why: if footage from different takes or cameras looks different, the jump is obvious.
    How to check: make sure all footage is graded and tone mapped the same way before cutting. Compare a frame from each take side by side.

17. **Rebuild from the plan, then read it back.**
    Why: a timeline edited by hand gets lost on the next rebuild. The plan is the source of truth.
    How to check: build with `scripts/build_timeline_lua.py`, then run `scripts/verify_resolve.py`: no gaps, every cut where the plan says, at `video.fps`.
