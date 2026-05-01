import io
from PIL import Image


def collage(medal_paths: list[str]) -> io.BytesIO:
    if not medal_paths:
        raise ValueError("no medals to render")
    medals = [Image.open(p).convert("RGBA") for p in medal_paths]

    # Creative team will deliver same-sized PNGs; if not, normalize to the first.
    w, h = medals[0].size
    medals = [m if m.size == (w, h) else m.resize((w, h)) for m in medals]

    gap = max(8, w // 32)
    canvas_w = w * len(medals) + gap * (len(medals) - 1)
    canvas = Image.new("RGBA", (canvas_w, h), (0, 0, 0, 0))
    for i, m in enumerate(medals):
        canvas.paste(m, (i * (w + gap), 0), m)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf


def wear(medal_paths: list[str], template_path: str) -> io.BytesIO:
    """Pin medals onto the jersey template in a chest-level row."""
    template = Image.open(template_path).convert("RGBA")
    medals = [Image.open(p).convert("RGBA") for p in medal_paths]

    tw, th = template.size

    # Scale each medal to 1/8 of the template width, preserving aspect ratio.
    target_w = tw // 8
    sized = []
    for m in medals:
        scale = target_w / m.width
        sized.append(m.resize((target_w, max(1, int(m.height * scale)))))

    mw = sized[0].width
    n = len(sized)

    # Spread medals between 12% margins so they stay within the shirt body.
    # With a single medal, centre it horizontally.
    margin = int(tw * 0.12)
    usable_w = tw - 2 * margin
    spacing = usable_w // (n - 1) if n > 1 else 0
    y = int(th * 0.16)  # upper chest — ribbon tops sit just below the collar

    canvas = template.copy()
    for i, m in enumerate(sized):
        x = margin + spacing * i - mw // 2 if n > 1 else (tw - mw) // 2
        canvas.paste(m, (x, y), m)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf
