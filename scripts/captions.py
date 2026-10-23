"""Caption cards for a job: word map in, timed caption cards out.

Words come from a word->timeline map (work/tl_words.json, or tl_words_v2.json when the
edited audio has been re-transcribed). The rules:

  * 2-3 words per card, grouped so the grouping MAKES SENSE
  * no punctuation at all; the one exception is "?", and only at the END of a card
  * always lower case, except the pronoun "I" and its contractions (I'm, I'll, I've, I'd);
    NOT words that merely start with an i ("ignore", "iguana")
  * no animation, hard cut card to card
"""
import json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as _config  # noqa: E402

if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(
        description="Build and print the caption cards for a job (reads <job>/work/*.json).")
    _ap.add_argument("--job", help="job name (under paths.jobs_dir) or folder path; "
                                   "default $JOB_DIR")
    _a = _ap.parse_args()
    if _a.job:
        os.environ["JOB_DIR"] = str(_config.job_dir(_a.job))

# Job is selectable so one script serves every job. $JOB_DIR points at <jobs_dir>/<job>.
JOB  = os.environ.get("JOB_DIR", "")
WORK = JOB + "/work"
# tl_words_v2.json is the better map: the transcript run on the REBUILT edited audio, so the
# text reflects what is actually audible after the cut. tl_words.json is the original per-word
# map, kept as a fallback.
# work/caption_config.json makes the frame rate, word map and grid explicit per build. Absent ->
# config.yaml video.fps.
# CAPTION_CONFIG lets a re-cut carry its own config without clobbering the previous
# timeline's: the elements, grid, word map and total_frames all move together, and a
# half-updated config is invisible (the plan and the timeline agree while both are stale).
_cfg_p = WORK + "/" + os.environ.get("CAPTION_CONFIG", "caption_config.json")
CFG = json.load(open(_cfg_p)) if os.path.exists(_cfg_p) else {}

V3  = WORK + "/tl_words_v3.json"      # after a later re-cut
V2  = WORK + "/tl_words_v2.json"
SRC = (WORK + "/" + CFG["words"]) if CFG.get("words") else (
      V3 if os.path.exists(V3) else (V2 if os.path.exists(V2) else WORK + "/tl_words.json"))
WORDS = json.load(open(SRC)) if os.path.exists(SRC) else []

FPS       = float(CFG.get("fps", _config.FPS))
_last_t   = max((float(w.get("t", 0)) for w in WORDS), default=0.0) + 1.0
TL_END    = int(CFG.get("total_frames", int(_last_t * FPS))) / FPS   # picture length
# The captions are timed to BOTH the voiceover cuts and the b-roll cuts, so the grid is the
# UNION of the two cut lists: a card may not straddle either kind of cut.
_grid = WORK + "/" + CFG.get("grid", "caption_grid.json")
_slots = WORK + "/" + CFG.get("slots", "slots.json")
if os.path.exists(_grid):
    VO_CUTS = [s["sf"] / FPS for s in json.load(open(_grid))]
elif os.path.exists(_slots):
    VO_CUTS = [s["sf"] / FPS for s in json.load(open(_slots))]
elif os.path.exists(WORK + "/vo_segments.json"):
    VO_CUTS = [s["sf"] / FPS for s in json.load(open(WORK + "/vo_segments.json"))]
else:
    VO_CUTS = []
# WhisperX's forced-alignment onsets sit slightly INSIDE the word: measured against a Groq
# whisper-large-v3 pass over the same audio, they run a median +65 ms (+1.6 frames) late, with
# no drift (slope +0.24 ms/s), i.e. a constant bias rather than a rate mismatch. Captions built
# straight off them therefore lag the voice. Lead the
# cards by 2 frames so a card lands on or a hair before the onset, the eye needs a beat to
# register text, and broadcast subtitling leads for the same reason. Clamped so a lead can
# never pull a card across a cut.
LEAD_F    = int(CFG.get('lead_f', 2))
# How a pause between cards is filled. See fill_gaps().
#   "cut"  (default): the FIRST card of each grid
#          segment is snapped back onto the cut. Correct only when the cut is carved to ~20 ms
#          before the first phoneme, which is true of a carved shortform cut but NOT of a b-roll
#          cut that lands mid-phrase.
#   "hold" the card KEEPS its own word onset, and the gap in front of it is filled by RE-ISSUING
#          the card already on screen (same text, so nothing appears before it is spoken), so
#          the screen is never left bare.
FILL_MODE = CFG.get("fill_mode", "cut")
# Frame ranges where NO caption may be drawn, because something else owns that part of the frame.
# Example: stat cards on V3 that sit straight through the caption band and already carry the
# words the caption would repeat. Switch the caption stream off under a graphic panel.
EXCLUDE   = [tuple(r) for r in CFG.get("exclude_frames", [])]
# Two adjacent words whose TIMESTAMPS came back swapped. Groq is authoritative for TIMING, not
# for word ORDER, and transcribe.py rebuilds the
# order from the segment text, but a map that has already been aligned, carved and remapped
# cannot be rebuilt without re-cutting the film, so the swap is undone here instead.
# work/caption_config.json: "swap_words": [[192, 193]], the two TIMELINE FRAMES to exchange.
SWAP_WORDS = [tuple(r) for r in CFG.get("swap_words", [])]
SNAP_BACK  = int(CFG.get("snap_back_f", 3))   # see hold_forward()
MIN_PIECE  = int(CFG.get("min_piece_f", 4))   # see tidy_slivers()
MAX_HOLD  = 0.85     # how long a card may hang on past its own last word
GAP_CLOSE = 0.30     # butt cards together when the next starts within this
PAUSE     = 0.50     # a gap this big between words forces a card break

