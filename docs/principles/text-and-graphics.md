# Text and graphics principles

Text elements are the bigger words, stat cards, lists, strikes and title cards that pop on screen, separate from captions. They hit hardest when they say exactly what the creator says, exactly when they say it, and they look designed when they use one font, one color and no animation. Each rule below says what to do, why, the numbers, and how to check it.

Scripts: `scripts/align_words.py` gives word times, `scripts/snap_cuts.py` holds the onset measurement that text timing reuses, `scripts/render_caption_frames.py` is the authority for the shadow, `scripts/build_caption_clips.py` and `scripts/place_caption_clips.py` show the one clip per item pattern, and `scripts/verify_resolve.py` reads the timeline back. Font and colors come from `brand.*` in `config.yaml`, the shadow from the `captions.*` keys, frame rate and size from `video.*`.

## Words

1. **Text is word for word what the creator says.**
   Why: a paraphrase on screen fights the voice. The viewer reads one thing and hears another. Quiet rewrites slip in easily ("editors cost money" where the speaker said "they cost some money").
   How to check: every text element is a run of words found in the aligned transcript exactly, in order, with nothing dropped from the middle.

2. **Lists are the one exception.**
   Why: a spoken list can be summed up into short lines that read well.
   How to check: only list elements differ from the spoken words.

3. **If the line is too long, pick a shorter run of real words.**
   Why: dropping small words out of the middle turns it into a paraphrase.
   Numbers: measure what the space holds. A 286 px tall band on a 3840 wide frame holds about four words.
   How to check: the chosen run fits the space and is still contiguous.

## Timing

4. **Every state lands one frame before the measured start of its sound.**
   Why: the aligner marks a word 20 to 80 ms inside it, where the model is confident. Measured over 209 words the real start was a median 1 frame earlier than the aligner, up to 3.
   Numbers: start from the aligner's frame, walk back on the 300 to 6000 Hz energy envelope to where it crosses the burst peak minus 16 dB (the same measurement `scripts/snap_cuts.py` uses for cuts, so the two agree), then place the state at that onset minus 1 frame.
   How to check: overlay state frames on the waveform.

5. **Clamp the backward walk twice.**
   Why: connected speech has no silence between words, so an unclamped walk runs into the previous word. It once moved words 7 and 8 frames early.
   Numbers: never earlier than the previous word's onset plus 1 frame, and never more than 3 frames back (the measured aligner error).
   How to check: no state moved more than 3 frames from the aligner.

6. **Two states closer than 3 frames are one state.**
   Why: a one frame change is not something anyone can see. Two words said as one gesture should appear together.
   Numbers: under 3 frames apart means merge them into one step.
   How to check: no two consecutive states in an element are under 3 frames apart.

7. **A phrase builds one word at a time, each on its own word.**
   Why: a whole phrase that appears on its first word shows up to four words early, which reads as badly early even when the first word is on time.
   Numbers: each word is its own state at its own onset minus 1. Three things do not build: a stat or money card (the whole line appears on the frame the figure is said; "$1,200 a month" is one unit), a cumulative list (it builds by line, a whole line at once), and a phrase whose last word would leave under about 12 frames of hold before the picture ends (split it into two chunks instead).
   How to check: step through each element frame by frame against the audio.

8. **A strike comes after the phrase is done.**
   Why: striking mid build crosses out words not said yet.
   Numbers: the strike lands on the word after the phrase's last word.
   How to check: the strike frame is after the last word of the phrase.

## Look

9. **Text is white. There is no accent color.**
   Why: one color keeps the look clean. Accent colors were measured from reference graphics, the room's light, a linked product and a brand token, and every one was rejected. When a note about a visual property keeps coming back, ask whether the property should exist at all instead of sampling better.
   Numbers: text, strike bars, list markers and rules are all white (or the text color in `brand.primary_color`). A struck phrase is told apart by the bar plus the phrase dimming to 0.85 opacity, never by a hue.
   How to check: no colored pixels in any text element render.

