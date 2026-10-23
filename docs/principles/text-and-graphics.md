# Text and graphics principles

Text elements are the bigger words and graphics that pop on screen, separate from captions. They hit hardest when they say exactly what the creator says, exactly when they say it. These rules keep them clean, on time and on brand.

Scripts: `scripts/align_words.py` gives word times, `scripts/snap_cuts.py` holds the same onset measurement used for text, `scripts/build_caption_overlay.py` renders text clips, `scripts/verify_resolve.py` reads the timeline back. Colors and fonts come from `brand.*` in `config.yaml`, frame rate from `video.fps`.

## Rules

1. **Text is word for word what the creator says.**
   Why: a paraphrase on screen fights the voice. The viewer reads one thing and hears another.
   How to check: every text element is a run of words that appears in the aligned transcript exactly, in order, with nothing dropped from the middle.

2. **Lists are the one exception.**
   Why: a spoken list can be summed up into short lines that read well.
   How to check: only list elements are allowed to differ from the spoken words.

3. **If the line is too long, pick a shorter run.**
   Why: dropping small words out of the middle makes it a paraphrase.
   How to check: choose a shorter run of the real words that fits the space.

4. **Time text to the waveform, not to the transcript guess.**
   Why: the transcriber's word times can be off by a frame or more. Text that pops late looks sloppy.
   How to check: each word lands one frame before the measured start of its sound, using the same measurement as `scripts/snap_cuts.py`. Limit how far back the search can go, since connected speech has no gaps.

5. **Text builds word by word, on the word.**
   Why: each word showing up as it is said keeps the viewer locked to the voice.
   How to check: each word is its own clip. Each starts on its word. Two words less than 3 frames apart become one step.

6. **Text is white.**
   Why: one color keeps the look clean and on brand. Accent colors pile up and look cheap.
   How to check: text color is white (or the text color in `brand.*`) with the caption shadow. No accent words, no colored strikes, unless the brand settings say otherwise.

7. **Text uses the same shadow as captions.**
   Why: one look across captions and text makes the video feel designed.
   How to check: no border and no hard offset drop shadow on text elements, unless the brand settings call for it.

8. **Graphics hard cut on and off.**
   Why: the clean style is no animation. Fades, slides and bounces feel dated and slow the pace.
   How to check: every state changes on a single frame. Hash each frame of the render. N states should give N runs of identical frames.

9. **A strike comes after the phrase is done.**
   Why: striking in the middle of a build crosses out words not said yet.
   How to check: the strike frame is after the last word of the phrase.

10. **Cut each text state from the render's own frames.**
    Why: working out where a state starts by math can be off by one. The render knows.
    How to check: find state boundaries in the rendered frames, then cut there.

11. **Hooks stay in the safe zone.**
    Why: on shortform, the app's buttons and labels cover the top, bottom and right edge.
    How to check: put a platform safe zone overlay over the hook frame and confirm the text is clear of it.

12. **A hook holds through the opening sentence.**
    Why: the hook should be on screen while the first idea lands, then get out of the way.
    How to check: the hook starts on frame 0 and ends at the end of the first sentence run.

13. **Hide private info in any screenshot or pop up.**
    Why: profile pop ups and screen grabs can show handles, names or account details the creator does not want shown.
    How to check: read every screen graphic at full size. Crop or blur anything private before it ships.

14. **Transition effects sit on the sound.**
    Why: an effect should start when the line before it finishes, and the next line should start when the effect is done.
    How to check: line up the effect's start with the end of the waveform before it, and the next line with the end of the effect sound.

15. **Look at it before calling it done.**
    Why: numbers can all pass while the graphic looks wrong.
    How to check: screenshot each text element on the timeline and look at it.