# ASR mishearings, fixed on the WORD STREAM (before grouping) so a fix still lands when the
# phrase straddles two cards. Each entry is (words to match, words to put back); matching is
# case- and punctuation-insensitive and any trailing punctuation is carried over.
# Per-job fixes live in work/caption_config.json as "word_fixes": [[["clod"], ["claude"]], ...]
# and in config.yaml as captions.word_fixes in the same shape. Add the brand and product names
# your speaker uses that the transcriber mishears.
WORD_FIXES = [
    (["clod"],  ["claude"]),        # Groq often hears "Claude" as clod/cloud
    (["cloud", "code"], ["claude", "code"]),
]
WORD_FIXES += [(list(a), list(b)) for a, b in (_config.get("captions.word_fixes") or [])]
WORD_FIXES += [(list(a), list(b)) for a, b in CFG.get("word_fixes", [])]


def _tail(tok):
    m = re.search(r'[.,!?;:"]+$', tok)
    return m.group(0) if m else ""


def apply_word_fixes(words):
    out, i, n = [], 0, len(words)
    while i < n:
        hit = None
        for src, dst in WORD_FIXES:
            k = len(src)
            if i + k <= n and [_bare(w) for w in words[i:i + k]] == src:
                hit = (src, dst, k); break
        if not hit:
            out.append(words[i]); i += 1; continue
        src, dst, k = hit
        tail = _tail(words[i + k - 1]["w"])
        for j, tok in enumerate(dst):
            out.append({"w": tok + (tail if j == len(dst) - 1 else ""),
                        "t": words[i + min(j, k - 1)]["t"]})
        i += k
    return out


ENDPUNC = re.compile(r'[.!?]"?$')
COMMA   = re.compile(r'[,;:]$')
# function words that read badly as the last word of a card
GLUE = {"a", "an", "the", "my", "her", "his", "our", "your", "their", "to", "of", "in", "on",
        "at", "for", "and", "but", "so", "with", "from", "that", "this", "as", "by", "into",
        "about"}
# capitalised words that almost always open a new sentence in spoken delivery
STARTERS = {"so", "and", "then", "after", "but", "now", "because", "finally", "once", "while",
            "literally", "unfortunately", "first", "she", "he", "they", "we"}


# How the speaker WRITES a word, which is not always how the transcript spells it. Applied to the
# word stream before grouping, so the shortened form is what gets counted, grouped and rendered.
# Add your own in work/caption_config.json as "spelling": {"though": "tho"}.
SPELLING = dict(CFG.get("spelling", {}))


def apply_swaps(words):
    """Exchange the TEXT of two words identified by their timeline frame (see SWAP_WORDS)."""
    if not SWAP_WORDS:
        return words
    def idx(f):
        return next((i for i, w in enumerate(words)
                     if int(w.get("f", round(w["t"] * FPS))) == f), None)
    for fa, fb in SWAP_WORDS:
        ia, ib = idx(fa), idx(fb)
        if ia is None or ib is None:
            raise SystemExit(f"swap_words: no word at frame {fa if ia is None else fb}")
        words[ia]["w"], words[ib]["w"] = words[ib]["w"], words[ia]["w"]
    return words


def apply_spelling(words):
    out = []
    for w in words:
        key = w["w"].strip().strip('.,!?;:"').lower()
        if key in SPELLING:
            sub = SPELLING[key]
            head = w["w"][:len(w["w"]) - len(w["w"].lstrip())]
            tail = w["w"][len(w["w"].rstrip()):]
            punc = "".join(c for c in w["w"].strip()[-1:] if c in '.,!?;:"')
            if w["w"].strip()[:1].isupper():
                sub = sub[:1].upper() + sub[1:]
            out.append({**w, "w": head + sub + punc + tail})
        else:
            out.append(w)
    return out


