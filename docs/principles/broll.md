# B-roll principles

B-roll is the footage that plays over the talking head. Good b-roll shows what the words say, right when the words say it, and makes the creator look good. Bad b-roll is random, badly framed, awkward, mismatched in color, or leaks private info. Every rule below came from a real insert that got rejected. Each one is a bold rule, then why, then the numbers, then how to check.

Scripts that exist in this repo: `scripts/place_inserts.py` places inserts on a video track (`--track`, default 2), `scripts/audit_broll.py` runs the placement rules against the timeline readback (`--fps` defaults to `video.fps`, `--intro-slots` sets where the intro ends), `scripts/verify_resolve.py` reads the timeline back, `scripts/align_words.py` gives the aligned word times you cut on. Frame rate is `video.fps` and shortform or longform is `video.format` in `config.yaml`. The b-roll library is `paths.broll_dir`.

The big idea: **a number narrows the search, your eyes make the call.** Motion scores, framing scores and color stats all passed shots that a person rejected on sight. Use the numbers to make a shortlist and to catch outliers. Then look.

## A. Choosing the moment

1. **A clip is not a beat.**
   Why: one clip usually holds several usable moments plus dead stretches. A 28 second clip held two different lines' worth of footage. An 8 minute clip held 24 separate beats.
   Numbers: split on visual content change (a coarse per-frame color signature), not on motion alone. Cap a moment at about 8 seconds, since a moment longer than 8 seconds is almost always two beats. Drop dead footage like an empty hallway.
   How to check: your shot list has one row per moment, each under about 8 seconds, with no "nothing happening" rows.

2. **Label every moment by subject and action, never by camera move.**
   Why: "whip across the seat" is what put the wrong clip under the wrong line. "She browses the table with the plaid bag" is something you can match to words.
   How to check: read the shot list. Every label names who or what is in frame and what they are doing.

3. **Story order uses effective time: capture time plus the offset inside the clip.**
   Why: capture time is per clip. A moment 59.5 seconds into a clip stamped 12:31:19 really happened at 12:32:18. Sorting by file time alone puts "the door opens" before "he arrives at the door".
   How to check: every moment carries capture time plus in-clip offset, and you sort on that.

4. **Motion alone picks whip pans. Reject low-detail windows.**
   Why: taking the highest-motion window picked a blurred camera whip on 3 of 4 clips. A whip is high motion and low detail.
   Numbers: measure gradient energy (detail) per frame and reject any window whose lowest detail falls below 0.55 times that clip's own median. Relative, because a dim room and a bright beach have very different absolute detail.
   How to check: no shortlisted window contains a frame below 0.55 of its clip's median detail.

5. **Score framing as well as motion, shortlist, then pick by eye.**
   Why: maximizing motion lands mid-pan, with the subject sliding out of frame. Two scoring passes in a row picked badly (first whips, then off-framed pans).
   Numbers: score `detail` (mean gradient, an empty sky or blown window scores about 0), `centre` (energy-weighted centroid, full marks anywhere in the middle 64 % so rule-of-thirds still scores 1.0) and `edge` (share of energy in the outer 8 %, the sign of a subject being chopped). Shortlist the top 4 non-overlapping windows per slot and render one frame from each.
   How to check: you looked at all 4 frames before choosing. No pick was made by the score alone.

6. **Movement means the subject moves, not the camera.**
   Why: frame-difference motion cannot tell a moving subject from a moving camera. A golden-hour timelapse (the sun moved, the person did not), a drive-by from a car (scenery moves past a still subject) and an arms-in-the-air pose all scored well and were rejected.
   Numbers: a good replacement was the subject walking away from a locked camera, at 3.8 times the clip's own median motion.
   How to check: watch the window. The person or thing in frame does something. Keep the narrative beat too: a "working" line still gets a working shot, even if the subject walks off 40 frames later.

7. **A walk must go forward, and the window must end before the camera moves.**
   Why: a walk that starts backward reads as awkward, even when it passed motion, framing and relevance.
   Numbers: measure the subject's apparent size over the window. Shrinking while facing camera is a retreat, growing is an arrival. Use the arrival. Stop the window before a tilt or pan begins (slip it 3 frames early if needed).
   How to check: the subject grows or holds size through the window and the camera is still at the out point.

8. **Calm beats motion when the subject is the creator.**
   Why: in one six-insert review only two survived, and both were a still subject talking or looking with intent, on a locked camera at chest height, dark shirt, skyline or nice room behind. The rejects were walks with luggage, a walk through a lounge, a laptop on the lap in shorts, and a wide open-hand gesture.
   How to check: prefer a nearly still subject who is talking or looking with purpose. Before going to a new location, try other windows of clips that were already approved.

## B. What may appear on screen

