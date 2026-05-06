import io
from pathlib import Path
from PIL import Image

# Discord displays embed images well under 1200 px wide.
# We pre-downscale the template (which can be 3000+ px from the creative team)
# to this width once, save it to disk, and keep it in memory for the session.
MAX_TEMPLATE_W = 1200

# Per-medal cap in the collage (5 medals → ~1024 px wide canvas).
MAX_MEDAL_W = 200

# Background fill used when saving the wear output as JPEG.
# Matches Discord's dark-mode channel background so transparent shirt edges
# blend in rather than showing as a jarring white block.
DISCORD_DARK_BG = (49, 51, 56, 255)

# In-memory cache: key (str) -> Image (RGBA).
# Keyed by file path for originals, and "path@width" for pre-resized copies.
_cache: dict[str, Image.Image] = {}


def _small_path(template_path: str) -> str:
    p = Path(template_path)
    return str(p.with_stem(p.stem + "_small"))


def _get(path: str) -> Image.Image:
    """Return a cached image, or load it fresh and cache it."""
    if path not in _cache:
        _cache[path] = Image.open(path).convert("RGBA")
    return _cache[path]


def _disk_cache_path(path: str, width: int) -> Path:
    """Sibling file that stores a pre-resized copy, e.g. medal_1_w133.png."""
    p = Path(path)
    return p.with_stem(f"{p.stem}_w{width}")


def _get_sized(path: str, width: int) -> Image.Image:
    """Return a cached resized copy, loading from the on-disk cache if available,
    otherwise resizing from the original and saving to disk for next time."""
    key = f"{path}@{width}"
    if key not in _cache:
        dp = _disk_cache_path(path, width)
        if dp.exists():
            # Fast path: just read the small pre-saved file — no CPU resizing.
            _cache[key] = Image.open(dp).convert("RGBA")
        else:
            # First-ever run: resize and save so future startups are fast.
            src   = _get(path)
            scale = width / src.width
            img   = src.resize((width, max(1, int(src.height * scale))), Image.LANCZOS)
            img.save(dp, "PNG", compress_level=1)
            _cache[key] = img
    return _cache[key]


def preload(template_path: str, medal_paths: list[str]) -> None:
    """Load and cache all assets.  On first run this generates small on-disk
    copies of the template and medals; subsequent runs just read those small
    files, which is fast and keeps the event loop responsive during startup."""
    sp = _small_path(template_path)

    if sp not in _cache:
        if not Path(sp).exists():
            # First-ever run: downscale and save to disk.
            img = _get(template_path)
            if img.width > MAX_TEMPLATE_W:
                scale = MAX_TEMPLATE_W / img.width
                img = img.resize(
                    (MAX_TEMPLATE_W, max(1, int(img.height * scale))), Image.LANCZOS
                )
            img.save(sp, "PNG", compress_level=1)
        _cache[sp] = Image.open(sp).convert("RGBA")

    # Pre-load pre-sized medal variants into memory.
    wear_w = MAX_TEMPLATE_W // 9
    for p in medal_paths:
        _get_sized(p, wear_w)
        _get_sized(p, MAX_MEDAL_W)


def collage(medal_paths: list[str]) -> io.BytesIO:
    if not medal_paths:
        raise ValueError("no medals to render")

    medals = [_get_sized(p, MAX_MEDAL_W) for p in medal_paths]

    # Normalize all to first medal's size.
    w, h = medals[0].size
    medals = [m if m.size == (w, h) else m.resize((w, h)) for m in medals]

    gap = max(4, w // 32)
    canvas_w = w * len(medals) + gap * (len(medals) - 1)
    canvas = Image.new("RGBA", (canvas_w, h), (0, 0, 0, 0))
    for i, m in enumerate(medals):
        canvas.paste(m, (i * (w + gap), 0), m)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", compress_level=1)
    buf.seek(0)
    return buf


def wear(medal_paths: list[str], template_path: str) -> io.BytesIO:
    """Pin medals onto the jersey template in a chest-level row."""
    # Use the pre-downscaled template; copy so we can draw on it without
    # mutating the cached version.
    sp       = _small_path(template_path)
    template = _get(sp).copy()
    tw, th   = template.size

    target_w = tw // 9
    sized    = [_get_sized(p, target_w) for p in medal_paths]
    mw = sized[0].width
    n  = len(sized)

    # Body bounds as fractions of template width
    # (original measurements: 709–2713 on a 3426 px canvas).
    body_left  = int(tw * 0.207)
    body_right = int(tw * 0.792)
    inner      = int(tw * 0.044)
    usable     = (body_right - inner) - (body_left + inner)
    spacing    = usable // (n - 1) if n > 1 else 0
    y          = int(th * 0.22)

    for i, m in enumerate(sized):
        cx = body_left + inner + spacing * i if n > 1 else tw // 2
        x  = cx - mw // 2
        template.paste(m, (x, y), m)

    # Save as JPEG (4× faster encode, 5× smaller file vs PNG) with a Discord
    # dark-mode background fill so transparent shirt edges blend in.
    bg     = Image.new("RGBA", (tw, th), DISCORD_DARK_BG)
    result = Image.alpha_composite(bg, template).convert("RGB")
    buf    = io.BytesIO()
    result.save(buf, "JPEG", quality=85)
    buf.seek(0)
    return buf