def _bare(w):
    return w["w"].strip().strip('.,!?;:"').lower()


# The frames where an EXCLUDE range ENDS, i.e. where a V3 element leaves the screen.
# A card may not carry words across one. `apply_exclusions` keeps only a card's leading fragment,
# so a card that STARTS under an element and runs past its out-point is dropped ENTIRELY, and the
# words it carried that were spoken AFTER the element left go uncaptioned.
# Breaking the group here instead makes the first card after an element start on its own word,
# which is what apply_exclusions' docstring says the stream should do.
#
# The START edge is deliberately NOT a break. A card that begins outside an element and runs into
# it is simply truncated by apply_exclusions, and keeping the natural 2-3 word grouping is right:
# a 2-3 word card holding until the element arrives reads better than a lone word.
EX_END_F = sorted({int(hi) for lo, hi in EXCLUDE})


def _exzone(t):
    """How many element out-points lie at or before this word. Two words with different zones are
    on opposite sides of an element's exit and may not share a card."""
    f = round(t * FPS)
    return sum(1 for e in EX_END_F if e <= f)


def _voseg(t):
    """Index of the voiceover segment a timeline time falls in."""
    lo, hi = 0, len(VO_CUTS) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if VO_CUTS[mid] <= t + 1e-6: lo = mid
        else: hi = mid - 1
    return lo


def next_cut(t):
    """The first grid boundary strictly after `t`. A card may hold right up to it and must
    never hold across it."""
    for c in VO_CUTS:
        if c > t + 1e-6:
            return c
    return TL_END


def snap_to_cuts(words):
    """Nudge a word that sits a hair on the WRONG side of a picture cut.

    Only marginal cases: a word whose onset is within SNAP_F frames of a boundary while the rest of
    its sentence sits on the other side. This used to force every word of a Groq segment into that
    segment's majority cut, which was right when picture cuts matched sentences 1:1, but once
    phrases are split at their internal pauses the cuts are FINER than the sentences, and forcing
    collapsed several cuts' words into one and left the others with no caption at all.

    Word ORDER is fixed upstream in `transcribe.py` (rebuilt from the segment text), so this only
    has to handle the boundary jitter.
    """
    # Keep the reach small (3 frames). A bigger reach can push the last word of a phrase onto
    # the next boundary, orphaning it into its own card. A snap that moves a word FORWARD makes
    # the caption LATE, which is the complaint this whole rule exists to avoid.
    SNAP_F = int(CFG.get("snap_cut_f", 3))
    if not words or all(w.get("seg") is None for w in words):
        return words
    cuts = sorted(int(round(c * FPS)) for c in VO_CUTS)
    for w in words:
        f = w["t"] * FPS
        for c in cuts:
            if 0 < c - f <= SNAP_F:          # just before a cut: does the next word cross it?
                nxt = next((z for z in words if z["t"] > w["t"]), None)
                # The snap may never move a word to or past the NEXT word's onset. The test above
                # is true for the LAST word before any cut, which is most of them, so without
                # this guard the snap pushes that word across the cut and the following `sort`
                # then reorders it against its own neighbour, so a card reads out of order.
                # The word belongs where it was
                # SPOKEN, so a snap that would reorder is refused outright, not clamped.
                if nxt and nxt["t"] * FPS >= c and (c + 0.5) / FPS < nxt["t"]:
                    w["t"] = (c + 0.5) / FPS
                break
    words.sort(key=lambda w: w["t"])
    return words