10. **Text uses the same soft shadow as captions.**
    Why: one look across captions and text makes the video feel designed. A hard offset drop shadow next to soft captions is two looks on one frame.
    Numbers, as ratios of type size so they port to any size: shadow alpha 0.50, blur sigma 0.14 x size (a CSS blur radius is about 2 x sigma), offset 0.083 x size at 45 degrees, and the shadow dilated before blurring (8 px at 96 px type). CSS text-shadow has no spread, so emulate the dilation by stacking the same shadow twice; without that mass a fully blurred shadow fades to nothing on a bright background. No border and no hard offset shadow unless `captions.look` says otherwise.
    How to check: compare a text element frame next to a caption frame at the same zoom.

11. **One typeface, from your brand settings, never from a reference.**
    Why: re-deriving a font from someone else's video keeps getting it wrong.
    Numbers: `brand.font_family` and `brand.font_file` for every element in every format: captions, stat cards, lower thirds, pop up labels, overlays. Measure a reference only for geometry (position, cap height ratio, shadow, radius, timing). Move size between faces by cap height, not point size. Never swap in Bold because the regular weight looks light; fix the shadow or plate and say so.
    How to check: the font in every render matches `brand.*`.

## No animation

12. **Graphics hard cut on and off.**
    Why: measured frame by frame, reference videos have no animated text at all. Every graphic cuts on in one frame and off in one frame. Fades, slides and bounces are invented, not modelled, and slow the pace.
    Numbers: what replaces each banned move. A count up on a number becomes the whole line appearing on the frame the figure is said. A wipe, type on or slide becomes the words simply being there. A sweeping strike bar becomes frame N clean, frame N+1 struck, with the full bar and the dimming in the same frame. A rule drawing itself becomes absent then full width. A scale punch becomes nothing (87 to 100 percent of reference shots are scale static). A fade out becomes the element holding to the last frame of its clip, with the clip boundary as the cut off. No slow pushes or Ken Burns on graphics.
    How to check: hash every frame of the render (rule 16).

13. **A multi part element is a series of still states.**
    Why: a word by word build and a stacking list are fine because they are states. A wipe or count up is not.
    Numbers: a list stacks lines; it does not replace them. Reserve each hidden word's or line's layout box (hide with visibility, never by removing it from layout) so earlier words never move when a later one appears.
    How to check: the bounding box of earlier words does not change between states.

14. **Each text state is its own clip on the timeline.**
    Why: one flattened render per element means a word that feels early needs a code edit and a full re-render. Separate clips turn a re-time into a drag.
    Numbers: each clip is static (no tweens, no interpolation) and shows the cumulative state (word 1, then words 1 and 2, and so on, then struck). It runs from its own state frame to the next, the last holding to the element's end. Clips butt up with no gap, so the picture matches the flattened version. Assert that contiguity per element when building.
    How to check: `scripts/verify_resolve.py` shows one item per state with no gaps between an element's items.

15. **If you render states with tweens, make them exact.**
    Numbers: use only zero duration tweens, each placed half a frame before its target frame: time = (f - rec - 0.5) / fps, where rec is the clip's first frame. Frame f - 1 samples before it and frame f after, so no rounding can produce an in between frame. A state on the clip's very first frame goes in the static markup, not a tween at time 0.
    How to check: rule 16.

16. **Verify states by hashing frames, not by watching.**
    Why: one interpolated frame is invisible at speed and still wrong.
    Numbers: decode the render to RGBA (so the alpha plane is really decoded), hash each frame, and collapse identical neighbours into runs. N states must give exactly N runs (N + 1 when the clip opens on empty frames), and every run boundary must be a frame you scheduled. Report the alpha evidence in the same pass: corners 0, min 0 and max 255, and some partial alpha for real antialiased edges.
    How to check: the run count and boundaries match the schedule for every element.

17. **Cut each state from the render's own boundaries.**
    Why: working out a slice point from two numbers kept in different files drifts. Three of eight elements were once off by one frame, inside the right state only by luck. One frame the other way puts the previous state's words on screen while every readback agrees.
    Numbers: read each state's offset from the render's own manifest, assert the state counts match, and assert every offset falls inside the render.
    How to check: hash each placed clip's first frame and compare it with the render's frame at that state's offset. It is cheap and it is the only proof the right words are on screen.

## Title cards (text hooks)

