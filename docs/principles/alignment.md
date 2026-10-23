# Transcript and alignment principles

Every other step (cuts, captions, text) depends on knowing exactly when each word is said. The transcript gives you the words. The waveform gives you the timing. These rules keep both honest.

Scripts: `scripts/transcribe.py` makes the transcript (Groq by default), `scripts/align_words.py` force aligns each word to the audio, `scripts/snap_cuts.py` moves boundaries onto the real sound, `scripts/tighten.py` and `scripts/carve_silence.py` cut pauses. Settings: `transcription.engine` (groq or whisperx), `transcription.language`, `transcription.whisperx_python`, and `video.fps` in `config.yaml`. The Groq key is `GROQ_API_KEY` in `.env`.

## Timing

1. **The waveform is the timing authority, not the transcriber.**
   Why: the transcriber's word onsets are guesses. Measured against forced alignment they were off by up to 667 ms, with 41 of 62 words off by more than 3 frames, in both directions, so it is not a constant you can subtract.
   Numbers: after forced alignment, caption starts land a median of 1 ms from the measured onset.
   How to check: run `scripts/align_words.py` (the wav2vec2 aligner only, text from the transcript, timing from the audio). For key words, confirm the onset sits on the start of energy in the 300 to 6000 Hz band.

2. **The tools that cut must read the ALIGNED times.**
   Why: if the word file still holds the transcriber's onsets (up to 0.3 s off), tighten and carve land inside words and can drop whole phrases.
   How to check: right after `align_words.py`, rewrite the word file the cutters read with the aligned times, and keep the raw copy under another name. After carving, list any word whose aligned onset is earlier than a carved range's start. A clean carve report is not proof.

3. **Trust the transcriber's segment text for word ORDER, not its word list.**
   Why: the word list can swap two adjacent timestamps, float a word into the previous phrase, come back one token short, and carry almost no punctuation (1 of 64 words). The segment text has the right order and the punctuation.
   How to check: `scripts/transcribe.py` rebuilds the tokens per segment from the segment text and pairs them with the segment's sorted onsets, and tags each word with its segment index as the sentence break. Do not use a difflib alignment: a swap reads as an insert plus a delete and duplicates tokens.

4. **Derive pauses from aligned words, not a level gate, and pick the threshold from the data.**
   Why: after loudness normalization, room tone rose to -29 to -33 dBFS, so a -32 dB gate read it as speech and left 0.58 s of dead air.
   Numbers: normal gaps between words ran 60 to 120 ms and real pauses began around 230 ms, so 220 ms was the split point. Measure your own clip and choose the split the same way.
   How to check: cut boundaries come from aligned word start and end times.

5. **Re-cutting converges, so iterate.**
   Why: trimming to aligned boundaries changes the audio slightly, which shifts the next alignment.
   Numbers: a second pass took a clip from 19.24 s to 18.25 s and drove leftover dead air to zero.
   How to check: run align, tighten, carve a second time and confirm the dead air total drops toward zero.

6. **Re-seat any word smeared across a non-verbal.**
   Why: the aligner spends its slack on a hum, a laugh or a breath, stretching a word across it (one word started 2.7 s early; another was placed inside pure silence). Cutters then cut on those false spans.
   Numbers: flag any aligned word longer than about 1 s, or with a score under about 0.3.
   How to check: move the onset to the measured 300 to 6000 Hz envelope onset before tightening or carving.

7. **Expand numbers to spoken words before aligning, by position.**
   Why: "$71,433" is 7 characters and 2.9 s of speech. The aligner places the characters and reports the rest as a pause, so the tightener cuts the middle out of the line.
   How to check: expand every digit token to its spoken form with `num2words` (place value, "seventy one thousand four hundred thirty three dollars", never a fixed lookup table), keep a per segment list of (index, word count, original token), align the spoken text, then collapse each run back by position: start is the first word's onset, end the last word's offset. The caption still shows "$71,433" and holds for the full time it is said. A segment that lost a word in alignment can leave its run spoken; that is harmless for cutting, only captions would show it. Catch misses with the envelope: a "gap" inside continuous 300 to 6000 Hz energy is not a gap.

