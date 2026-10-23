# B-roll principles

B-roll is the footage that plays over the talking head. Good b-roll shows what the words say, right when the words say it. Bad b-roll is random, badly framed, or leaks private info. These rules tell you how to pick, place and check every insert.

Scripts: `scripts/place_inserts.py` places inserts, `scripts/audit_broll.py` checks them, `scripts/verify_resolve.py` reads the timeline back.

## Rules

1. **Cut the b-roll on the words.**
   Why: the picture should change on the syllable it shows (the kick on "kick", the laugh on "laughing"). When picture and word land together, the viewer feels the edit is tight.
   How to check: map each key word to its timeline frame (from the aligned word list) and confirm an insert starts within 1 or 2 frames of it.

2. **The voiceover's own cuts are the spine.**
   Why: every cut in the talking head is a natural place for the picture to change. Following them gives you good pacing without chasing a number.
   How to check: every voiceover cut starts a new b-roll clip. Split any voiceover piece longer than about 2.3 seconds. Merge any piece shorter than about 8 frames instead of cutting there.

3. **A clip is not a beat.**
   Why: one long clip often holds several moments plus dead stretches. Treating the whole clip as one thing puts the wrong moment under the wrong line.
   How to check: split each clip into moments by what changes on screen, cap each moment at about 8 seconds, and drop dead footage (empty rooms, nothing happening).

4. **Label every moment by subject and action, never by camera move.**
   Why: "whip pan across the seat" tells you nothing about what the viewer sees. "She picks up the bag" does, and that is what you match to the words.
   How to check: read your shot list. Every label should name who or what is in frame and what they are doing.

5. **Score framing as well as motion, then pick by eye.**
   Why: picking the most motion lands you mid pan, where the subject is sliding out of frame. One number never makes a good pick.
   How to check: score each window for detail (is there something to look at), centre (is the subject near the middle area) and edge (is the subject getting chopped at the frame edge). Shortlist the top 4 windows per slot, render one frame from each, and look before choosing.

6. **A body part is not a shot, and a clipped head is a reject.**
   Why: feet or hands with no context read as a mistake. A head cut off at the top of frame looks broken.
   How to check: look at the rendered frame. A person should be readable as a person, with the head fully in frame.

7. **Never use the setup phase of a clip.**
   Why: the first seconds of a self shot clip are often the creator checking the lens, fixing the tripod or walking into place. That looks awkward on screen.
   How to check: window every clip past the setup, into the part where the person is actually doing the thing. Reject any window where someone looks at the camera to check it.

8. **Movement means the subject moves, not the camera.**
   Why: a still person with a moving camera still feels static. A walk should go forward, not wander back.
   How to check: watch the window. The person or thing in frame should be doing something. If the camera moves, let the move finish before the window ends.

9. **Pick eye catching footage, not just on topic footage.**
   Why: on topic and well shot is the floor. The bar is a frame a scroller would stop on.
   How to check: after a clip passes relevance and framing, rank the shortlist on "would this stop the scroll" and take the highest.

10. **B-roll of the creator should make them look good, and fit the tone of the line.**
    Why: awkward poses hurt trust. Footage that fights the line (a playful moment under a serious business point) feels off.
    How to check: watch each insert with the words playing. Ask: does the creator look confident and natural, and does the mood match?

11. **Add a picture the talking head does not already have.**
    Why: if the creator is already in the kitchen on camera, a b-roll of the same kitchen adds nothing.
    How to check: compare each insert to the talking head shot under it. It should show a new place, thing or moment.

12. **A transition word means the picture is already at the next place.**
    Why: words like "then", "after that" and "finally" tell the viewer the story moved. The picture should move with them.
    How to check: find each transition word and confirm the new scene starts on or before it.

13. **Never reuse the same seconds of a clip.**
    Why: the viewer notices a repeat. Reusing a clip is fine, reusing the same range is not.
    How to check: `scripts/audit_broll.py` flags any overlapping source range.

14. **A reused clip must run forward, and the story runs in order after the intro.**
    Why: going back in time inside a clip feels wrong. The intro is a montage of the best moments, but after it, order by when things happened (capture time plus offset inside the clip).
    How to check: source in points go up down the timeline after the intro. Set the intro length in your audit config, since it cannot be guessed.

15. **A slot under about 12 frames stays on a neighbour clip.**
    Why: a hard cut to new footage for under half a second reads as a glitch.
    How to check: any slot shorter than 12 frames uses a later, non overlapping part of the clip next to it.

16. **Never show people who did not agree to be in the video.**
    Why: their face is their choice, and showing them can cause real harm. This includes faces on a call or a screen in the background.
    How to check: look at every person in every insert, including people on monitors and phones. If you are not sure they agreed, do not use the clip. Move known no go clips to a separate folder so they are never picked again.

17. **Read every screen in a shot before you use it.**
    Why: a monitor, laptop, phone or TV can show private info: bookmark bars, tab titles, URLs, dashboards, revenue, client names, live chat names. A shot can score well and still leak.
    How to check: view the screen content at full resolution across the whole window, not one frame. Reject the shot. Do not try to crop or blur around it. A shot is cleared by what is on it, never by its file name or score.

18. **Grade and tone map every insert so it matches.**
    Why: footage from different cameras looks different. An ungraded clip looks washed out or too punchy next to the others.
    How to check: put each insert next to the talking head and the other inserts. Match the look to each source's own character, not to a number. Do not trust "this is already standard color", measure it. A look that is too strong at full strength can be blended down over a neutral base.

19. **Place b-roll silent, frame exact, with no flashes.**
    Why: b-roll audio fights the voice. B-roll frame rates often differ from the timeline, and rounding errors leave one frame black flashes at cuts.
    How to check: place video only. Round converted source lengths up and add one safety frame. Work out positions in whole frames, never by adding up decimals. Read the timeline back with `scripts/verify_resolve.py`: zero gaps, no black frames, no b-roll audio.

20. **Camera brand does not matter, the picture does.**
    Why: what counts is the shot, not the device. Horizontal clips can be cropped to vertical for shortform.
    How to check: when cropping, crop at full source resolution and run the framing check on the cropped frame.
