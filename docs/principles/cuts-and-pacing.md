# Cuts and pacing principles

Cuts decide how a video feels. Too loose and people scroll. Too tight and words get chopped. These rules say where to cut, how tight to go, and how to prove nothing was lost. Most of the numbers were measured on the waveform and on the creator's own finished edits, not picked by feel. Each rule is a bold rule, then why, then the numbers, then how to check.

Scripts that exist in this repo: `scripts/transcribe.py` and `scripts/align_words.py` give aligned word times, `scripts/plan_cuts.py` plans the edit, `scripts/tighten.py` closes word gaps, `scripts/carve_silence.py` rebuilds kept ranges from the waveform, `scripts/snap_cuts.py` moves edges onto the measured sound, `scripts/build_timeline_lua.py` builds the timeline, `scripts/verify_resolve.py` reads it back. Frame rate is `video.fps`, shortform or longform is `video.format`, and caption timing settings live under `captions.*` in `config.yaml`. At 30 fps one frame is about 33 ms; at 60 fps about 17 ms.

The big idea: **measure, do not guess.** Word timings from a transcript are guesses. Sound levels are measurable. Every time a guess was replaced by a measurement, the cut got better.

## A. Where the energy comes from

1. **"An edit every 1 to 2 seconds" means captions, not picture cuts.**
   Why: four strong reference videos were counted frame by frame over their first 90 seconds. None changed the picture every 1 to 2 seconds, and every one went past 6 seconds somewhere. An edit already at the top of that range still felt dead. Adding cuts was the wrong fix, and so was adding reframes: the most reframe-heavy reference (39 % of its events) had the worst dead stretch.
   Numbers: references ran 18.7 to 29.3 visible picture edits per minute, with longest gaps of 6.2 to 8.6 seconds. The best one ran captions throughout at 36 to 39 cards per minute, on screen about 55 % of the time, 1 to 3 words, small, plain, lowercase, no plate. In one 20 second window captions lifted the visible event rate from 21 to 60 per minute and cut the longest gap from 4.80 to 2.75 seconds. Graphics are a second layer: about 4.7 per minute, median time on screen 1.8 seconds, never more than 2 on screen at once.
   How to check: count caption changes and picture cuts separately. If the video feels dead, fix the caption layer (`captions.words_per_card`), do not add cuts or zooms. Longform gets the same caption system as shortform, re-sized for its frame.

2. **Match pacing to the creator's own past edits, not to a feeling.**
   Why: "tight" means different things to different people. Their best shipped videos are the target.
   Numbers: three finished shortform cuts measured median clip 1.04 to 1.13 seconds, p10 0.375 to 0.670 seconds, shortest 0.167 to 0.600 seconds, 6.9 to 7.2 cuts per 10 seconds. So a tight shortform lands around median 1.1 seconds, p10 0.4 seconds, shortest 0.2 seconds, about 7 cuts per 10 seconds. A build at 7.7 cuts per 10 seconds was fine. A pass that applied the hard tail bar to every burst came out at 12.1 cuts per 10 seconds, visibly denser than anything shipped. 12 per 10 seconds is the shred line.
   How to check: read the clip durations off 2 or 3 past timelines the creator likes and compute median, p10, minimum and cuts per 10 seconds. Compare your edit's numbers before you show it.

3. **Longform on a screen share is paced by jump cuts, and the shortform ceiling still applies.**
   Why: on a static screen share most joins are invisible audio joins, not picture cuts.
   Numbers: one longform carve went from 667 planned ranges to 1320 (8.8 cuts per 10 seconds, 127 slivers under 0.25 seconds). Merging each sliver into its neighbour across the smaller gap (when that gap is under 0.5 seconds) left 1208 pieces at 8.0 cuts per 10 seconds, median 0.92 seconds. The only guard that applies is the 12 per 10 seconds ceiling. A longform figure of 11 to 15 cuts per minute is a shot rate and does not compare.
   How to check: count jump cuts per 10 seconds of body and compare to a past longform the creator liked.

## B. Cutting from the sound