## Hidden repeats

8. **Whole phrase transcription hides repeats and self corrections.**
   Why: the transcriber de-duplicates. "And the... and the best part" comes back as one "And the". A self correction ("videos for... from my editors") reads as "for from" in a wide window and collapses to "for" in a narrow one, so every whole phrase pass looks clean. Re-running that same check is how one fix took six rounds.
   How to check: find the silences in the 300 to 6000 Hz envelope and transcribe each burst on its own, in DISJOINT windows aligned to those boundaries. Two overlapping windows both reading a word are consistent with one word.

9. **Use the redundancy test.**
   Why: a single word cannot survive losing a third of itself.
   Numbers: remove about 7 to 10 frames and re-transcribe.
   How to check: if the phrase still reads complete, those frames were redundant and there IS a duplicate.

10. **Do not trust a short isolated window to name a small word.**
    Why: a short window can read "for" when the audio is "from", because the last sound falls outside the window.
    How to check: check the word in a window that includes what FOLLOWS it.

11. **A fragment of a discarded take can hide in a tail pad.**
    Why: the transcriber returns the same text with or without it.
    How to check: read the envelope. A fragment RISES in level; a word tail decays.

12. **After cutting a repeat, re-seat the kept word.**
    Why: with one instance left in the text, the aligner can match the word to the discarded audio, and the caption loses the word while the audio still says it.
    How to check: fix the word's time in every word file the scripts read (the job's transcript and the master word list), then re-check its onset on the envelope.

## Working with the creator

13. **When the creator quotes the words to cut, cut THOSE words.**
    Why: substituting a different, visible repeat removes a line they wanted and leaves the real one.
    How to check: if the quoted words are not in the transcript, the transcriber is hiding them (rules 8 to 11). Say so and keep looking; never silently retarget.

14. **When the creator gives a timecode, go to that frame, and ask for one early.**
    Why: they heard it. Searching the transcript can miss it again. A re-cut changes the timeline length, so timecodes shift between rounds.
    How to check: confirm which timeline they are watching before mapping a timecode to a frame, then open that frame and listen.

## The master and rebuilds

15. **Transcribe and align the MASTER once; a re-cut is arithmetic.**
    Why: re-transcribing the cut audio after every re-cut makes the text churn, and since caption files are named by a hash of their text, every caption re-renders.
    How to check: keep one aligned master word list per video and remap it through each new cut list. Never delete the caption clip cache; unchanged cards must reuse their file.

16. **A fix that lives only in a placed timeline is lost on the next rebuild.**
    Why: remapping through a cut list made before the fix silently reverts it.
    How to check: write every positional fix as a RULE in the script that builds the layer (or into the master word list), rebuild, and confirm each fix is still there on the readback.

17. **Re-transcribe the edit to prove it.**
    Why: the only real proof the edit kept the right words is to hear it again.
    How to check: run `scripts/transcribe.py` on the edited audio and compare word for word against the plan.

## Limits

18. **Plan for the transcription rate limit.**
    Why: Groq's free tier caps whisper at 7200 seconds of audio per hour, so a long file stalls halfway.
    Numbers: `scripts/transcribe.py` sends 600 s chunks. A 55 minute master (3315 s) is six chunks. On a rate limit it reads the "try again in Nm Ns" hint and sleeps that long, up to 40 tries, so a long file walks through as the hour window rolls (about one chunk every 5 minutes when the window is full). The master and any re-check of the edit draw on the same hour.
    How to check: budget the hour before a long job. Local WhisperX (`transcription.engine: whisperx`) on CPU is not a faster fallback for a long file; it can take hours.