9. **Never show people who did not agree to be in the video, including on screens.**
   Why: their face is their choice, and some people must never appear (for example someone in a dispute with the creator). A face inside a laptop, phone, monitor or call window counts exactly as much as a face in the room. One slipped through as a face on a video call shown on a laptop, and the file name mentioned no people.
   How to check: look at every face in every insert, including faces on screens. Keep a written never-use list. **Quarantine** failing clips by moving them to a separate never-use folder in the library, do not just skip them, so the next search cannot find them. After moving, search the library for the names and confirm 0 matches. Treat whole eras of footage where those people were around as suspect and check by frame, since file names miss them.

10. **Read every screen in a shot at full resolution before you use it.**
   Why: a top-scoring pick labelled "the finished video on the monitor" was really a live webinar console with a chat sidebar, a comment box and a fully readable bookmarks bar listing every tool the business uses. No banned face, sharp, well framed and moving, so every check passed it. Another clip was a phone full of payment notifications showing customer emails.
   How to check: any candidate with a monitor, laptop, phone, TV or call window gets its screen read at full size for faces, private business info (bookmark bars, tab titles, URLs, dashboards, revenue, client names) and live chat panels. A chat can put a name on screen at any frame, so one sampled frame is not proof. Reject the shot. Do not crop or blur around it. A shot is cleared by what is on it, never by its file name, label or score. Rename a leaking clip in the library so it is not picked again.

11. **No equipment in shot, and never the setup phase of a clip.**
   Why: the first seconds of most self-shot clips are the creator glancing at the lens, adjusting the tripod or walking into place. Two inserts shipped exactly that because the file names said "filming himself". A ring light visible in every frame is also a reject.
   How to check: window past the setup into the part where the person is performing. Reject any window where someone checks the camera or where gear (ring light, tripod, rig) is visible. The same clip is usually fine a few seconds later.

12. **A body part is not a shot, and a clipped head is a reject.**
   Why: feet on a recliner or hands with no context read as a mistake. A head cut off at the frame edge looks broken.
   Numbers: one carve-out is a point-of-view shot of hands doing what the line names (hands on a keyboard under "when I come back"). Detect clipped heads with a face box (frontal, profile and mirrored): touching the top, running off the bottom, or sitting in the bottom fifth of the frame means cut. Add a top-edge detail check with a high centroid to catch back-of-head and over-the-shoulder cases a face detector misses. The average `edge` score cannot catch this, since one clipped edge averages away against three clean ones.
   How to check: look at the rendered frame. A missed face is not evidence of a bad frame (a shot from behind, a hands shot), so use face detection only to reject, never to select.

13. **The creator must look good: aura, never awkward.**
   Why: this was given as a correction three separate times. Awkward footage hurts trust even when it is on topic.
   Numbers: aura means well dressed or a nice setting, cinematic light (skyline, golden hour, rooftop, studio, a nice interior), calm confident posture, natural movement (a walk, sitting down, laughing with friends). Reject posing for the lens, flailing arms, gym, tank top, shirtless or underwear looks (shorts and bare legs are fine, underwear is not), body-part shots, and anything that reads as "doing something weird". This bar applies to everyone in the frame, including a partner or family member when the story is about them.
   How to check: look at the frames for pose, expression and framing. A clip being on topic does not clear it.

## C. Matching the picture to the words

14. **Relevance and aura are both mandatory, checked by eye before anything else.**
   Why: an awkward literal shot and a pretty irrelevant one both fail.
   How to check: for each insert, play the line over it. Does it show what the sentence is about, and does the creator look good? Keep searching until a candidate clears both.

15. **Match the register of the line, not only the topic.**
   Why: an affectionate clip (a kiss, a cuddle) under a business line about a brand deal felt weird, even though it was aura-clean.
   How to check: affection footage goes under relationship lines only, never under business, event, work or money lines. Match what the sentence is about and its tone, then apply the aura bar.

16. **Add a picture the talking head does not already show.**
   Why: if the creator is already filmed in the apartment, an insert of the same apartment adds nothing.
   How to check: look at where the talking head is. If the frame already shows the place, object or person the line names, the insert comes out.

17. **On topic and well shot is the floor. Pick for scroll-stop value.**
   Why: two full library passes were called "random" because they stopped at on topic.
   How to check: after relevance and aura, rank the shortlist on whether a scroller would stop: skyline, sunset, travel, a striking place, a moment with energy, a reveal the line sets up. Take the highest. Use the creator's previously accepted inserts as the reference for what "good" means.

## D. Timing and placement

