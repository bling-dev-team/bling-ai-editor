# Caption principles

Most people watch with the sound off, so captions carry the video. Good captions land on the word, change often, never cover a picture cut, and never leave a frame empty. These rules tell you how to build and check them.

Scripts: `scripts/captions.py` groups words into cards, `scripts/build_caption_overlay.py` renders and places them, `scripts/verify_resolve.py` reads the timeline back. Look and position come from `config.yaml`: `captions.look`, `captions.center_y`, and the `brand.*` keys for font and colors.

## Rules

1. **Change the caption every 1 to 2 seconds.**
   Why: frequent change keeps the eye busy and the viewer watching. This is where the "edit every 1 to 2 seconds" feeling comes from.
   How to check: list card lengths. Most should sit between 1 and 2 seconds. Flag any card over about 2.5 seconds.

2. **Keep cards short: 2 or 3 words.**
   Why: short cards read in one glance.
   How to check: count words per card. Split anything over 3 or 4 words.

3. **A caption starts on its word, never after it.**
   Why: a caption that shows up late feels out of sync. Rounding a start time up puts it after the word.
   How to check: round start times down (floor), never to nearest. Compare each card's first frame to its first word's aligned start.

4. **Only the end of a card gets clamped.**
   Why: you can shorten a card to fit, but moving its start breaks sync.
   How to check: no card start was moved off its word to fit a cut or gap.

5. **A caption never crosses a picture cut.**
   Why: the same words on both sides of a cut look like a glitch.
   How to check: for every picture cut, no card starts before it and ends after it. A card can snap to a nearby cut (a few frames at most) but never change word order to do it.

6. **No frame of the video is uncaptioned.**
   Why: an empty gap breaks the rhythm and looks like a mistake.
   How to check: walk every frame. Fill gaps by stretching the card on the left, but never past a picture cut. If a card already ends on a cut, the next card has to start there.

7. **Build captions from the edited audio, not the raw transcript.**
   Why: the edit removed words and moved time. Raw timing will be wrong.
   How to check: transcribe and align the edited audio (`scripts/transcribe.py`, `scripts/align_words.py`), then build from that.

8. **The caption look is chosen by format.**
   Why: shortform and longform are watched differently. Each needs its own size, position and style.
   How to check: read `captions.look` and `captions.center_y` from `config.yaml`. Do not hardcode a look in a script.

9. **Text rules: lower case, almost no punctuation.**
   Why: clean text reads faster.
   How to check: lower case except "I" and its contractions. No punctuation except a trailing question mark and the comma inside big numbers (10,000).

10. **Numbers show as digits.**
    Why: "10,000" reads faster than "ten thousand".
    How to check: scan cards for spelled out numbers.

11. **The font comes from your brand settings, not from a reference video.**
    Why: guessing a font off someone else's video gets it wrong. Your brand font is known.
    How to check: the font in the render matches `brand.*` in `config.yaml`.

12. **Shadow is the default style, border on request.**
    Why: a soft shadow keeps white text readable without looking heavy.
    How to check: test the card over the brightest, busiest frame of the video. If it is hard to read, raise the shadow. If a value looks too strong once rendered, try it at a tenth.

13. **Put captions where they do not cover the face.**
    Why: covering the mouth or eyes hurts the talking head.
    How to check: measure the face box on a few frames per shot and set `captions.center_y` below the chin. Check with a screenshot on every shot, not just one.

14. **Lists stack, they do not shift.**
    Why: when the creator lists things, each new item should add below. Moving the block each time is hard to read.
    How to check: mark list cards on purpose (do not guess from line breaks). Anchor the list at the top so the finished list ends up centred. Each line lands on the first word of that line.

15. **Do not print words a text element is about to show.**
    Why: if a graphic builds the same words, the caption doubles them.
    How to check: for each text element, exclude those words from captions for that range. The end of the exclusion lands on a card boundary.

16. **If two people talk, show who is speaking.**
    Why: the viewer should know whose words they are reading.
    How to check: use a color per speaker from `brand.*`. Tell speakers apart by voice and picture, not by reading the text.

17. **Captions are real clips on their own track.**
    Why: separate clips can be timed, moved and checked one by one. One flat overlay cannot.
    How to check: each card is its own clip. Give each a new file name when it changes, so the editor does not show a stale cached version.

18. **The cache key holds every visual setting.**
    Why: if a setting (size, shadow, color) is not part of the key, old clips get reused after you change the look.
    How to check: change one setting and confirm every affected clip re-renders.

19. **Prove it on the real timeline.**
    Why: the plan can be right while the timeline is wrong.
    How to check: run `scripts/verify_resolve.py`. Then take screenshots of a few cards over different shots and look at them.
