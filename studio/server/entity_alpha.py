"""Punch seamless studio backdrops to PNG alpha for cast and prop cutouts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path


def _dist2(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def punch_light_background_to_alpha(
    path: Path,
    *,
    color_tolerance: int = 38,
    min_corner_hits: int = 5,
    min_punch_ratio: float = 0.06,
    max_punch_ratio: float = 0.92,
) -> bool:
    """
    Key the backdrop from border/corner samples (not absolute white).

    Light studio plates are often mid light-gray (~180–220), which absolute
    white thresholds miss. We pick the dominant edge color and flood-fill similar
    pixels from the border to alpha=0, then rewrite as RGBA PNG.
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
    samples: list[tuple[int, int, int]] = []
    step = max(1, min(w, h) // 40)
    for x in range(0, w, step):
        for y in (0, h - 1):
            r, g, b, a = px[x, y]
            if a >= 16:
                samples.append((r, g, b))
    for y in range(0, h, step):
        for x in (0, w - 1):
            r, g, b, a = px[x, y]
            if a >= 16:
                samples.append((r, g, b))

    if len(samples) < 8:
        return False

    # Quantize to stabilize the backdrop key.
    bucket = Counter(((r // 8) * 8, (g // 8) * 8, (b // 8) * 8) for r, g, b in samples)
    key = bucket.most_common(1)[0][0]
    # Reject keys that look like clothing/hair (high chroma or too dark).
    chroma = max(key) - min(key)
    luma = sum(key) / 3
    if luma < 95 or chroma > 48:
        return False

    tol2 = color_tolerance * color_tolerance

    def _is_bg(rgba: tuple[int, int, int, int]) -> bool:
        r, g, b, a = rgba
        if a < 16:
            return True
        if _dist2((r, g, b), key) > tol2:
            return False
        # Keep near-neutral relative to key (avoid eating colored garment edges).
        if abs((max(r, g, b) - min(r, g, b)) - chroma) > 36:
            return False
        return True

    edge_hits = 0
    for x in range(0, w, max(1, w // 16)):
        if _is_bg(px[x, 0]) or _is_bg(px[x, h - 1]):
            edge_hits += 1
    for y in range(0, h, max(1, h // 16)):
        if _is_bg(px[0, y]) or _is_bg(px[w - 1, y]):
            edge_hits += 1
    if edge_hits < min_corner_hits:
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
        if not _is_bg(rgba):
            continue
        px[x, y] = (rgba[0], rgba[1], rgba[2], 0)
        punched += 1
        stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

    ratio = punched / float(w * h)
    if ratio < min_punch_ratio or ratio > max_punch_ratio:
        return False

    im.save(p, format="PNG")
    return True