18. **The voiceover's own cuts are the spine, and key words force a cut.**
   Why: following the talking-head cuts gives good pacing without chasing a target, and a picture that changes on the syllable it shows (the kick on "kick", the crying on "cried") feels tight.
   Numbers: voiceover cuts land about 1.38 seconds apart on average, which matches a reference pace of about 1.5 seconds. Split any voiceover piece longer than about 2.2 to 2.3 seconds, since there is no audio cut inside it. Merge fragments under 8 frames instead of cutting there.
   How to check: map every word to its timeline position by walking the edited timeline's source ranges back through the aligned word list (`scripts/align_words.py`). Every voiceover cut starts a new insert, and each key word has an insert boundary on it.

19. **Insert boundaries sit on the talking-head cuts, within 4 frames.**
   Why: an insert edge that misses a cut by 1 to 3 frames grows slivers in the caption grid and splits cards.
   How to check: every insert start and end is within 4 frames of a V1 cut, then snapped onto it.

20. **A transition word means the picture is already at the next place.**
   Why: "then", "after that", "finally", "once we finished up", "but yeah" tell the viewer the story moved.
   How to check: the new scene starts on or before each transition word.

21. **The intro is a montage. After it, the story runs in order.**
   Why: the intro is the most interesting, emotional, scroll-stopping footage that still fits the words. That also frees the literal footage for the line that names it later.
   Numbers: the intro boundary cannot be guessed (auto-detection picks nonsense), so set it per job with `--intro-slots`. On one job it was 7 slots, ending at frame 274 = 11.417 seconds, the story start and the music drop.
   How to check: after the intro, source in points sorted by effective time go up down the timeline. Prefer motion, but content wins for the emotional payoff.

22. **Never reuse a source range, and a reused clip must run forward.**
   Why: the viewer notices the same seconds twice. Going back in time inside a clip feels wrong.
   How to check: `scripts/audit_broll.py` flags any overlapping source range (everywhere, intro included) and any in point that goes backward (after the intro only, since the intro breaks order on purpose).

23. **A slot under about 12 frames stays on a neighbour's clip.**
   Why: a hard cut to new footage under 0.5 seconds reads as a glitch. This reverses the naive "never repeat" instinct.
   How to check: any slot shorter than 12 frames uses a later, non-overlapping part of the clip next to it.

24. **Place b-roll silent and frame exact, with no black flashes.**
   Why: b-roll audio fights the voice. B-roll frame rates (59.94, 60, 29.97, 30) often differ from the timeline, and rounding leaves a one-frame black flash at every cut.
   Numbers: place video only. Round the converted source length up and add 1 safety frame. Compute record positions cumulatively in whole frames, never by adding up decimals. Better still, pre-render each insert at the timeline's own rate (`video.fps`) so source frames map 1:1 to timeline frames, which removes this whole class of bug.
   How to check: `scripts/verify_resolve.py` readback shows 0 gaps, head and tail offsets both 0.000 seconds, and no b-roll audio track in use.

25. **Render each insert with handles.**
   Why: a cut you can slip is a cut you can fix in a second.
   Numbers: render about 4 seconds per clip, roughly 1 second of handle on each side.
   How to check: every placed insert can be slipped about 1 second either way.

## E. Sourcing and cropping

26. **Footage does not have to be your own.**
   Why: some lines need a picture that was never filmed (a place that bans phones, for example).
   How to check: pull it from a public video site with a current build of a downloader (a stale build fails partway through a download and only offers low resolution). Re-encode at the timeline's frame rate. Keep sourced clips in their own folder in the job. No on-screen credit, unless the license or the creator says otherwise.

