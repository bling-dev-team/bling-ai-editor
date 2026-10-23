# Caption principles

Most people watch with the sound off, so captions carry the video. They also carry the pace. When people ask for "an edit every 1 to 2 seconds" they do not mean cuts: measured reference videos never beat about 29 picture edits per minute, and every one has a dead stretch longer than 6 seconds. The steady motion comes from the caption layer, at 36 to 39 cards per minute. If a video feels dead, fix the captions first. Do not add cuts or zooms.

Good captions land on the word, change often, never sit across a picture cut, and never leave a frame empty. Each rule below says what to do, why, the numbers, and how to check it.

Scripts: `scripts/transcribe.py` and `scripts/align_words.py` give word times, `scripts/captions.py` groups words into cards, `scripts/render_caption_frames.py` draws each card, `scripts/build_caption_clips.py` turns cards into clips, `scripts/place_caption_clips.py` puts them on the timeline, `scripts/build_caption_overlay.py` is the older single file path, and `scripts/verify_resolve.py` reads the timeline back.

Settings live in `config.yaml`: `captions.look` (shadow, border or pill), `captions.font_size`, `captions.words_per_card`, `captions.center_y` (0.0 top, 1.0 bottom), `captions.uppercase`, `captions.shadow_blur`, `captions.border_px`, `captions.pill_color`, the `brand.*` keys for font and colors, and `video.fps`, `video.width`, `video.height`, `video.format`. Set your own look in `config.yaml`. Never hardcode a look in a script.

## Timing

1. **A card starts on its own word, never after it. Round the start down, the end to nearest.**
   Why: a late caption feels out of sync. Rounding a start to nearest puts it one frame after its word on about half of all words (any word that begins in the upper half of a frame).
   Numbers: start frame = floor(start x fps). End frame = round(end x fps). Flooring can only move a card one frame earlier, never past its word.
   How to check: for every card, its first frame is at or before its first word's aligned start, and no more than about 2 frames early.

2. **Only the end of a card gets clamped.**
   Why: you may shorten a card to fit before a cut, but moving its start breaks sync. Snapping the first card of each segment back onto the cut once put cards up to 13 frames (0.54 s) early.
   Numbers: a good build measures worst card about 2 frames early, median 0, and 0 cards across a cut. The minimum card length padding obeys the same end limit.
   How to check: no card start was moved off its word to fill a cut or gap. A card's first word always sits inside its own segment, so starting on the word can never cross a cut.

3. **A caption never crosses a picture cut.**
   Why: the same words on both sides of a cut look like a glitch.
   Numbers: the cut list is the union of the voiceover cuts and the b-roll cuts. Both count.
   How to check: for every cut, no card starts before it and ends after it. Build the cut list from the timeline readback, not from a saved plan file, which goes stale the moment a b-roll slot moves. If a phrase spans two shots, it becomes two cards, or the two shots become one timeline item.

4. **A snap to a nearby cut reaches 3 frames at most and never reorders words.**
   Why: a longer reach pulls a word forward and makes the caption late, or orphans a word into its own card. A snap that lands at or past the next word's start swaps the word order on screen.
   Numbers: 3 frames maximum. A snap that would land at or past the next word is refused, not clamped. The word stays where it was spoken.
   How to check: card text reads in spoken order everywhere. Look for any word whose time moved more than 3 frames.

5. **Keep the cuts tight to the speech.**
   Why: when a cut sits about 20 ms before the first sound, "on the cut" and "on the word" are the same moment. Loose cut padding starts putting captions early again.
   How to check: spot check a few cuts against the waveform.

6. **No frame of the video is uncaptioned. Fill gaps from the left.**
   Why: an empty gap breaks the rhythm and looks like a mistake. Gaps between phrases are common (one film had 96 of them, 6.8 percent of the runtime).
   Numbers: hold the card already on screen until the next one starts. Never pull the next card back early; that is what puts captions half a second early.
   How to check: walk every frame and list any frame with neither a caption nor a text element on it. Report the longest such run, not just the card count.

7. **When a cut interrupts a hold, start a fresh card with the same words on the cut.**
   Why: nothing appears before it is spoken, and two cards either side of a cut is not a crossing. A held card reuses its parent's image, so there is no flicker.
   Numbers: measure the hold limit from the card's start, the only frame sure to be inside its own segment. Measuring from its end makes a crossing at every segment boundary. A card that already ends on a cut cannot stretch past it.
   How to check: no held card crosses a cut, and no cut is followed by an empty frame.

8. **Build captions from the edited audio, not the raw transcript.**
   Why: the edit removed words and moved time. Raw timing is wrong, and an edit that removed a stumble changes the text too.
   How to check: rebuild the cut's audio, run `scripts/transcribe.py` on it, then `scripts/align_words.py`, then build cards from that. Keep word spelling fixes in one list inside `scripts/captions.py`.