def group(words):
    cards, i, n = [], 0, len(words)
    while i < n:
        cur, i = [words[i]], i + 1
        seg0 = _voseg(cur[0]["t"])
        while i < n and len(cur) < 3:
            prev, w = cur[-1], words[i]
            if _voseg(w["t"]) != seg0: break            # never straddle a voiceover cut
            if _exzone(w["t"]) != _exzone(cur[0]["t"]): break   # never carry words out of an element
            # Groq gives no punctuation, so its SEGMENT index is the sentence signal. Without this
            # a card runs through a sentence end.
            if w.get("seg") is not None and cur[0].get("seg") is not None \
                    and w["seg"] != cur[0]["seg"]: break
            if (w["t"] - prev["t"]) > PAUSE: break
            if ENDPUNC.search(prev["w"]): break
            if COMMA.search(prev["w"]) and len(cur) >= 2: break
            if w["w"][:1].isupper() and _bare(w) in STARTERS and len(cur) >= 2: break
            if _bare(prev).isdigit() and len(cur) >= 3: break     # keep "1 pm" together
            cur.append(w); i += 1
        # a 3-word card must not end on a function word: give it back, but never go below 2
        if (len(cur) == 3 and i < n and not ENDPUNC.search(cur[-1]["w"])
                and (_bare(cur[-1]) in GLUE or _bare(cur[-1]).isdigit())):
            cur.pop(); i -= 1
        cards.append(cur)

    # a lone word gets absorbed by whichever neighbour it belongs to, if that still fits in 3
    out, k = [], 0
    while k < len(cards):
        c = cards[k]
        joinable_back = (out and len(out[-1]) < 3
                         and (c[0]["t"] - out[-1][-1]["t"]) <= PAUSE
                         and _voseg(c[0]["t"]) == _voseg(out[-1][0]["t"])
                         and _exzone(c[0]["t"]) == _exzone(out[-1][0]["t"])
                         and not ENDPUNC.search(out[-1][-1]["w"])
                         # ...and never back ACROSS A COMMA. group() breaks on one (see the
                         # COMMA rule above); absorbing the stranded word back undoes that break
                         # and re-forms the very card the comma was there to split.
                         and not COMMA.search(out[-1][-1]["w"]))
        joinable_fwd = (k + 1 < len(cards) and len(cards[k + 1]) < 3
                        and (cards[k + 1][0]["t"] - c[0]["t"]) <= PAUSE
                        and _voseg(c[0]["t"]) == _voseg(cards[k + 1][0]["t"])
                        and _exzone(c[0]["t"]) == _exzone(cards[k + 1][0]["t"])
                        and not ENDPUNC.search(c[0]["w"]))
        if len(c) == 1 and joinable_back:
            out[-1].append(c[0])
        elif len(c) == 1 and joinable_fwd:
            cards[k + 1] = c + cards[k + 1]
        else:
            out.append(c)
        k += 1

    # A greedy 3-3-1 split inside one voiceover segment strands the last word as a 1-frame
    # flash. Rebalance to 3-2-2: pull a word back from the predecessor.
    for k in range(len(out) - 1, 0, -1):
        if len(out[k]) == 1 and len(out[k - 1]) == 3 \
                and _voseg(out[k][0]["t"]) == _voseg(out[k - 1][0]["t"]) \
                and _exzone(out[k][0]["t"]) == _exzone(out[k - 1][0]["t"]):
            out[k].insert(0, out[k - 1].pop())
    return out


_DROP = str.maketrans("", "", '.;:!"\u201c\u201d\u2014\u2013')   # comma handled separately, see depunct
_DOT   = "§"        # stand-in for a decimal point while the real ones are stripped
_COMMA = "¤"        # ditto for a thousands separator ($1,000)


# Numbers of 4 or more digits always get their thousands comma ($1,200), automatically rather
# than as a per-job WORD_FIXES entry. The one carve-out is a
# bare four-digit year (1900-2099) with no currency symbol on it, "2,026" would be plainly wrong.
_YEAR = re.compile(r"^(?:19|20)\d\d$")


def group_thousands(text):
    def sub(m):
        run = m.group(0)
        if len(run) < 4:
            return run
        if _YEAR.match(run) and not (m.string[:m.start()].rstrip().endswith(("$", "£", "€"))):
            return run
        return f"{int(run):,}"
    # only whole runs of digits that are not already part of a decimal or a grouped number
    return re.sub(r"(?<![\d.,])\d+(?![\d.,])", sub, text)


def depunct(text):
    """No punctuation. Keeps ' and - inside words (don't, full-time), and BOTH the decimal point
    and the thousands comma inside a number ($9.97, $1,000).
    Four-or-more-digit runs get their commas INSERTED here (see group_thousands).
    Keeps one trailing '?', never a '?' mid-card."""
    text = group_thousands(text)
    q = text.rstrip().endswith("?")
    text = re.sub(r'(?<=\d)\.(?=\d)', _DOT, text)
    text = re.sub(r'(?<=\d),(?=\d)', _COMMA, text)
    text = text.replace("?", " ").replace(",", " ")
    text = text.translate(_DROP).replace(_DOT, ".").replace(_COMMA, ",")
    text = re.sub(r"\s+", " ", text).strip(" -’'")
    return (text + "?") if q and text else text


_I = re.compile(r"\b(i)('(?:m|ll|ve|d|s))?\b")


def lower_except_i(text):
    return _I.sub(lambda m: "I" + (m.group(2) or ""), text.lower())


def build():
    cards = group(snap_to_cuts(apply_spelling(apply_word_fixes(apply_swaps(WORDS)))))
    out = []
    for i, c in enumerate(cards):
        raw = re.sub(r'\s+', ' ', " ".join(w["w"] for w in c).strip())
        text = lower_except_i(depunct(raw))
        if not text:
            continue
        # A card starts ON THE WORD. An earlier build snapped the first card of every
        # segment back to the cut so no cut was left uncaptioned, that put cards on screen
        # up to half a second BEFORE the words are spoken, which reads as mistimed.
        # The word onset is always inside its own segment, so starting on it can never
        # straddle a cut; only the END has to be clamped.
        start = c[0]["t"]
        nxt = cards[i + 1][0]["t"] if i + 1 < len(cards) else TL_END
        own = c[-1]["t"] + MAX_HOLD
        end = min(nxt if (nxt - own) <= GAP_CLOSE else own, TL_END, next_cut(start))
        # FLOOR the start, round the end. `round` puts a card up to half a frame AFTER the word
        # it captions, and a late caption is the exact complaint this pipeline exists to avoid
        # (cards lead rather than lag: the eye needs a beat to register text). Flooring can only
        # ever move a card one frame EARLIER, and never past its own word's frame.
        out.append({"text": text, "start": start, "end": end, "words": list(c),
                    "sf": int(start * FPS), "ef": int(round(end * FPS))})
    out.sort(key=lambda c: c["sf"])
    for i in range(len(out) - 1):                       # never overlap
        if out[i]["ef"] > out[i + 1]["sf"]:
            out[i]["ef"] = out[i + 1]["sf"]

    # A card shorter than MIN_F reads as a flash. Give it room from the gap that follows;
    # if there is no gap, fold its words into the neighbour inside the same voiceover segment.
    MIN_F = 6
    i = 0
    while i < len(out):
        c = out[i]
        if c["ef"] - c["sf"] >= MIN_F:
            i += 1; continue
        nxt = out[i + 1] if i + 1 < len(out) else None
        limit = min((nxt["sf"] if nxt else round(TL_END * FPS)),
                    round(next_cut(c["sf"] / FPS) * FPS))
        room = limit - c["sf"]
        if room >= MIN_F:
            c["ef"] = c["sf"] + MIN_F; i += 1; continue
        prev = out[i - 1] if i else None
        # Folding a short card into a neighbour EXTENDS that neighbour over the sliver's frames,
        # so it may not reach across a picture cut. `_voseg` alone is not enough: it compares
        # VOICEOVER segments, while the grid is the UNION of the VO and b-roll cut lists, so a
        # b-roll cut sitting inside one VO segment slips straight through. The standing rule is
        # "no caption in between cuts". tidy_slivers guards the same way.
        def _spans_cut(a, b):
            return any(a < x * FPS < b for x in VO_CUTS)
        if prev and _voseg(prev["sf"] / FPS) == _voseg(c["sf"] / FPS) \
                and not _spans_cut(prev["sf"], c["ef"]) \
                and len(prev["text"].split()) + len(c["text"].split()) <= 3:
            prev["text"] = (prev["text"].rstrip("?") + " " + c["text"]).strip()
            prev["ef"] = c["ef"]; out.pop(i); continue
        if nxt and _voseg(nxt["sf"] / FPS) == _voseg(c["sf"] / FPS) \
                and not _spans_cut(c["sf"], nxt["ef"]) \
                and len(nxt["text"].split()) + len(c["text"].split()) <= 3:
            nxt["text"] = (c["text"] + " " + nxt["text"].lstrip()).strip()
            nxt["sf"] = c["sf"]; out.pop(i); continue
        c["ef"] = c["sf"] + max(1, room)                 # last resort: leave it as-is
        i += 1
    return fill_gaps([c for c in out if c["ef"] > c["sf"]])


def fill_gaps(cards):
    """Align captions to the film's own cuts, and never leave a frame bare.

    Rule: time the captions to the main video's cuts (no caption in between cuts).
    A card must live entirely inside ONE cut of the picture. Earlier builds filled a pause by
    holding the current card and RE-ISSUING it after the cut, which put the same words either side
    of a cut. That is a caption sitting "in between cuts", which is not allowed.

    So per cut segment:
      * the FIRST card starts ON the cut,
      * the LAST card ends ON the next cut,
      * cards in between keep their word timing.

    Starting on the cut is only honest because the cut itself is now trimmed to ~20 ms before the
    first phoneme (see carve_silence.py). When the cut is tight to the speech, "aligned to the
    cut" and "aligned to the word" are the same instant, which is why the old snap-to-cut put
    captions half a second early and this one does not.
    """
    grid = sorted({int(round(c * FPS)) for c in VO_CUTS})
    end_f = int(round(TL_END * FPS))
    bounds = grid + [end_f]

    out = []
    for lo, hi in zip(bounds, bounds[1:]):
        seg = [c for c in cards if lo <= c["sf"] < hi]
        if not seg:
            continue
        seg.sort(key=lambda c: c["sf"])
        for a, b in zip(seg, seg[1:]):          # butt cards together inside the segment
            a["ef"] = b["sf"]
        if FILL_MODE != "hold":
            seg[0]["sf"] = lo                    # first card starts ON the cut
        seg[-1]["ef"] = hi                       # last card ends ON the next cut
        for c in seg:
            c["start"], c["end"] = c["sf"] / FPS, c["ef"] / FPS
        out.extend(seg)
    if FILL_MODE == "hold":
        out = hold_forward(out, bounds)
    # apply_overrides lives INSIDE build() on purpose: build_caption_clips.py and
    # place_caption_clips.py call build() directly, so an override applied only in __main__
    # renders and places the un-overridden cards while captions.py prints the right ones.
    cards = close_element_gaps(
        apply_exclusions(apply_overrides([c for c in out if c["ef"] > c["sf"]])))
    return tidy_slivers(cards, bounds) if FILL_MODE == "hold" else cards