18. **A text hook is one static card, same face and look as the captions.**
    Why: a hook is a title, not an animation.
    Numbers: render once to an RGBA image, wrap it in a short alpha video clip (a still cannot be given a length through the editor's API), and place it as one trimmable item on its own video track. Hard cut on and off. Same shadow as captions at the hook's size: at 70 px, distance and spread are 6. Render the clip at the larger of the hold or 6 seconds so the item has handles. A restyle gets a new clip name so an old cached clip is never reused.
    How to check: one item on the hook track, readable over the first frames.

19. **Hooks stay in the platform safe zone.**
    Why: on shortform the app's tabs, labels, handle and buttons cover the top and bottom.
    Numbers, on 1080 x 1920: the top chrome reaches about 250 to 270 px; the bottom 20 to 35 percent is also covered. A 70 px card centred at y 390 sits at 355 to 425, clear with margin. Refuse a centre above 300 or below 1400 rather than rendering into the chrome. On a split screen, the hook shares the caption centre.
    How to check: put a platform safe zone overlay on the hook frame.

20. **A hook holds through the opening sentence.**
    Why: it should be on screen while the first idea lands, then get out of the way.
    Numbers: starts on frame 0. Ends at the end of the opening sentence run: the first caption card ending in ? . or !, extended while the next sentence starts within 2 seconds (an opener is often a question plus its options). With no caption plan, hold 4.0 seconds.
    How to check: the hook's last frame matches the end of that run.

21. **If no hook line is given, write one from this video only.**
    Why: a hook must be true to the cut it sits on.
    Numbers: draft 5 to 8 candidates from the ideas the cut carries, push each for stakes and interest, apply the copy rules (plain words around grade 4, lower case except I, only a trailing question mark), and trace every claim in the winner to a moment in THIS cut. A fact from another video never goes on the card. List the rejected candidates.
    How to check: each claim word points to a timestamp in the cut.

## Privacy

22. **Hide private details in any screenshot or pop up.**
    Why: profile pop ups and screen grabs can show handles, names or account details the creator does not want shown. Treat any private handle this way by default.
    Numbers: crop first, since a crop removes the detail completely; blur (pixelate plus blur on that box only) when a crop would remove something wanted. Save a NEW asset and render under a NEW clip name, because the editor holds the old one linked.
    How to check: read every screen graphic at full size before it ships.

23. **Blur every file except the one being worked on in any file browser on screen.**
    Why: a file list, downloads folder or dock stack can show unrelated private files.
    Numbers: blur every row, pill and thumbnail except the working file, not just what looks sensitive. Per region, crop the master, Gaussian blur at sigma 28, lay it on a transparent full frame canvas, one patch clip per source range, placed against each picture item's source in point. Find these moments by looking at frames, not the transcript.
    How to check: step through every kept range that shows a file browser.

## Transition effects

24. **A transition effect sits on the sound and straddles the cut.**
    Why: an effect should fire when the line before it is done, and the next line should start when the effect is done.
    Numbers: for a 9 frame effect plate at 24 fps, put 5 frames on the outgoing clip and 4 on the incoming, so the two brightest frames land one each side of the cut, with the sound effect starting on the same frame. The outgoing clip ends where its last word's waveform ends. The incoming clip starts so the next line's waveform begins the frame the effect sound ends. Measure both edges on the 300 to 6000 Hz envelope at 36 dB below the local peak; the aligner alone can leave a word inside the effect. Do the same at every seam, including intro to body. If pulling the incoming head back would expose a cut word, refuse.
    How to check: line the effect's start against the end of the waveform before it, and the next line against the end of the effect sound.

25. **Use the same transition asset every time.**
    Why: a generated or stock substitute looks and sounds different and gets rejected.
    Numbers: keep one approved plate and its own matching sound in your assets and reuse them. If the original is lost, rebuild it from the same source, frame for frame, not from a new pick.
    How to check: the placed plate and sound are the approved files.

## Proof

26. **Look at it before calling it done.**
    Why: numbers can all pass while the graphic looks wrong.
    How to check: run `scripts/verify_resolve.py`, then screenshot each text element on the timeline, open the screenshot and look at it.
