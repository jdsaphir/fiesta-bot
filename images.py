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
    """Pin medals onto a shirt/bag template. Positioning is a first pass —
    once the creative team ships the template, tweak target_w and (x, y)."""
    template = Image.open(template_path).convert("RGBA")
    medals = [Image.open(p).convert("RGBA") for p in medal_paths]

    tw, th = template.size
    target_w = tw // 8
    sized = []
    for m in medals:
        scale = target_w / m.width
        sized.append(m.resize((target_w, max(1, int(m.height * scale)))))

    canvas = template.copy()
    n = len(sized)
    spacing = tw // (n + 1)
    y = th // 3  # rough chest line; adjust once the template arrives
    for i, m in enumerate(sized):
        x = spacing * (i + 1) - m.width // 2
        canvas.paste(m, (x, y - m.height // 2), m)

    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    buf.seek(0)
    return buf