def hold_forward(cards, bounds):
    """Fill every gap from the LEFT, and never across a cut.

    A card keeps its own word onset, so leaving the last
    card of the previous segment ending on the cut opens a hole between the cut and the next word.
    Fill it by RE-ISSUING the card already on screen: identical text, starting on the cut, so
    nothing appears before it is spoken and the caption reads as continuous through the cut. The
    held copy reuses its parent's rendered clip, so it costs nothing to render.

    The fill is split at every grid boundary it crosses, so a held card can never straddle a cut.
    A hole before the FIRST card of the film has nothing to hold and is left bare.
    """
    cards = sorted(cards, key=lambda c: c["sf"])
    out = []
    for c in cards:
        # A hole of a frame or two is not worth a timeline item: re-issuing the held card there
        # makes a 1-frame clip that is indistinguishable on screen and miserable to trim by hand.
        # Let the next card open on the cut instead, at most SNAP_BACK frames early, which is
        # inside the aligner's own 20-80 ms bias and well under the 2.4-frame worst case the
        # start-on-the-word fix measured.
        if out and 0 < c["sf"] - out[-1]["ef"] <= SNAP_BACK:
            # ...but the snap may never reach back across a V3 element's OUT-point. Doing so puts
            # the card's START inside an EXCLUDE range, and `apply_exclusions` keeps only a card's
            # LEADING fragment, so a card that begins inside an element and runs past its
            # out-point is dropped ENTIRELY, taking the words spoken AFTER the element left with
            # it, leaving bare frames. This only appears when an element's out-point lands
            # 1..SNAP_BACK frames after the previous card's end, so it is easy to miss.
            floor = out[-1]["ef"]
            for lo, hi in EXCLUDE:
                if floor < hi <= c["sf"]:
                    floor = hi
            # ...and it may never reach back across a PICTURE CUT either. The grid is the union
            # of the VO and b-roll cut lists, and the standing rule is that no card sits across
            # one. Without this, a card whose first word lands 1-2 frames after a cut gets pulled
            # to the far side of it, straddling the cut. Same shape as the EXCLUDE floor above, a snap that
            # is free within a shot is not free across an edit.
            for b in bounds:
                if floor < b <= c["sf"]:
                    floor = b
            if floor < c["sf"]:
                c["sf"] = floor
                c["start"] = c["sf"] / FPS
        if out and out[-1]["ef"] < c["sf"]:
            prev = out[-1]
            # A hold may never reach INTO an excluded range, let alone across it: the caption
            # that was on screen before a V3 text element must stop when the element arrives,
            # and the next card must start on its own word after the element leaves.
            stop = min([c["sf"]] + [lo for lo, hi in EXCLUDE if prev["ef"] < lo < c["sf"]])
            edges = [prev["ef"]] + [b for b in bounds if prev["ef"] < b < stop] + [stop]
            for lo, hi in zip(edges, edges[1:]):
                if any(a < hi and lo < b for a, b in EXCLUDE):
                    continue
                out.append({"text": prev["text"], "sf": lo, "ef": hi,
                            "start": lo / FPS, "end": hi / FPS, "held": True,
                            **({"plate": prev["plate"]} if prev.get("plate") else {})})
        out.append(c)
    return out


