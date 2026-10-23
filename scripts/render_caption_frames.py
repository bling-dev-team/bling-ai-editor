"""Render caption cards to RGBA PNGs (one transparent full-frame PNG per card).

Defaults come from config.yaml (brand.*, captions.*, video.*); any key can be overridden per job
in <job>/work/caption_config.json. Three looks, chosen by `captions.look` (or `style` in the job
config):

  "border"  solid outline around white text
  "shadow"  soft drop shadow, no outline
  "pill"    white text on a translucent rounded plate

List cards (text prefixed "list:") have knobs of their own in work/caption_config.json:
`list_center_y`, `list_bullet` ("minus" draws a rounded bar; "" turns it off), `list_lines`,
`list_widest`. Every visual knob is hashed into STYLE_DIR, because rewriting a clip under its old
filename leaves Resolve's viewer showing stale frames.

    python3 scripts/render_caption_frames.py "some words" /tmp/card.png
"""
import json as _json
import os as _os
import sys as _sys
from pathlib import Path as _Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import config as _config  # noqa: E402

# Read the SAME job config captions.py reads, so `style` set there actually reaches the render.
# CAPTION_CONFIG still overrides, for one-off style tests.
_JOB = _os.environ.get("JOB_DIR", "")
_JOB_CFG = _JOB + "/work/" + _os.environ.get("CAPTION_CONFIG", "caption_config.json")
_cfg = {}
for _c in (_os.environ.get("CAPTION_CONFIG"), _os.environ.get("CAPTION_JOB_CONFIG"), _JOB_CFG):
    if _c and _os.path.exists(_c):
        _cfg = _json.load(open(_c)); break


def _hex(c, default):
    c = c or default
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


# --- frame size ----------------------------------------------------------
# Everything below is expressed against W/H, so the same renderer serves both orientations, and
# W/H are part of the cache key, or a 4K rebuild would silently reuse the 1080-wide clips.
W = int(_cfg.get("width", _config.WIDTH))
H = int(_cfg.get("height", _config.HEIGHT))

# Font: a per-job copy in <job>/graphics/fonts wins, then paths.fonts_dir/brand.font_file.
_FACE = _cfg.get("font", _config.get("brand.font_file", ""))
_cands = []
if _FACE:
    _cands.append(_JOB + "/graphics/fonts/" + _FACE)
    _fd = _config.path("paths.fonts_dir", "./assets/fonts")
    if _fd:
        _cands.append(str(_fd / _FACE))
    _cands.append(_os.path.expanduser("~/Library/Fonts/" + _FACE))
FONT = next((p for p in _cands if p and _os.path.exists(p)), None)
SIZE = int(_cfg.get("size_px", _config.get("captions.font_size", 72)))
_UPPER = bool(_cfg.get("uppercase", _config.get("captions.uppercase", False)))
FILL = tuple(_cfg.get("fill", _hex(_config.get("brand.primary_color"), "#FFFFFF") + (255,)))
# `center_y` is the vertical CENTRE of the card in px. config captions.center_y is a fraction.
CENTER_Y     = int(_cfg.get("center_y", int(H * float(_config.get("captions.center_y", 0.5)))))
MAX_W        = int(W * float(_cfg.get("max_w_frac", 0.86)))

STYLE        = _cfg.get("style", _config.get("captions.look", "border"))
STROKE_W     = int(_cfg.get("stroke_w", _config.get("captions.border_px", 6)))
STROKE_FILL  = (0, 0, 0, 255)
# Shadow opacity is a judgement call in 0.10-0.30: bright or busy footage under the caption needs
# the top of that range, dark or clean footage the bottom. Pick it by looking at real frames.
SHADOW_ALPHA = float(_cfg.get("shadow_alpha", 0.20))
SHADOW_BLUR  = float(_cfg.get("shadow_blur", 1.00))   # smoothing, 0-1
SHADOW_DIST  = float(_cfg.get("shadow_distance", 5.0))
SHADOW_ANGLE = float(_cfg.get("shadow_angle", -45.0))
# Smoothing is not in pixels. 100 % smoothing == 0.14 em of Gaussian radius, the widest blur that
# still leaves the glyph edge readable over bright footage. config captions.shadow_blur, when set,
# is taken as the radius in px instead. EYEBALL ONE CARD before rendering a whole film.
BLUR_PX      = float(_cfg.get("shadow_blur_px", _config.get("captions.shadow_blur",
                                                            SHADOW_BLUR * 0.14 * SIZE)))