9. **Get word times from a word level transcriber, and check its bias.**
   Why: forced alignment marks a word where the model is confident, which sits inside the word. Measured on one voiceover, forced alignment ran a median 65 ms late (p75 113 ms, p95 213 ms) with no drift, and that bias reads as "captions feel off".
   Numbers: `transcription.engine` in `config.yaml` picks groq (word timestamps, a few seconds for a full video, send a compressed mp3) or whisperx (local, slower). Keep a small lead on card starts.
   How to check: compare a sample of word starts to the waveform. A constant late bias means add lead, not re-align.

## Cards and text

10. **Change the caption every 1 to 2 seconds.**
    Why: frequent change keeps the eye busy. This is where the "edit every 1 to 2 seconds" feeling comes from.
    Numbers: aim for 36 to 39 cards per minute. Flag any card over about 2.5 seconds.
    How to check: list card lengths and the cards per minute.

11. **Keep cards short: 2 or 3 words.**
    Why: short cards read in one glance.
    Numbers: `captions.words_per_card` (default 3). Split anything over 3 or 4 words.
    How to check: count words per card.

12. **Any cleanup pass after grouping must obey every break rule the grouper used.**
    Why: a tidy pass that merges a lone word back into the card before it can undo a comma or sentence break the grouper made on purpose. A cleanup pass can build a card just like the grouper, so it needs the same rules.
    How to check: after any merge step, no card spans a comma or sentence end that the grouper split on.

13. **Text rules: lower case, almost no punctuation, digits with commas.**
    Why: clean text reads faster.
    Numbers: lower case except "I" and its contractions (not words that merely start with i). No punctuation except a trailing question mark and the thousands comma inside a number: 4 digits or more get commas ($1,200, 10,000), inserted automatically. The one exception is a bare four digit year with no currency sign. Numbers show as digits, not words. `captions.uppercase: false` by default.
    How to check: scan cards for punctuation, spelled out numbers and missing commas.

## Look

14. **Shadow is the default look for every format. Border and pill are on request.**
    Why: a soft shadow keeps white text readable without looking heavy. The border is a louder look and should be a choice.
    Numbers (`captions.look: shadow`): shadow opacity 0.50, full blur (`captions.shadow_blur`), angle -45 degrees, distance and spread both round(0.083 x type size). That is 5 px at 59 px type, 6 px at 70 px, 8 px at 96 px. The spread is a dilation of the shadow before blurring, so it has mass.
    How to check: read `captions.look` from `config.yaml`. Lay one card over the brightest, busiest frame and the darkest frame under the caption area. If it is hard to read on a bright, low contrast background, raise the opacity. Lean darker, not lighter.

15. **The border look is a solid black stroke and nothing else.**
    Numbers (`captions.look: border`): `captions.border_px` 6 px at 1080 wide, solid black, no shadow, no blur. White text.
    How to check: zoom a rendered card. The stroke is even and 6 px at 1080 wide.

16. **The pill look is a rounded plate behind the same type.**
    Why: on split screens a plate reads over both halves. Only the plate is new; the font and size stay the same.
    Numbers (`captions.look: pill`), all as ratios of type size so they follow it: plate height 1.83 x size, side padding 0.46 x size, corner radius 0.41 x size, baseline 0.30 x size below the plate centre, fill grey 118 (`captions.pill_color`) at 0.50 opacity. A card that would wrap shrinks until it fits one line, with a minimum size, so only long cards change size.
    How to check: measure a rendered plate against those ratios. To read a plate color off a reference, sample a row inside the plate and the same row just outside it in the same frame, then solve alpha x G + (1 - alpha) x background = observed with alpha 0.50. Do not compare against the row above, because the background changes up and down.

17. **If a style value looks too strong once rendered, try it at a tenth.**
    Why: numbers copied from another app's units often land ten times too big. A huge blur can spread a shadow so wide it disappears.
    How to check: judge from a grid of real frames, and write down which values you divided and why.

18. **The font comes from your brand settings, never from a reference video.**
    Why: guessing a typeface off someone else's video gets it wrong, again and again.
    Numbers: `brand.font_family` and `brand.font_file` in `config.yaml`, one face for every on-screen element in every format. Use one weight. Never swap in Bold because Medium looks light; fix the shadow or plate instead and say so. You may measure a reference for geometry: position, cap height ratio, color, shadow, radius, timing. Never the face.
    How to check: the font in the render matches `brand.*`.

19. **Size moves between fonts by cap height, not point size.**
    Why: fonts differ in metrics, so a pixel size measured on another face gives the wrong optical size.
    How to check: compare cap height in pixels, not the size number.

