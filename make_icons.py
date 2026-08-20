"""Generate the home-screen icons, in the same house style as the other apps.

Dark tile, a small mark up top, the name in a serif wordmark in the page's own
accent colour, a hairline rule, then what the thing does in spaced-out sans.
Run once and commit the PNGs — the workflow copies them rather than rebuilding
them, so CI never has to care which fonts a runner happens to have.

    python3 make_icons.py
"""

from PIL import Image, ImageDraw, ImageFont

BG = "#16161A"        # the page's dark background
ACCENT = "#E08560"    # the page's dark-mode accent
RULE = "#3A3A42"
SUB = "#8E9AAB"

SERIF = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
SANS = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def rounded_tile(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.225), fill=BG)
    return img, d


def centred(d, y, text, font, fill, tracking=0):
    """Draw text centred on the tile, optionally letter-spaced."""
    if not tracking:
        w = d.textlength(text, font=font)
        d.text(((d.im.size[0] - w) / 2, y), text, font=font, fill=fill)
        return
    widths = [d.textlength(c, font=font) for c in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (d.im.size[0] - total) / 2
    for c, w in zip(text, widths):
        d.text((x, y), c, font=font, fill=fill)
        x += w + tracking


def sunrise(d, size):
    """A half-risen sun on a horizon — the mark, in the accent colour."""
    cx, cy = size / 2, size * 0.315
    r = size * 0.072
    lw = max(2, int(size * 0.016))
    d.arc([cx - r, cy - r, cx + r, cy + r], start=180, end=360, fill=ACCENT, width=lw)
    d.line([cx - r * 2.05, cy, cx + r * 2.05, cy], fill=ACCENT, width=lw)
    for frac in (-0.72, -0.36, 0.0, 0.36, 0.72):
        ang = frac * 1.05
        import math
        sx, sy = cx + math.sin(ang) * r * 1.5, cy - math.cos(ang) * r * 1.5
        ex, ey = cx + math.sin(ang) * r * 1.95, cy - math.cos(ang) * r * 1.95
        d.line([sx, sy, ex, ey], fill=ACCENT, width=lw)


def build(size):
    img, d = rounded_tile(size)
    sunrise(d, size)

    wordmark = ImageFont.truetype(SERIF, int(size * 0.155))
    subtitle = ImageFont.truetype(SANS, int(size * 0.058))

    centred(d, size * 0.40, "MORNING", wordmark, ACCENT)

    ry = size * 0.605
    d.line([size * 0.34, ry, size * 0.66, ry], fill=RULE, width=max(1, int(size * 0.006)))

    centred(d, size * 0.655, "BRIEF", subtitle, SUB, tracking=size * 0.028)
    return img


if __name__ == "__main__":
    for size, name in [(512, "icon-512.png"), (192, "icon-192.png"), (180, "apple-touch-icon.png")]:
        build(size).save(name)
        print(f"wrote {name} ({size}x{size})")
