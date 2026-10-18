"""Punch near-white / light-gray studio backdrops to PNG alpha for cast & prop cutouts."""

from __future__ import annotations

from pathlib import Path


def punch_light_background_to_alpha(
    path: Path,
    *,
    threshold: int = 232,
    min_corner_hits: int = 3,
) -> bool:
    """
    If most image corners are light (SceneMixer-style seamless plate), flood-fill
    contiguous light pixels from the border to alpha=0 and rewrite as RGBA PNG.

    Returns True when the file was rewritten. Soft-fails (False) when Pillow is
    missing or the plate does not look like a light cutout backdrop.
    """
    try:
        from PIL import Image
    except ImportError:
        return False

    p = Path(path)
    if not p.is_file():
        return False
    try:
        im = Image.open(p).convert("RGBA")
    except Exception:
        return False

    w, h = im.size
    if w < 8 or h < 8:
        return False

    px = im.load()
    corners = [
        (0, 0),
        (w - 1, 0),
        (0, h - 1),
        (w - 1, h - 1),
        (w // 2, 0),
        (w // 2, h - 1),
        (0, h // 2),
        (w - 1, h // 2),
    ]

    def _is_light(rgb: tuple[int, int, int, int]) -> bool:
        r, g, b, a = rgb
        if a < 16:
            return True
        if min(r, g, b) < threshold - 40:
            return False
        # Near-white or soft studio gray (low chroma).
        if max(r, g, b) - min(r, g, b) > 28:
            return False
        return (r + g + b) / 3 >= threshold

    hits = sum(1 for xy in corners if _is_light(px[xy[0], xy[1]]))
    if hits < min_corner_hits:
        return False

    visited = bytearray(w * h)
    stack: list[tuple[int, int]] = []
    for x in range(w):
        stack.append((x, 0))
        stack.append((x, h - 1))
    for y in range(h):
        stack.append((0, y))
        stack.append((w - 1, y))

    punched = 0
    while stack:
        x, y = stack.pop()
        if x < 0 or y < 0 or x >= w or y >= h:
            continue
        i = y * w + x
        if visited[i]:
            continue
        visited[i] = 1
        rgba = px[x, y]
        if not _is_light(rgba):
            continue
        px[x, y] = (rgba[0], rgba[1], rgba[2], 0)
        punched += 1
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    # Require a meaningful backdrop area so we don't nuke a full-bleed plate.
    if punched < (w * h) * 0.08:
        return False

    im.save(p, format="PNG")
    return True