4. **Shortform is cut from the waveform, not from word gaps.**
   Why: the aligner marks a word as over where it loses confidence, 20 to 80 ms inside the word, so the 100 to 200 ms of audible decay after it never counts as a gap. An aligner-only pass (gap 0.15, floor 0.12, 40 / 60 ms pads) left 14 silent runs totalling 3.01 seconds inside a 26 second cut and reported itself clean.
   How to check: run `scripts/carve_silence.py` on the enhanced audio. It reads the 300 to 6000 Hz voice band in 5 ms steps. `scripts/tighten.py` (gap 0.15, floor 0.06 by default) is a word-level first pass, not enough on its own for shortform.

5. **Use different bars for the start of a phrase, the middle and the end.**
   Why: the hardest trim belongs at the end of a phrase, not at every small burst inside one. Applying the hard bar everywhere shredded the delivery and was reverted.
   Numbers (the `carve_silence.py` defaults):
   - Onset bar: -42 dB (`--on`), so a consonant onset is never clipped.
   - Phrase start: max(that burst's own peak minus 16 dB, -42 dB) (`--on-rel 16`), then a 20 ms lead pad (`--lead 0.020`). A flat -42 dB bar fired on quiet ramp-ins and breaths and left 101 to 127 ms of near silence at the head of five pieces. Minus 20 dB relative measurably hurt the check transcript. Below about 15 ms of lead, a splice starts eating short words like "if" and "the".
   - Mid-phrase tail: -36 dB (`--off`) plus 10 ms (`--tail 0.010`). Inside a phrase, just close the silence.
   - Phrase, sentence or question end: max(that burst's peak minus 12 dB, -36 dB) (`--off-rel 12`), 0 ms pad, so the cut lands inside the decay.
   - Merge pieces closer than 60 ms (`--merge 0.060`); a picture cut there buys nothing. Drop pieces under 60 ms.
   How to check: on a test cut these bars took a 25.68 second edit to 22.88 seconds and left one 80 ms run below -42 dB in the whole film (longest run below -36 dB: 105 ms).

6. **The end-of-phrase bar is relative to that phrase's own peak.**
   Why: the speaker trails off, so a phrase end is quiet in absolute terms. A flat -30 dB bar ate the last word of a soft line outright.
   Numbers: 12 dB below the phrase's own peak, never gentler than the -36 dB mid bar. 10 dB is measurably too far: it turned "captions" into "caps".
   How to check: listen to the last word of the quietest phrases.

7. **Decide merges on the untrimmed gaps.**
   Why: trimming first pulls previously merged bursts apart and adds picture cuts.
   How to check: group bursts on their raw positions, then apply the trimmed edges only to the outside of each group.

8. **Snap every edge onto the measured sound.**
   Why: a cut a frame or two early clips the first sound of a word, and the aligner's word edges sit inside the word.
   Numbers: `scripts/snap_cuts.py` walks from the planned edge to where sound rises above the local floor (6 dB margin by default), reaching at most 0.30 seconds, and keeps 35 ms before the onset and 55 ms after the offset by default.
   How to check: play 1 second each side of every cut. Every word is whole.

9. **Merge away slivers.**
   Why: a cut that saves 60 ms but leaves a fragment under about 0.25 seconds reads as a glitch, not an edit. A one-frame sliver can also collapse into its neighbour and silently undo a cut.
   How to check: list every kept piece and merge any piece under about 0.25 seconds into its neighbour.

10. **Remove splice clicks after the carve, before the plan.**
   Why: the relative bars fire inside soft-onset words and inside decays, so both sides of a butt splice sit mid-waveform, and the editor adds no crossfade. You hear it as a zipper or a pop.
   Numbers: on one edit 22 of 39 splices had a sample jump over 0.05 of full scale at the join (max 0.68). The fix walks each in point earlier and each out point later, in whole frames, to the first frame whose peak is under about 2 times the noise-floor frame peak (floor p95 0.021, so bars of 0.04 in and 0.06 out), with budgets of 12 frames in and 6 frames out, never crossing into a neighbouring kept range. Result: 22 to 8 joins over 0.05 (max 0.25), 167 frames (2.78 s) kept. A very short fade of a few ms at any join that still jumps is the fallback.
   How to check: count joins with a sample jump over 0.05 before and after. If the noise is continuous instead of per cut, also try decoding the master audio to PCM in a new file and rebuilding against it, since compressed audio decode is a known crackle source. Treat both as suspects until a replay settles it.

11. **Cut between phrases only where the creator talks. A second voice is one block.**
   Why: a computer voice or a screen recording's comma pauses are how it reads a list, and they hold the screen picture together. Cutting 16 internal gaps out of two such blocks saved 3.4 seconds and left a jump cut every 1.5 seconds.
   How to check: tag every kept range with a speaker. Tighten the creator's own pauses as hard as ever. For a second voice, tighten only the head and tail of its block.

12. **Tell two live voices apart from the picture, not the pitch.**
   Why: over car noise a pitch estimate read 90 to 140 Hz for both speakers and could not separate them. One contact sheet (whose mouth is open, who the other person is looking at) settled every line in a minute.
   How to check: build the contact sheet first. Do not spend a pass on pitch.

13. **A shot can keep its head if it has a reason.**
   Why: when the picture is a screen recording of another edit, trimming the head moves that edit's own cut closer to ours and looks off. A pause or look before a line can also be the moment.
   How to check: revert that one piece by hand and keep the rest. Write it into the plan so the next rebuild keeps it.

## C. The edge pads are frozen

14. **The pads are frozen. Do not let them swing from video to video.**
   Why: the pads kept swinging like a rubber band: tails cut too much, then not enough. Measured on 1786 edges of two hand edits, the creator's accepted band was the same on both jobs. The swing was ours: each time a handful of outlier edges was turned into a global pad.
   Numbers: carve onset max(peak minus 16, -42) plus 20 ms, phrase end max(peak minus 12, -36) plus 0, mid tail -36 plus 10 ms. The final edge reseat keeps a 25 ms lead, a 40 ms tail and 0 extra on sentence ends. That lands heads about 0.2 frames before the onset, sentence ends about 2.6 frames after the -12 dB decay, mid tails about 0.4 frames after. The accepted band is heads about 0 to 1 frame before the onset, sentence ends about 1 to 4 frames after the decay end, mid tails about 0 to 2 frames after. Every bulk rule that moved edges matched the creator worse: per-type snapping gave 64 to 70 % of edges within 1 frame of the creator, a clamp-to-band rule 73 to 75 %, against 88 to 97 % for the frozen defaults.
   How to check: a global pad changes only when at least 60 % of one edge type, over at least 30 edges, moved the same way in one hand edit. Otherwise fix the few edges and log them.

15. **Sentence ends get 0 extra tail.**
   Why: one study added 4 frames to sentence ends because 3 had been extended. That pushed the whole class to a median of about 5.8 frames, and in the next hand edit 78 of 127 sentence-final tails were cut back to a median of 0.3 frames (trim median 4 frames, p25 3, p75 5), against only 16 of 428 other tails. That was the biggest single pattern: 95 runs, 16.6 seconds.
   How to check: end a sentence-final range on the word's measured decay (the -12 dB relative end bar) with no added pad.

16. **Clip guard: extend a sentence end whose decay runs past the cut.**
   Why: words said longer than they are written (acronyms and abbreviations like "AI." and "etc.") get ended early by the aligner. The 4 sentence ends the creator extended in one edit were all of this kind, clipped by 5.7 to 7.2 frames.
   Numbers: if a sentence or question end's measured decay runs more than 4.5 frames past the cut, extend the out point to the decay end. On the test job this moved 4 edges, all 4 closer to the creator, 0 farther.
   How to check: measure decay end against the out point on every sentence and question end of every cut. The threshold was fitted in sample, so the next hand edit is the test.

17. **Heads sit on the onset. A long head is a pacing beat, not a pad.**
   Why: the creator's in points sit on the measured onset (median about 0 frames). A head extended by 9 to 12 frames is a breath or beat before a line, a picture pacing call, not onset precision. Reading those as "start soft onsets 2 to 3 frames early" would have started the same swing on heads, and was retracted.
   How to check: keep heads at the onset. Treat any 9 to 12 frame head extension as a deliberate beat for that one line.

## D. What to cut: study the creator's own hand edits

When the creator hand-edits a cut, study what changed and why before anything else touches the timeline, then turn each pattern into a rule here. Measure what changed as source-frame coverage (built set minus their set), not from a clip list diff: a 1 to 4 frame head trim shows in a list as a removed clip plus a new in point, which looks like a deletion when it was only a split.

18. **They do not re-trim, they delete. Spend effort on which sentences exist.**
   Why: on one longform the creator cut a 26:54.9 AI cut to 17:00.1 by deleting 536 of 1208 pieces (44 %), 710.7 seconds, and the pacing medians did not move: head pad 0.85 vs 0.87 frames, tail pad 1.06 vs 1.07 frames, mean piece 31.0 frames in both, 8.0 vs 7.74 cuts per 10 seconds.
   How to check: when a cut reads too long, re-read the cut list for whole clauses and whole sections that can go. Do not re-tune the tighten thresholds.

19. **Strip the head word: start on the first content word.**
   Why: a leading discourse marker or function-word run after a cut is dead air to the ear.
   Numbers: one edit had 60 head strips, median 3 frames, 47 of 60 under 12 frames. A leading "Okay," cost exactly 7 frames (292 ms at 24 fps), identical in three separate cases. Most dropped first words: okay 7, and 6, for 4, but 3, again 3, so 2, that 2. Others seen: "now", "right?", "then", "because", "if", "to", "we've", "the one thing" (13 and 32 frame trims). "So" right after "Okay," is kept, 3 of 3. In another edit about 22 head strips saved 6.5 seconds.
   How to check: when a kept range opens with a marker or conjunction, at a sentence start or after a removed span, and at least two more words follow and the sentence still reads, reseat the in point to the next word's measured onset. An automatic strip pass fired 77 times where the creator stripped about 22, so review the list and keep only strips where the marker carries nothing.

20. **Cut at three scales: section, then paragraph, then clause.**
   Why: the creator's removal runs were clause scale (median 1.52 seconds, 76 of 94 under 4 seconds) and section scale (one run was 64 % of everything removed). The AI's proposals were paragraphs only: 57 candidates, median 7.5 seconds, maximum 39.9 seconds, and none for head strips, bridge clauses ("so once we have all of that"), self-corrections or list padding ("all the ums, all the ahs, all the you knows").
   How to check: every sculpt proposal has a section pass, a paragraph pass and a clause pass.

21. **The biggest cut in a demo is a whole repeated section.**
   Why: the creator deleted one run of 457.5 seconds (7:37, 335 pieces), every round of a feedback loop after the first, joining straight to the finished result. A proposal to compress those rounds into a 45 second montage was not taken: they were removed. The AI's largest proposal was 39.9 seconds; theirs was 11 times that.
   How to check: when a demo repeats the same loop (round 2, round 3, round 4), propose deleting every round after the first as one candidate.

22. **A "keep" on a joke means nothing until its section survives.**
   Why: of 13 jokes marked keep, 4 vanished with the deleted section, and one keep was justified by a restructure that had only been proposed. Every joke that was also a demo of the product survived. Every joke that was only about the process died with the process.
   How to check: run the structural pass before the joke pass. Favor jokes that also show the thing.

23. **The ranked sculpt list.**
   Why: the creator acted on 36 of the AI's 57 proposed cuts (63 %), 25 in full and 11 in part, and removed 710.7 seconds against 612.4 proposed, so their knife ran 16 % heavier.
   Numbers: the 25 full cuts by volume: replay of a demo already seen (8), redundant restatement (6), dictation (3), rambling (3), narrating the screen (2), apologizing for the product (2), bookkeeping (1), broken promise (1).
   How to check: run every longform cut through these eight categories, in that order.

24. **Process and waiting chatter dies whole, every take.**
   Why: lines that narrate logging in, installing, waiting or "I'll be back once it's done ... we're back" were cut every time: 15 runs, 16.9 seconds in one edit, plus 1.4 seconds of dead air after one. The retake dedup had kept the last of three "I'll be back" takes.
   How to check: delete every take of a waiting or bookkeeping line. Do not dedup it to the last take.

25. **Cut screen browsing and abandoned plans to the first line that does the thing.**
   Why: clicking around while commenting ("if I just click on any of them, boom, this one has been running since...") and a stated plan dropped in the next breath were cut: 10 runs, 10.7 seconds.
   How to check: find narration of clicking or a plan that is not followed, and start on the first line that acts.

26. **Cut leading fillers, retakes inside a sentence, restatements and false starts.**
   Why: on a live demo the filler is "okay so", not only "um". A self-correction inside a sentence ("at like 10 a.m. or at 10 in the morning") is a retake: keep the last form only. Redundant trailing clauses, false starts ("Then what"), restatements and doubled phrases ("it's super simple, it's super simple") go: 5 runs, 5.1 seconds in one edit.
   How to check: look for a phrase that takes too long for its words, a phrase said twice in a row, or a correction mid-sentence. Pieces that only had their pauses closed are not deletions, so check the words before calling them cut.

27. **A second number that restates a point goes, hedge and all.**
   Why: "every weekend with like 450,000 followers" was cut because a bigger figure two lines earlier had already landed the scale, and this one was a hedge plus a repeat (61 plus 96 frames).
   How to check: when a clause carries a hedge ("with like", "kind of", "I guess") and a figure that an earlier sentence already made the point with, cut the clause. Keep only the figure that is the hook.

28. **The kept take must be a complete sentence.**
   Why: the creator added back 286 frames of words in one edit, all to finish sentences. A take choice kept a subject without its predicate; the predicate only existed in the next attempt, so the whole later attempt came back, including a self-aware aside that owned the stumble ("well, I explained that terribly"), which is personality, not filler. A name the next line referred to was restored (46 frames) even though its screen was frozen. A dedup that kept a sentence with no subject got its subject back.
   How to check: when a dedup or take choice leaves a sentence without its verb, its object or a name the next line needs, splice the missing piece from the attempt that has it. A frozen static screen is not a reason to lose the words.

29. **A clause cut off at a function word gets its end back.**
   Why: of 37 duration increases in one edit, 9 restored a clause the carve had amputated, by up to 64 frames (7 to 71) and 54 frames. The median increase of 3 frames is ordinary sentence decay.
   How to check: when a kept piece ends on a function word or a preposition, treat it as cut mid-clause and extend to the end of the clause.

30. **Keep a pause before the reveal noun.**
   Why: the creator closed 15 mid-phrase pauses (3.8 seconds) and opened 5 (1.2 seconds). All 5 sat right before the noun the line builds to ("there's something called an ... X", "all you really need is a ... Y").
   Numbers: keep 4 to 9 frames of pause before the reveal noun.
   How to check: find "something called a ___" and "all you need is a ___" lines and leave the pause.

31. **Keep a silent beat where the screen is doing something.**
   Why: a 1.9 second silent stretch where the tool was visibly working was kept.
   How to check: act on every "screen action, consider keeping a beat" flag, do not just list it.

32. **A big transition is section punctuation, and it sets the cut to the frame.**
   Why: the carve placed 7 full-frame transitions on departures; the creator shipped 1 in 17 minutes plus the intro. The survivor was a departure that was also a joke and a change of subject.
   Numbers: the outgoing clip is trimmed so its last audible speech (300 to 6000 Hz at -36 dB of local peak) ends on the cut frame C (0 frames of trailing silence on 5 of 6, 1 on the sixth). The incoming clip's first speech starts at C+4 (measured 3 or 4, median 4), the frame a 9-frame whoosh ends.
   How to check: give a departure a big transition only if the viewer returns to a different subject. Carve both clips to end on C and start at C+4 before the graphic goes down. A departure that returns to the same task gets a hard cut, or its round gets deleted (rule 21).

## E. Proving the cut

33. **Prove the words did not change.**
   Why: tight cutting can drop a syllable without anyone noticing. In one test, a too-aggressive bar turned "Bro," into "bro." and "$1,200" into "1200" in the check transcript.
   How to check: run `scripts/transcribe.py` on the rebuilt edit. The words must be identical to the plan. If one word looks lost at a hard splice, transcribe that range on its own before believing it, since recognition can flake at a splice. Any word that falls in a newly cut slice also drops out of the captions, so count dropped caption words: any beyond the pieces you meant to remove are mis-seated words in the word list, and get fixed there.

34. **An impossible word span is a hidden retake.**
   Why: a whole-file transcript collapsed a retake into one line, and the aligner squeezed "460,000 followers before I got banned" into 1.0 second, a six-syllable number in 140 ms. The silence map disagreed both ways: a 1.2 second pause where the transcript had none, and 2.9 seconds of speech where it had one word.
   How to check: when an aligned word is too short for its syllables, or the silence map shows a pause the transcript lacks, transcribe that region in non-overlapping slices cut from the envelope, fix the text, and re-align the whole master. Spell numbers out as words before aligning and collapse them back after. Speech recognition also merges words repeated back to back, so the same slicing finds a missing repeated word.

35. **When the creator names the words to cut, cut those words.**
   Why: they know what they said. Do not swap in your own idea of the cut.
   How to check: find the quoted words in the aligned transcript and confirm they are gone, and only they are gone.

36. **Re-cutting settles, so repeat until nothing moves.**
   Why: each trim changes the audio a little, which shifts the next measurement.
   How to check: run plan, carve and snap again. Stop when the cut list stops changing.

37. **Rebuild from the plan, then read it back.**
   Why: a fix that only lives on the placed timeline is lost on the next rebuild. A plan and a timeline agreeing is not proof; both can be wrong together. A track even one frame longer than the picture renders a black frame.
   How to check: write every fix into the script or plan that builds the layer, then rebuild with `scripts/build_timeline_lua.py` and run `scripts/verify_resolve.py`: no gaps, no overlaps, no item shorter than 0.25 seconds you did not intend, nothing longer than the picture, every cut where the plan says, at `video.fps`. Match items between duplicated timelines by start and length, never by id.

## F. The talking head itself

38. **One grade for the talking head and the inserts, measured not trusted.**
   Why: a warmer, more saturated talking-head grade was built to match how a desktop player showed the raw file, and it was rejected as worse. The editor's built-in HDR color management looked worse still. What was accepted was the same recipe the inserts got.
   Numbers: the accepted head grade was the plain tone map plus `format=rgb24,eq=contrast=1.06:saturation=1.12:gamma=1.02`, then the job's look blended at 0.15. Hand-built HDR-to-SDR chains measured about 24 to 26 code values brighter than the camera maker's own conversion at every timestamp, with saturation within 0.005 of it: a lift problem, not a color problem. Adding saturation, contrast and warmth pushed on axes that were already right.
   How to check: tone map phone HDR with the maker's own converter before it enters the pipeline, then grade the SDR file. Compare frames against a frame from that converter, never against a player on an HDR laptop screen, which shows highlights an SDR file cannot hold. Compare a frame from each take side by side.

39. **Swap the master picture without moving a cut.**
   Why: a regrade must not shift the audio or the cuts.
   Numbers: conform the new picture to hard constant frame rate at `video.fps`. The frame count must match the old master exactly (one rebuild hit 5449 of 5449), and a ±2 frame difference sweep must bottom out at offset 0.
   How to check: rebuild the master video only, copy the audio stream from the old master, then replace the clip's media in place so every timeline item follows.

40. **Join two raw clips per clip, then join the audio separately.**
   Why: joining before conversion breaks timing.
   Numbers: tone map each clip with the same settings and no audio, join the outputs with a stream copy, and build the audio once from both raw audio streams. Check the frame count equals the sum (for example 7376 + 880 = 8256). Clip 2's picture starts on a whole frame while its audio starts where clip 1's audio ended, so it sits 6.7 ms (0.4 frame at 60 fps) behind its sound. Under half a frame is invisible. With more than two clips, re-anchor the audio per clip so the drift does not add up.
   How to check: record each clip's start offset in the job and confirm the frame count.

## G. Graphic card pacing

41. **Size graphic card pacing by duration, then by density.**
   Why: a fixed card count is wrong for both a 30 second reel and an hour podcast.
   Numbers: base seconds per card: under 60 s, 6 to 8; 60 s to 3 min, 8 to 12; 3 to 10 min, 12 to 20; 10 to 30 min, 20 to 35; over 30 min, 30 to 60. Multiply by 0.7 for high density (many numbers, a new idea every 1 to 2 sentences), 1.0 for mixed, 1.5 for one slow story. Card count = max(5, round(duration / seconds per card)), no upper clamp. "Fewer" is about 0.6 times that, "more" about 1.5 times. A static one-liner gets boring past 8 seconds; a card held past about 15 seconds needs a richer multi-step reveal.
   How to check: compute the count before designing cards and clamp every card end to the real media duration, or the render shows a black tail.

## H. How to work

42. **Let it decide, then correct it, and stop after two failures.**
   Why: correcting a built cut takes a minute; waiting for approval on a cut list takes a day. But an approach that failed twice will fail a third time.
   How to check: build the cut, show it, take the correction. If the same approach fails twice, stop and re-plan instead of retrying.

43. **Write every correction down the turn you get it.**
   Why: a correction that lives only in one job's notes is repeated on the next job.
   How to check: each correction becomes a rule in these principles or in the script that builds the layer, the same turn.