27. **Camera brand does not matter, the picture does. Horizontal may be cropped.**
   Why: after several reversals the final rule was that all cameras are the same tier. The shot is what counts.
   Numbers: for a vertical shortform, crop horizontal clips to 9:16 (centered or tracked on the subject) at the source's full resolution, for example a 16:9 1920x1080 source cropped `crop=608:1080:656:0` then scaled to 1080x1920 with lanczos and a light sharpen. Native vertical footage is screened first, then horizontal crops.
   How to check: the framing check runs on the cropped frame, not the original. Record which camera each insert came from in the plan (read it from the file's metadata tags), and the report says which folders were screened, so an empty slot is proven empty and not just unsearched.

28. **Keep a trimmed, ungraded copy of each insert before deleting the source.**
   Why: when disk was low, sources were deleted after rendering, so every regrade meant downloading nine 4K originals again.
   Numbers: save the slot window plus 60-frame handles, cropped, at native resolution and bit depth, ungraded (CRF 10, or ProRes HQ for 10-bit sources, about 50 to 150 MB each). Record it in the plan row.
   How to check: a regrade is a re-encode from that copy, seconds, never a fresh download.

## F. Grading and matching

29. **Grade every insert, every time, by what shot it. Measure, do not trust a tag.**
   Why: a clip tagged as standard color (bt709) shipped ungraded and was visibly flatter than the graded ones. A tag says how the file is flagged, not whether it was graded. A re-render with a shortened chain can also silently lose the grade on one clip.
   Numbers: the ungraded clip measured std 53.4 and saturation 0.023 against graded inserts at std 81.8 to 89.7 and saturation 0.131 to 0.182, with a squeezed range (p1 39, p99 212). Its saturation was even below raw log footage (0.038). Measure mean, std and saturation on a mid frame of every insert against the talking-head master and the accepted inserts. An insert with std under about 50 or saturation under about 0.10 is ungraded and gets re-rendered, never placed.
   How to check: a side-by-side image of the master plus every insert, rendered before placing, with the stats beside each.

30. **Size the grade to the source's own character, not to another insert's numbers.**
   Why: a flat clip graded to match log inserts was rejected as "way too much contrast and saturation". Log footage needs a full expansion. A standard clip of a white corridor is genuinely low contrast and needs only a lift.
   Numbers: raw std 53.4 / sat 0.023. Matched to the log clips (std 82.0, sat 0.119): rejected. Gentle lift (std 60.8, sat 0.053): shipped. Two inserts can rightly differ in contrast if their scenes do.
   How to check: stats are how you detect an outlier, never the target. Judge the graded result by eye next to the master.

31. **Do not solve a grade to a target number. Expansion first, look second.**
   Why: solving every insert's std to the master's by lifting gamma turned every black grey and the whole set read milky. Grading look-first produced "super saturated", then "too hazy".
   Numbers: what held was a measured black and white expansion plus `eq=saturation=1.28:contrast=1.06:gamma=0.98`, then a black-point check only: p1 luma 8 to 20, p99 235 to 250 (fix with curves or contrast when outside), saturation multiplier 1.0 to 1.1, letting std land naturally around 65 to 85. A creative look is at most a light tint on top (blend about 0.25) and comes off if it hazes the blacks.
   How to check: read p1 and p99 on each graded insert and compare to the creator's previously accepted inserts.

32. **A creative look at full strength reads oversaturated. Blend it over a neutral base.**
   Why: log inserts through a stylized look at 100 % were called "super saturated / contrast" next to the talking head.
   Numbers: convert to neutral first with the camera maker's own conversion, then blend the look on top at partial opacity (start at 0.45 and tune per source) until the insert's mid-frame std sits about 50 to 70 and saturation about 0.20 to 0.28, next to the master and never above it on both. A look meant for log input never goes on footage that was already converted. Test a look on a well-lit frame, not a backlit silhouette.
   How to check: the side-by-side image again. Judge a daytime look on the window or sky region (a cool, clean exterior is fine) and reject any look that shifts skin color.

33. **Phone HDR footage gets the phone maker's own tone map first, then the same grade.**
   Why: every hand-built HDR-to-SDR chain came out about 24 code values brighter than the maker's own conversion, and no grade fixes a lifted image. A skipped tone map reads as "no color grade" and fails silently (the encoder exits 0 and the file plays).
   Numbers: order for an HDR phone insert is tone map at native size, then crop and scale to the timeline, then the job's insert grade. Resize before tone mapping only where a shortform pipeline requires it.
   How to check: measure the insert against the master as in rule 29. Compare against a frame from the maker's conversion, not against how the file looks in a player on an HDR laptop screen.

34. **On 10-bit sources, convert to RGB before any level or LUT filter.**
   Why: `colorlevels` on 10-bit YUV writes pure black frames, and ffmpeg still exits 0 with a valid file.
   Numbers: on one 10-bit frame, no filter measured mean 121.5 / std 64.9. `colorlevels` alone measured mean 0.0 / std 0.1. `format=rgb24,colorlevels` measured mean 134.7 / std 83.1. Always put `format=rgb24` (or `gbrp`) before `colorlevels` or `lut3d`. `eq` works on YUV and is unaffected. A 1D LUT file needs `lut1d`, since `lut3d` rejects it.
   How to check: check a rendered frame's mean luma, never the exit code. A mean near 0 is a black insert.

## G. Process

35. **Look at every contact sheet yourself before placing.**
   Why: two picks per pass were wrong on the sheet (back of head, a distorted foreground hand, a whip pan, shirtless on a bed) and every metric had passed them. Four of six pulls in one pass were mislabelled in the library. A helper's "verified" is a claim.
   How to check: you opened the contact sheet for every insert. The sheet decides, never the title.

36. **Brief from the last job's record, not from the rules alone.**
   Why: a correction recorded only in one job's notes recurred on the next job.
   How to check: before the first pick, read the previous job's accepted and rejected clip lists and plan, write them into a checklist, and write any new correction into these principles the same turn.

37. **Run the scripted checks against the plan and the readback.**
   Why: a plan and a timeline agreeing with each other is not proof. Both can be wrong together.
   How to check: run `scripts/audit_broll.py` on the timeline readback (not just the plan), then `scripts/verify_resolve.py`. Every placement rule in section D is a scripted check.