20. **Size a longform caption from a measured reference, not by shrinking the shortform one.**
    Why: a longform caption takes a LARGER share of frame height than a shortform one. Height scaling the shortform size comes out too small.
    Numbers: a good longform caption is about 3.52 percent of frame height in ink, centred about 87 percent of the way down. On a 3840 x 2160 frame that is 96 px type centred at y 1891 (`captions.center_y` 0.875). A good shortform caption is 59 px on 1080 x 1920. Set `captions.font_size` per format.
    How to check: measure ink height over frame height on a rendered frame.

## Position

21. **Captions sit in the exact centre of the frame unless asked otherwise.**
    Numbers: horizontally centred, vertical centre at half the frame height (`captions.center_y: 0.5`, y 960 on 1080 x 1920). Do not carry a special position over from a previous video.
    How to check: read `captions.center_y` and a rendered frame.

22. **Never cover the face. Measure the face box, not a guess.**
    Why: covering the mouth or eyes hurts a talking head, and a face moves between shots.
    Numbers: below the chin, run a face detector on every kept range at 0.5 s steps, take the 90th percentile of the box bottom, and add about 60 px (25 px of air plus half the card height). Keep the centre above the bottom platform chrome (about the bottom 35 percent on shortform, y 1248 on 1920). On the forehead, measure per shot and set it from the highest forehead, not the average, because one average covers the eyes on some shots.
    How to check: screenshot a card on every shot, not just one.

23. **On a split screen, centre captions on the boundary between the two halves.**
    Why: the brightest edge in the pixels is often text inside the screen share, not the split. A caption centred there sits visibly high.
    Numbers: measure the split from your layout (the scene or canvas layout that made the recording). If you cannot, find it by color, not brightness: the camera half carries color and a screen share mostly does not, so the average of red minus green over a column steps at the boundary. That same centre applies to every card, including a text hook.
    How to check: the caption centre lands on the boundary within a couple of pixels.

24. **Captions are an overlay, not a reserved band.**
    Why: shifting the picture up to "make room" leaves a dead band and moves the subject off centre.
    Numbers: centre the composition on the true vertical centre (half the height). Content may run to the bottom edge. Only keep small critical text (a link, a legal line) out of the strip where captions sit.
    How to check: look at a frame with captions on. Judge legibility by eye; there is no keep out zone.

## Lists

25. **A spoken list stacks; nothing shifts.**
    Why: each new item should add below. Moving the block each time is hard to read.
    Numbers: mark list cards on purpose (an explicit marker, never guessed from a line break, because the first card of a list has one line and no break). The block is top anchored and left aligned, centred horizontally as a block. Place the anchor so the FINISHED list is vertically centred, and pin the left edge to the widest line so a later long line does not push the block sideways.
    How to check: compare the bounding boxes of each list image, not by eye. The left edge and top must not move.

26. **A list line lands on the first word of the line it shows.**
    Why: anchoring a line to the word before it (the word that introduces it) puts it on screen too early. The caption keeps that word.
    Numbers: pin each list state to a picture cut where you can, so an item appears exactly on the cut to its phrase.
    How to check: each line's first frame matches its first word's start.

27. **A list block gets its own vertical centre.**
    Why: a list centred on a raised caption line covers the eyes.
    Numbers: put it above the face or below the chin, never across the eyes, and below the top platform chrome (about 270 px on 1920). Default it to the caption centre. Measure the face box across the cut before picking the number.
    How to check: screenshot the finished list on every shot it covers.

28. **Every list line gets a minus bar, drawn as a shape.**
    Why: many fonts have no glyph for the minus emoji, and the emoji version is a dark grey bar that vanishes on dark footage.
    Numbers: on by default. A rounded bar 0.75 em wide and 0.18 em tall, 0.35 em gap before the text, in the caption color with the caption look. Centre it on the cap height midpoint of the line (measure the letter H), not on the full line box. The block re-centres with the bullet included.
    How to check: on the image, the bar's middle and the first capital letter's middle agree within 1 px.

## Two speakers

29. **If two people talk, the caption shows who is speaking.**
    Why: the viewer should know whose words they are reading.
    Numbers: one color per speaker, used as the plate fill on the pill look or the stroke on the border look. Colors come from `brand.*`. A card lies inside one speaker span, so its start decides its color. To sample a brand color from footage, mask for saturated pixels, keep the top few percent by saturation and average them; the most common value is the antialiased edge and comes out too dark.
    How to check: read the printed card list for the colors, not the build's exit status.