def apply_exclusions(cards):
    """Drop / trim cards inside a range the caption may not occupy (see EXCLUDE).

    A card that runs INTO an exclusion keeps only its leading fragment, it ends when the V3
    element arrives. The fragment that would RESUME at the far edge is thrown away rather than
    restarted on the boundary: the words it carries were spoken under the element, and a caption
    reappearing mid-phrase exactly on the element's out-point reads as a glitch. The stream picks
    up again at the first card that starts on its own word after the element has left.
    """
    if not EXCLUDE:
        return cards
    out = []
    for c in cards:
        pieces = [(c["sf"], c["ef"])]
        for lo, hi in EXCLUDE:
            nxt = []
            for a, b in pieces:
                if b <= lo or a >= hi:
                    nxt.append((a, b)); continue
                if a < lo:
                    nxt.append((a, lo))          # keep the head; drop everything from `lo` on
            pieces = nxt
        for a, b in pieces:
            if b <= a:
                continue
            # Trimming the card's FRAMES is not enough, its TEXT has to lose the words that
            # were spoken under the element. A text animation always wins over the caption,
            # and its words are taken out of the caption.
            # Without this the caption GIVES AWAY the element's words before the element builds
            # them, which is the opposite of a word-by-word build.
            # Only the UPPER bound matters: apply_exclusions keeps the leading fragment, so `a`
            # is always the card's own start. Testing `a <= w` wrongly dropped a card's FIRST
            # word whenever `sf = round(t)` rounded up past it.
            kept = [w for w in c.get("words", []) if w["t"] * FPS < b]
            if c.get("words") and not kept:
                continue                      # nothing of its own left to say
            txt = c["text"]
            if kept and len(kept) != len(c["words"]):
                txt = lower_except_i(depunct(
                    re.sub(r"\s+", " ", " ".join(w["w"] for w in kept).strip())))
                if not txt:
                    continue
            out.append({**c, "text": txt, "words": kept or c.get("words", []),
                        "sf": a, "ef": b, "start": a / FPS, "end": b / FPS})
    return out


def close_element_gaps(cards):
    """Close the sliver of bare film an element's OUT-POINT can leave.

    A card may not start before its own word, and a hold may not resume across an element, so
    when a V3 element leaves one or two frames before the next word is spoken, those frames belong
    to nothing. That is the same situation `hold_forward` already rules on: a hole of a frame or
    two is not worth a timeline item, so the next card opens early instead, by at most SNAP_BACK
    frames, inside the aligner's own 20-80 ms bias, and far under the 2.4-frame worst case the
    start-on-the-word fix measured. Only an element out-point is closed this way; a picture cut is
    handled upstream, and a longer hole is left alone rather than dragging a card off its word.
    """
    if not EX_END_F:
        return cards
    cards = sorted(cards, key=lambda c: c["sf"])
    ends = {c["ef"] for c in cards}
    for i, c in enumerate(cards):
        prev_ef = cards[i - 1]["ef"] if i else 0
        for e in EX_END_F:
            # ...but never back across a PICTURE CUT. Closing the sliver an element out-point
            # leaves is worth a couple of frames of lead; putting the card on the far side of an
            # edit is not, and "no caption in between cuts" is the older and stronger rule.
            # `<=` on the upper bound, deliberately: the card usually starts EXACTLY on the
            # cut, so a strict `<` misses the very case this guard exists for.
            if any(e < x * FPS <= c["sf"] for x in VO_CUTS):
                continue
            if prev_ef <= e < c["sf"] <= e + SNAP_BACK and e not in ends:
                c["sf"] = e
                c["start"] = e / FPS
                break
    return cards


def tidy_slivers(cards, bounds):
    """Absorb any card left shorter than MIN_PIECE.

    Trimming a card against an EXCLUDE range leaves a stub (a 1-frame "now" after the $30 stat
    card). Hand it to the NEXT card where that stays inside one grid segment and outside every
    exclusion, else to the previous one, else drop it, a sub-4-frame hole is invisible and a
    sub-4-frame timeline item is not.
    """
    def crosses(a, b):
        return any(a < x < b for x in bounds) or any(a < hi and lo < b for lo, hi in EXCLUDE)

    out = [dict(c) for c in cards]
    i = 0
    while i < len(out):
        c = out[i]
        if c["ef"] - c["sf"] >= MIN_PIECE:
            i += 1; continue
        nxt = out[i + 1] if i + 1 < len(out) else None
        prev = out[i - 1] if i else None
        if nxt and nxt["sf"] == c["ef"] and not crosses(c["sf"], nxt["ef"]):
            nxt["sf"] = c["sf"]; nxt["start"] = c["sf"] / FPS
        elif prev and prev["ef"] == c["sf"] and not crosses(prev["sf"], c["ef"]):
            prev["ef"] = c["ef"]; prev["end"] = c["ef"] / FPS
        out.pop(i)
    # a held card that now butts a same-text neighbour is one caption, so make it one item
    merged = []
    for c in out:
        if merged and merged[-1]["ef"] == c["sf"] and merged[-1]["text"] == c["text"] \
                and not crosses(merged[-1]["sf"], c["ef"]):
            merged[-1]["ef"] = c["ef"]; merged[-1]["end"] = c["ef"] / FPS
        else:
            merged.append(c)
    return merged