# A 100 %-blur shadow needs MASS: blurring a bare glyph outline spreads it to almost nothing.
# `shadow_spread` is a stroke, in px, applied to the SHADOW pass only.
SHADOW_SPREAD = int(_cfg.get("shadow_spread", 0))

# "pill": text on a translucent rounded rectangle, no outline, no shadow. Expressed as ratios of
# SIZE so a size change keeps the proportions.
PILL_BG       = tuple(_cfg.get("pill_bg", _hex(_config.get("captions.pill_color"), "#767676")))
PILL_ALPHA    = float(_cfg.get("pill_alpha", 0.50))
PILL_H        = int(_cfg.get("pill_h", round(SIZE * 1.83)))
PILL_PAD_X    = int(_cfg.get("pill_pad_x", round(SIZE * 0.46)))
PILL_RADIUS   = int(_cfg.get("pill_radius", round(SIZE * 0.41)))
PILL_BASE_OFF = int(_cfg.get("pill_baseline_offset", round(SIZE * 0.30)))
PILL_SS       = 4      # supersample the plate; PIL's rounded_rectangle corners alias badly at 1x
PILL_ONE_LINE = bool(_cfg.get("pill_one_line", False))
PILL_MIN_SIZE = int(_cfg.get("pill_min_size", round(SIZE * 0.82)))
# Per-SPEAKER shadow colour on the pill: the PLATE stays the same for everyone and a second voice
# is marked by a coloured glow on the glyphs instead. Ratios of the type SIZE so it ports.
PILL_SH_ALPHA  = float(_cfg.get("pill_shadow_alpha", 0.50))
PILL_SH_BLUR   = float(_cfg.get("pill_shadow_blur", 1.00))
PILL_SH_DIST_R = float(_cfg.get("pill_shadow_distance_ratio", 0.083))
PILL_SH_SPRD_R = float(_cfg.get("pill_shadow_spread_ratio", 0.083))
PILL_SH_ANGLE  = float(_cfg.get("pill_shadow_angle", -45.0))

_FONT_HELP = (f"caption font not found. Put {_FACE or 'a .ttf/.otf'} in paths.fonts_dir and set "
              f"brand.font_file in config.yaml.")
_f = ImageFont.truetype(FONT, SIZE) if FONT else ImageFont.load_default()

