# Transcript and alignment principles

Every other step (cuts, captions, text) depends on knowing exactly when each word is said. The transcript gives you the words. The waveform gives you the timing. These rules keep both honest.

Scripts: `scripts/transcribe.py` makes the transcript, `scripts/align_words.py` lines each word up with the audio, `scripts/snap_cuts.py` moves boundaries onto the real sound. Frame rate comes from `video.fps` in `config.yaml`.

## Rules

1. **The waveform is the timing authority.**
   Why: the transcriber guesses where words start and end. The sound wave shows where they really are.
   How to check: for key words, look at the voice band energy (about 300 to 6000 Hz) and confirm the word time sits on the real start of the sound.

2. **The transcriber is trusted for timing ranges, not for word order.**
   Why: transcribers often clean up speech. They drop repeats, fix grammar and smooth over restarts.
   How to check: when something looks off, listen to that spot. Trust your ears over the text.

3. **Hidden repeats and self corrections are real, and the transcript hides them.**
   Why: when the creator says "the the" or restarts a sentence, the transcript often writes it once. The doubled audio stays in the cut and sounds like a stutter.
   How to check: look for a word or phrase that takes far longer than its words should. Play each burst of sound alone and transcribe it alone. Two bursts for one word means a repeat.

4. **Do not trust a tiny window to name a small word.**
   Why: a very short clip of audio gets misheard, especially words like "a", "the" or "to".
   How to check: transcribe a little context around the word, then narrow down.

5. **When the creator gives a timecode, go to that frame.**
   Why: they heard it. Searching the transcript instead can miss it again.
   How to check: open the exact frame and listen.

6. **Expand numbers before aligning.**
   Why: the transcript writes "10,000" but the creator says "ten thousand". The aligner cannot match digits to sound, so the timing breaks around numbers.
   How to check: turn each number into its spoken words, align those, then join the words back into the number with the first word's start and the last word's end. Expand by place value ("one hundred twenty three"), not from a fixed lookup table.

7. **Watch for words smeared across a pause or a laugh.**
   Why: the aligner can stretch a word over a breath or a laugh, which makes its timing useless.
   How to check: flag any word much longer than normal. Snap it to the actual sound.

8. **Cut and caption tools read the aligned times.**
   Why: if a tool reads the raw transcript, it uses the wrong times.
   How to check: the word file the other scripts read holds the aligned times after `scripts/align_words.py` runs.

9. **Fixes live in the master, not in one timeline.**
   Why: a fix made by hand in a timeline is lost on the next rebuild. Remapping words through a new cut list can also undo earlier fixes.
   How to check: write every fix into the master transcript or plan. After a rebuild, confirm each fix is still there.

10. **Adjust, do not restart.**
    Why: re-running the whole transcript throws away fixes.
    How to check: patch the specific words. Keep one master transcript per video.

11. **Re-transcribe the edit to prove it.**
    Why: the only real proof the edit kept the right words is to listen to it again.
    How to check: run `scripts/transcribe.py` on the edited audio and compare word for word against the plan.

12. **Loudness steps can fool silence detection.**
    Why: after loudness normalizing, room tone gets louder and a fixed silence bar stops working.
    How to check: set silence relative to each phrase's peak, not a fixed number.

13. **Know your transcription limits.**
    Why: hosted transcription services can cap how much audio you send per hour.
    How to check: split long audio into chunks and plan for limits so a long video does not stall halfway.