def srt(cards):
    def tc(s):
        h = int(s // 3600); m = int(s % 3600 // 60)
        return f"{h:02d}:{m:02d}:{s % 60:06.3f}".replace(".", ",")
    return "\n".join(f"{i+1}\n{tc(c['sf']/FPS)} --> {tc(c['ef']/FPS)}\n{c['text']}\n"
                     for i, c in enumerate(cards))


# ---------------------------------------------------------------------------------------------
# Per-job card overrides: work/card_overrides.json replaces every card whose span falls inside a
# given frame range with a hand-authored run. Written for the cumulative LIST card (a card whose
# text contains newlines renders top-anchored and left-aligned, see render_caption_frames.py).
# Ranges are in TIMELINE frames and must line up with grid boundaries, or a list card would
# straddle a picture cut. The override is validated against the grid for exactly that.
# ---------------------------------------------------------------------------------------------
def apply_overrides(cards):
    # $CARD_OVERRIDES lets a re-cut carry its own hand-authored run without clobbering the
    # previous timeline's, the frames shift on every re-cut, and a stale override is invisible
    # (it simply stops matching any card, and the greedy grouper's split ships silently).
    path = WORK + "/" + os.environ.get("CARD_OVERRIDES", "card_overrides.json")
    if not os.path.exists(path):
        # Speaker plates/shadows were only tagged on the override path, so a job WITHOUT
        # card_overrides.json would ship every card in the default colour. Tag here too.
        return tag_shadows(tag_plates(cards))
    grid = sorted({int(round(c * FPS)) for c in VO_CUTS}) + [int(round(TL_END * FPS))]
    out = list(cards)
    for ov in json.load(open(path)):
        lo, hi = int(ov["from"]), int(ov["to"])
        out = [c for c in out if c["ef"] <= lo or c["sf"] >= hi]
        for c in ov["cards"]:
            sf, ef = int(c["sf"]), int(c["ef"])
            for b in grid:
                if sf < b < ef:
                    raise SystemExit(f"override card {c['text']!r} straddles a picture cut at {b}")
            out.append({"sf": sf, "ef": ef, "text": c["text"],
                        "start": sf / FPS, "end": ef / FPS})
    out.sort(key=lambda c: c["sf"])
    for a, b in zip(out, out[1:]):
        if a["ef"] != b["sf"]:
            raise SystemExit(f"override left a gap/overlap: {a['ef']} -> {b['sf']}")
    return tag_shadows(tag_plates(out))


# ---------------------------------------------------------------------------------------------
# Per-SPEAKER plate colour: for example a grey plate while the host talks and an accent colour
# while a second voice talks.
# work/caption_plates.json is [{"from": f, "to": f, "plate": [r,g,b]}] in TIMELINE frames, built
# from the `speaker` field of transcript/cuts_annotated.json. A card always lies inside one grid
# segment, so its start frame decides its plate unambiguously.
# ---------------------------------------------------------------------------------------------
def tag_shadows(cards):
    """Per-SPEAKER shadow colour, the same shape as tag_plates.

    The PLATE stays the same for every card and the second voice is marked by a coloured glow on
    the glyphs instead. $CAPTION_SHADOWS is
    [{"from": f, "to": f, "shadow": [r,g,b]}] in TIMELINE frames; a card always lies inside one
    grid segment, so its start frame decides its shadow unambiguously.
    """
    path = WORK + "/" + os.environ.get("CAPTION_SHADOWS", "caption_shadows.json")
    if not os.path.exists(path):
        return cards
    for c in cards:
        for sp in json.load(open(path)):
            if sp["from"] <= c["sf"] < sp["to"] and sp.get("shadow"):
                c["shadow"] = list(sp["shadow"]); break
    return cards


def tag_plates(cards):
    path = WORK + "/caption_plates.json"
    if not os.path.exists(path):
        return cards
    spans = json.load(open(path))
    for c in cards:
        for sp in spans:
            if sp["from"] <= c["sf"] < sp["to"] and sp.get("plate"):
                c["plate"] = list(sp["plate"]); break
    return cards


if __name__ == "__main__":
    if not WORDS:
        sys.exit(f"no word map found in {WORK}. Set --job or JOB_DIR, and build work/tl_words.json.")
    cs = build()
    words = sum(len(c["text"].split()) for c in cs)
    ones = sum(1 for c in cs if len(c["text"].split()) == 1)
    longs = [c for c in cs if len(c["text"].split()) > 3]
    print(f"{len(cs)} cards, {words} words, {ones} one-word, {len(longs)} over-3")
    print("source:", SRC)
    for c in cs:
        print(f'{c["sf"]:5d}-{c["ef"]:5d} ({(c["ef"]-c["sf"])/FPS:4.2f}s) '
              f'{len(c["text"].split())}w  '
              f'[plate {"gold" if c.get("plate") and c["plate"][2] < 150 and c["plate"][0] > 150 else "grey"}'
              f'{" / shadow " + "#%02x%02x%02x" % tuple(c["shadow"]) if c.get("shadow") else ""}]  {c["text"]}')