def wrap(text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if font.getlength(t) <= maxw or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

# A card whose text contains a newline is a LIST card: a cumulative reveal where each new item
# is appended BELOW the previous ones. The positioning never shifts when an item is added, so a
# list card is TOP-anchored, not centre-anchored: every card in the run
# starts its first line at the same y, and the block only grows downward. The anchor is placed so
# that the FULL list (LIST_LINES lines) ends up vertically centred, set LIST_LINES to the length
# of the longest card in the run, or the block drifts off centre.
# Lines are LEFT-aligned to each other, and the block as a whole is centred horizontally.
LIST_LINES = int(_cfg.get("list_lines", 0))
LIST_PREFIX = "list:"
# Where the FIRST line of the list sits.
#   "centred"  (default): the anchor is placed so the
#              FINISHED list, LIST_LINES lines, ends up vertically centred, so a short early
#              card floats high on the frame.
#   "caption": the first line sits exactly where a normal ONE-LINE card sits, and the list only
#              grows downward from there.
LIST_ANCHOR = _cfg.get("list_anchor", "centred")
# Where the LIST block is centred. Defaults to the caption centre; set it to put the list on top
# of the frame while the captions sit lower. Hashed into STYLE_DIR below like every other visual parameter.
LIST_CENTER_Y = int(_cfg.get("list_center_y", CENTER_Y))
# Bullet in front of every list line. "minus" draws the heavy-minus emoji SHAPE (Apple's ➖ is a
# rounded bar ~4.3:1) in the caption's own white + black stroke, because most fonts have no glyph
# for U+2796 and the flat dark-grey emoji vanishes on dark footage. "minus" is the
# DEFAULT for every list card; set list_bullet to "" or null in the job config to turn it off.
LIST_BULLET = _cfg.get("list_bullet", "minus") or None

# --- cache key -----------------------------------------------------------
# A caption clip's filename is a hash of its TEXT only, so the DIRECTORY has to carry every
# other thing that changes the pixels. `{fps}-{style}` is not enough: changing font, size or
# position would silently reuse every existing clip. STYLE_DIR appends a hash of every visual
# parameter.
import hashlib as _hl
_LEGACY = False
_VARIANT = [W, H, _FACE, SIZE, FILL, _UPPER, BLUR_PX, CENTER_Y, MAX_W, STYLE, STROKE_W, SHADOW_ALPHA, SHADOW_BLUR,
            SHADOW_DIST, SHADOW_ANGLE, PILL_BG, PILL_ALPHA, PILL_H, PILL_PAD_X, PILL_RADIUS,
            PILL_BASE_OFF, PILL_ONE_LINE, PILL_MIN_SIZE, LIST_LINES, LIST_ANCHOR,
            _cfg.get("list_widest")] + ([SHADOW_SPREAD] if SHADOW_SPREAD else []) \
           + ([LIST_CENTER_Y] if LIST_CENTER_Y != CENTER_Y else []) + ([LIST_BULLET, 'capmid'] if LIST_BULLET else [])
# Appended only when it differs from the default, so no shipped job re-renders its cache.
_VARIANT += ([PILL_SH_ALPHA, PILL_SH_BLUR, PILL_SH_DIST_R, PILL_SH_SPRD_R, PILL_SH_ANGLE]
             if (PILL_SH_ALPHA, PILL_SH_BLUR, PILL_SH_DIST_R, PILL_SH_SPRD_R, PILL_SH_ANGLE)
             != (0.50, 1.00, 0.083, 0.083, -45.0) else [])
STYLE_DIR = STYLE if _LEGACY else (
    STYLE + "-" + _hl.sha1(_json.dumps(_VARIANT, default=str).encode()).hexdigest()[:6])


def render(text, path, plate=None, shadow=None):
    if not FONT:
        _sys.exit(_FONT_HELP)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if _UPPER:
        text = text.upper().replace("LIST:", LIST_PREFIX, 1)
    # LIST mode is marked EXPLICITLY with a "list:" prefix, not inferred from newlines --
    # the first card of a cumulative run has only one item and therefore no newline, and
    # inferring it silently rendered that card centred while the rest were top-anchored.
    if text.startswith(LIST_PREFIX):
        return _render_list(text[len(LIST_PREFIX):], path, img)
    if STYLE == "pill":
        return _render_pill(text, path, img, plate, shadow)
    if text.strip():
        lines = wrap(text, _f, MAX_W)
        lh = int(SIZE * 1.18)
        total = lh * len(lines)
        y0 = CENTER_Y - total // 2

        if STYLE == "shadow":
            import math
            dx = SHADOW_DIST * math.cos(math.radians(SHADOW_ANGLE))
            dy = -SHADOW_DIST * math.sin(math.radians(SHADOW_ANGLE))
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ds = ImageDraw.Draw(sh)
            for i, ln in enumerate(lines):
                ds.text((W // 2 + dx, y0 + i * lh + dy), ln, font=_f,
                        fill=(0, 0, 0, int(round(255 * SHADOW_ALPHA))), anchor="ma",
                        stroke_width=SHADOW_SPREAD,
                        stroke_fill=(0, 0, 0, int(round(255 * SHADOW_ALPHA))))
            if BLUR_PX > 0:
                sh = sh.filter(ImageFilter.GaussianBlur(BLUR_PX))
            img.alpha_composite(sh)

        d = ImageDraw.Draw(img)
        # Per-SPEAKER border colour: a second voice can get a coloured border. `plate` is the same per-card colour
        # channel the pill uses (work/caption_plates.json, from the `speaker` tags), so the clip
        # cache key already carries it; on the border style it recolours the STROKE, nothing else.
        stroke_fill = (tuple(plate) + (255,))[:4] if (plate and STYLE == "border") else STROKE_FILL
        for i, ln in enumerate(lines):
            d.text((W // 2, y0 + i * lh), ln, font=_f, fill=FILL, anchor="ma",
                   stroke_width=(STROKE_W if STYLE == "border" else 0),
                   stroke_fill=stroke_fill)
    img.save(path)
    return path


def _render_pill(text, path, img, plate=None, shadow=None):
    """White text on a translucent grey rounded plate, centred on CENTER_Y. See PILL_* above.

    `pill_one_line` shrinks a card that would WRAP until it fits on one line (down to
    `pill_min_size`). Only long cards are
    affected, a normal 2-3 word card never reaches the check, so the film keeps one type size.
    """
    f, size = _f, SIZE
    pad, ph, rad, boff = PILL_PAD_X, PILL_H, PILL_RADIUS, PILL_BASE_OFF
    if PILL_ONE_LINE and len(wrap(text, f, MAX_W - 2 * pad)) > 1:
        for size in range(SIZE, PILL_MIN_SIZE - 1, -1):
            f = ImageFont.truetype(FONT, size)
            pad = round(size * 0.46)
            if f.getlength(text) + 2 * pad <= MAX_W:
                break
        rad, boff = round(size * 0.41), round(size * 0.30)
        ph = round(size * 1.83)
    globals()["_pill_f"], globals()["_pill_size"] = f, size
    return _pill_draw(text, path, img, f, pad, ph, rad, boff,
                      tuple(plate or PILL_BG), tuple(shadow) if shadow else None)


def _pill_draw(text, path, img, _f, PILL_PAD_X, PILL_H, PILL_RADIUS, PILL_BASE_OFF,
               PLATE, SHADOW=None):
    SIZE = _f.size
    lines = wrap(text, _f, MAX_W - 2 * PILL_PAD_X)
    lh = int(SIZE * 1.18)
    total_h = PILL_H + (len(lines) - 1) * lh
    top = CENTER_Y - total_h // 2
    pw = int(round(max(_f.getlength(ln) for ln in lines))) + 2 * PILL_PAD_X
    x0 = (W - pw) // 2

    plate = Image.new("RGBA", (pw * PILL_SS, total_h * PILL_SS), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        (0, 0, pw * PILL_SS - 1, total_h * PILL_SS - 1),
        radius=PILL_RADIUS * PILL_SS,
        fill=(*PLATE, int(round(255 * PILL_ALPHA))))
    img.alpha_composite(plate.resize((pw, total_h), Image.LANCZOS), (x0, top))

    base = top + PILL_H // 2 + PILL_BASE_OFF     # baseline, not top, see PILL_BASE_OFF

    # The coloured glow goes ON TOP of the plate and UNDER the glyphs, or the grey swallows it.
    if SHADOW:
        import math as _m
        from PIL import ImageFilter as _IF
        dist = PILL_SH_DIST_R * SIZE
        dx = dist * _m.cos(_m.radians(PILL_SH_ANGLE))
        dy = -dist * _m.sin(_m.radians(PILL_SH_ANGLE))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        col = (*SHADOW, int(round(255 * PILL_SH_ALPHA)))
        spread = int(round(PILL_SH_SPRD_R * SIZE))
        for i, ln in enumerate(lines):
            ds.text((W // 2 + dx, base + i * lh + dy), ln, font=_f, fill=col, anchor="ms",
                    stroke_width=spread, stroke_fill=col)
        sigma = PILL_SH_BLUR * 0.14 * SIZE
        if sigma > 0:
            sh = sh.filter(_IF.GaussianBlur(sigma))
        img.alpha_composite(sh)

    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text((W // 2, base + i * lh), ln, font=_f, fill=FILL, anchor="ms")
    img.save(path)
    return path


def _render_list(text, path, img):
    """Top-anchored, left-aligned cumulative list. See LIST_LINES above."""
    import math
    lines = [ln for ln in text.split("\n") if ln.strip()]
    lh = int(SIZE * 1.18)
    n_full = max(LIST_LINES, len(lines))
    if LIST_ANCHOR == "caption":
        y0 = LIST_CENTER_Y - lh // 2            # exactly where a one-line card sits
    else:
        y0 = LIST_CENTER_Y - (lh * n_full) // 2      # fixed for every card in the run
    x0 = (W - max(_f.getlength(ln) for ln in lines)) // 2   # block centred, lines left-aligned
    # NOTE: x0 uses THIS card's widest line, so a later, wider item would shift the block.
    # LIST_WIDEST pins it to the run's widest line instead.
    widest = _cfg.get("list_widest")
    if widest:
        x0 = (W - _f.getlength(str(widest))) // 2
    # bullet: a rounded bar the width of ~0.75 em, drawn like a glyph (stroke first, then fill)
    b_w, b_h, b_gap = int(SIZE * 0.75), int(SIZE * 0.18), int(SIZE * 0.35)
    if LIST_BULLET:
        x0 -= (b_w + b_gap) // 2                  # keep the whole block (bullet + text) centred
    # The bar sits on the vertical centre of the LINE OF TEXT: midway between the cap top and the
    # baseline, read off the font itself ("H" bbox with the same "la" anchor the text uses).
    # Descenders are ignored on purpose; a line with a "g" must not drop its bar.
    _hb = _f.getbbox("H", anchor="la")
    _cap_mid = (_hb[1] + _hb[3]) / 2
    def _bullet(dr, x, y_line, stroke):
        cy = int(round(y_line + _cap_mid))
        box = (x - stroke, cy - b_h // 2 - stroke, x + b_w + stroke, cy + b_h // 2 + stroke)
        dr.rounded_rectangle(box, radius=b_h // 2 + stroke, fill=STROKE_FILL if stroke else FILL)
    tx = x0 + (b_w + b_gap if LIST_BULLET else 0)

    if STYLE == "shadow":
        dx = SHADOW_DIST * math.cos(math.radians(SHADOW_ANGLE))
        dy = -SHADOW_DIST * math.sin(math.radians(SHADOW_ANGLE))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        for i, ln in enumerate(lines):
            ds.text((tx + dx, y0 + i * lh + dy), ln, font=_f,
                    fill=(0, 0, 0, int(round(255 * SHADOW_ALPHA))), anchor="la",
                    stroke_width=SHADOW_SPREAD,
                    stroke_fill=(0, 0, 0, int(round(255 * SHADOW_ALPHA))))
        if BLUR_PX > 0:
            sh = sh.filter(ImageFilter.GaussianBlur(BLUR_PX))
        img.alpha_composite(sh)

    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        if LIST_BULLET:
            if STYLE == "border":
                _bullet(d, x0, y0 + i * lh, STROKE_W)
            _bullet(d, x0, y0 + i * lh, 0)
        d.text((tx, y0 + i * lh), ln, font=_f, fill=FILL, anchor="la",
               stroke_width=(STROKE_W if STYLE == "border" else 0), stroke_fill=STROKE_FILL)
    img.save(path)
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Render one caption card to a transparent PNG.")
    ap.add_argument("text", nargs="?", default="sample caption")
    ap.add_argument("out", nargs="?", default="caption-test.png")
    a = ap.parse_args()
    print(render(a.text, a.out))
