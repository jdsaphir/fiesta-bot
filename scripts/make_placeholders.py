"""Generate five placeholder medal PNGs so the bot can run end-to-end before
the creative team delivers final assets.

Usage: python scripts/make_placeholders.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "assets" / "medals"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 512
COLORS = [
    (220, 60, 60),    # red
    (240, 170, 40),   # orange
    (60, 160, 90),    # green
    (60, 110, 200),   # blue
    (160, 70, 180),   # purple
]

try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", SIZE // 3)
except OSError:
    font = ImageFont.load_default()


def make(i: int, color: tuple[int, int, int]) -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((16, 16, SIZE - 16, SIZE - 16), fill=color, outline=(40, 40, 40), width=8)
    label = str(i)
    try:
        bbox = d.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = d.textsize(label, font=font)
    d.text(((SIZE - tw) / 2, (SIZE - th) / 2 - 12), label, fill="white", font=font)
    img.save(OUT / f"medal_{i}.png", "PNG")


for i, c in enumerate(COLORS, start=1):
    make(i, c)
print(f"Wrote 5 placeholder medals to {OUT}")