30. **Tell speakers apart by voice, not by reading the text.**
    Why: a line that reads like one speaker can be the other.
    Numbers: on the loud frames (70th percentile and up), compare the share of energy in 80 to 300 Hz and in 2 to 5 kHz. Two different voices separate cleanly (for example, a human voice at 0.08 to 0.29 low share and 0.13 to 0.18 high share against a synthetic voice at 0.04 and 0.41).
    How to check: plot both shares per segment and confirm two clusters.

31. **Apply speaker colors on every code path that makes a card.**
    Why: a color set on only one path once shipped every card in the default color while every check passed.
    How to check: build with and without hand overrides and confirm colors appear both times.

## Captions under text elements

32. **Do not print words a text element is about to show.**
    Why: if a graphic builds the same words one at a time, a caption that already shows them spoils the build. The text element wins.
    Numbers: trim the card's WORDS, not just its frames, and re-derive its text from the words that survive. A card that runs into an element keeps its leading words. When re-deriving, only the upper bound matters; testing the lower bound drops a card's first word whenever its start rounded up.
    How to check: read the words of every card next to every element. Every position check passes while this is broken, because only the text is wrong.

33. **Break a card at an element's out point, not at its in point.**
    Why: a card that starts under an element and runs past it was dropped whole, taking the words spoken after the element left with it, and leaving bare frames. The in point is not a break, so cards running into an element keep their natural grouping and are just cut short.
    Numbers: after the break, close any sliver of a few frames left at the out point.
    How to check: after ANY change to element ranges, re-measure caption coverage (longest run with neither caption nor element).

## Clips, cache and proof

34. **Each card is its own clip on its own track.**
    Why: separate clips can be timed, slipped and checked one by one. One flattened overlay can only be fixed by rebuilding the whole thing, and a mistimed card hides until playback.
    Numbers: use short video clips with real frames (for example qtrle with argb pixels for lossless alpha), not still images. A still imports as one frame and the editor gives it a default length that scripts cannot set. Tell `scripts/place_caption_clips.py` which track to use; do not trust its default.
    How to check: `scripts/verify_resolve.py` shows one item per card on the caption track.

35. **The cache key holds every visual setting.**
    Why: a clip's file name is a hash of its text. If size, shadow, color, position, font or any geometry is not in the folder key, old clips get reused after you change the look, and every check still says zero mismatches because plan and timeline agree and are both stale.
    Numbers: the clip folder key includes fps, look, font, size, center_y, width limit, list position, bullet and every style parameter. A per-card color goes in the file name. Any change to card geometry must change the key.
    How to check: change one setting and confirm every affected clip gets a new path.

36. **Never overwrite a card file the editor already has linked.**
    Why: the editor keeps old frames cached for some items and reads the new file for others, so the picture jitters (a bullet once moved 3 px between frames) or a render fails at the changed frame.
    How to check: a restyle produces new file names and the placer relinks. No delete and rewrite in place.

37. **Prove it on the real timeline, by name and by eye.**
    Why: the plan can be right while the timeline is wrong, and a count can match while the words are wrong. A hand override applied in only one entry point once printed the right cards while rendering and placing the old ones.
    How to check: run `scripts/verify_resolve.py` and read the item NAMES off the caption track, not just the counts. Then screenshot a few cards over different shots, open them and look.

## Optional: cinematic captions behind the subject

If you use a cinematic caption workflow (words composited behind the person using a matte), these rules hold on top of everything above.

38. **The verbatim rail carries most words; a word embedded behind the subject is a rare peak.**
    Why: embedding every word is the common mistake. It stops being an event.
    Numbers: each phrase is dropped (filler, stutters, self corrections), on the rail (verbatim, in front), or embedded (one big peak word behind the subject). At most one embed per sentence or beat, never two on screen at once, at least about 0.6 s between embed windows, one apex per section. Never grade, recolor or add texture to the footage itself.
    How to check: count embeds per section and look at the spacing.

39. **Cinematic caption timing and safety limits.**
    Numbers: every 0.3 s window keeps at least 30 percent of the face box uncovered. Each caption stays on screen at least 0.5 s. Word timings match the transcript within 80 ms; give each word its own entry, never two words sharing one start. A group's window starts at or before its first word and ends at or after its last. No two groups overlap in both time and screen area unless it is deliberate.
    How to check: run the workflow's timing and overlap checks, then preview frames before paying for a render.

40. **Read the scene before choosing a look.**
    Numbers: sample the caption area's brightness. Under 60, light text reads as is. 60 to 180, add a scrim behind the glyphs. Over 180, use opaque text plus a scrim, never bare light text. Refuse clips that already have burned in captions or heavy text (check a 1 frame per second contact sheet, not three spot frames), clips with no clear speech, clips under 3 seconds, and transcripts that do not read as language.
    How to check: look at the contact sheet and the brightness numbers before authoring.
