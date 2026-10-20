"""Punch seamless studio backdrops to PNG alpha for cast and prop cutouts.

Handles:
- light-gray / off-white plates (not only #FFFFFF)
- enclosed holes (between legs, rope gaps) the border flood cannot reach
- white fringe / halo on hair and cloth edges (despill + soft matte)
- repair of already-keyed PNGs that still have plate leftovers
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path


def _dist2(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def _estimate_key_from_transparent_neighbors(px, w: int, h: int) -> tuple[int, int, int] | None:
    """When the plate is already punched, recover key color from RGB left under alpha=0."""
    samples: list[tuple[int, int, int]] = []
    step = max(1, min(w, h) // 50)
    for y in range(0, h, step):
        for x in range(0, w, step):
            r, g, b, a = px[x, y]
            if a >= 16:
                continue
            # Prefer near-white / light-gray leftovers stored in premultiplied-ish RGB.
            if (r + g + b) / 3 < 140:
                continue
            if max(r, g, b) - min(r, g, b) > 40:
                continue
            samples.append((r, g, b))
    if len(samples) < 12:
        # Fall back: opaque bright fringe pixels next to clear.
        for y in range(1, h - 1, step):
            for x in range(1, w - 1, step):
                r, g, b, a = px[x, y]
                if a < 16 or (r + g + b) / 3 < 200:
                    continue
                if max(r, g, b) - min(r, g, b) > 36:
                    continue
                if any(px[x + dx, y + dy][3] < 16 for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                    samples.append((r, g, b))
    if len(samples) < 8:
        return (255, 255, 255)
    bucket = Counter(((r // 8) * 8, (g // 8) * 8, (b // 8) * 8) for r, g, b in samples)
    return bucket.most_common(1)[0][0]


def _despill_fringe(px, w: int, h: int, key: tuple[int, int, int], *, fringe_tolerance: int) -> None:
    key_r, key_g, key_b = key
    key_luma = (key_r + key_g + key_b) / 3.0

    fringe: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 16:
                continue
            near_clear = False
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if nx < 0 or ny < 0 or nx >= w or ny >= h:
                    near_clear = True
                    break
                if px[nx, ny][3] < 16:
                    near_clear = True
                    break
            if near_clear:
                fringe.append((x, y))

    for x, y in fringe:
        r, g, b, a = px[x, y]
        d = (_dist2((r, g, b), key)) ** 0.5
        if d <= fringe_tolerance:
            t = 1.0 - (d / float(max(1, fringe_tolerance)))
            new_a = int(a * (1.0 - 0.92 * t))
            spill = t * 0.85
            r2 = _clamp(int(r - spill * (key_r - key_luma)))
            g2 = _clamp(int(g - spill * (key_g - key_luma)))
            b2 = _clamp(int(b - spill * (key_b - key_luma)))
            boost = max(0.0, (r + g + b) / 3.0 - key_luma + 8) / 40.0
            if boost > 0:
                r2 = _clamp(int(r2 - boost * 22 * t))
                g2 = _clamp(int(g2 - boost * 22 * t))
                b2 = _clamp(int(b2 - boost * 22 * t))
            px[x, y] = (r2, g2, b2, max(0, min(255, new_a)))
        else:
            # Subject edge with light spill from white plate.
            spill_w = max(0, min(r, g, b) - 160) / 95.0
            if spill_w > 0:
                r2 = _clamp(int(r - spill_w * 28))
                g2 = _clamp(int(g - spill_w * 28))
                b2 = _clamp(int(b - spill_w * 28))
                px[x, y] = (r2, g2, b2, max(0, min(255, int(a * 0.94))))
            else:
                px[x, y] = (r, g, b, max(0, min(255, int(a * 0.96))))

    # Second ring for hair wisps.
    fringe2: list[tuple[int, int]] = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            r, g, b, a = px[x, y]
            if a < 32:
                continue
            clear_n = sum(
                1
                for nx, ny in (
                    (x - 2, y),
                    (x + 2, y),
                    (x, y - 2),
                    (x, y + 2),
                    (x - 1, y),
                    (x + 1, y),
                    (x, y - 1),
                    (x, y + 1),
                )
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] < 16
            )
            if clear_n >= 2 and _dist2((r, g, b), key) <= (fringe_tolerance + 14) ** 2:
                fringe2.append((x, y))
    for x, y in fringe2:
        r, g, b, a = px[x, y]
        d = (_dist2((r, g, b), key)) ** 0.5
        t = max(0.0, 1.0 - d / float(fringe_tolerance + 14))
        if t <= 0:
            continue
        new_a = int(a * (1.0 - 0.6 * t))
        spill = 0.6 * t
        r2 = _clamp(int(r - spill * (key_r - key_luma)))
        g2 = _clamp(int(g - spill * (key_g - key_luma)))
        b2 = _clamp(int(b - spill * (key_b - key_luma)))
        # Extra white-halo shrink on bright wisps.
        if (r + g + b) / 3 > 210:
            new_a = int(new_a * (1.0 - 0.35 * t))
        px[x, y] = (r2, g2, b2, max(0, min(255, new_a)))


def _punch_bg_islands(
    px,
    w: int,
    h: int,
    key: tuple[int, int, int],
    *,
    tol: int,
    chroma: int,
    key_luma: float,
) -> int:
    """Punch enclosed plate islands (between legs, rope gaps)."""

    def _is_bg(rgba: tuple[int, int, int, int]) -> bool:
        r, g, b, a = rgba
        if a < 16:
            return True
        if _dist2((r, g, b), key) > tol * tol:
            return False
        if abs((max(r, g, b) - min(r, g, b)) - chroma) > 42:
            return False
        if max(r, g, b) - min(r, g, b) > max(chroma + 30, 44) and abs((r + g + b) / 3 - key_luma) > 20:
            return False
        return True

    punched = 0
    visited = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if visited[i]:
                continue
            rgba = px[x, y]
            if rgba[3] < 16 or not _is_bg(rgba):
                visited[i] = 1
                continue
            stack = [(x, y)]
            island: list[tuple[int, int]] = []
            luma_sum = 0.0
            chroma_sum = 0.0
            while stack:
                cx, cy = stack.pop()
                if cx < 0 or cy < 0 or cx >= w or cy >= h:
                    continue
                ci = cy * w + cx
                if visited[ci]:
                    continue
                visited[ci] = 1
                cr, cg, cb, ca = px[cx, cy]
                if ca < 16 or not _is_bg((cr, cg, cb, ca)):
                    continue
                island.append((cx, cy))
                luma_sum += (cr + cg + cb) / 3.0
                chroma_sum += max(cr, cg, cb) - min(cr, cg, cb)
                stack.extend(((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)))
            if not island:
                continue
            mean_luma = luma_sum / len(island)
            mean_chroma = chroma_sum / len(island)
            if mean_luma < key_luma - 30 or mean_chroma > max(chroma + 32, 44):
                continue
            if len(island) > int(w * h * 0.35):
                continue
            for cx, cy in island:
                cr, cg, cb, _ca = px[cx, cy]
                px[cx, cy] = (cr, cg, cb, 0)
                punched += 1
    return punched


def punch_light_background_to_alpha(
    path: Path,
    *,
    color_tolerance: int = 42,
    hole_tolerance: int = 56,
    fringe_tolerance: int = 62,
    min_corner_hits: int = 5,
    min_punch_ratio: float = 0.04,
    max_punch_ratio: float = 0.95,
) -> bool:
    """
    Key the backdrop from border/corner samples (not absolute white).

    Also repairs already-keyed cutouts that still have enclosed white holes and
    white fringe on hair / cloth edges.
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
    clear_n = 0
    step_a = max(1, min(w, h) // 80)
    for y in range(0, h, step_a):
        for x in range(0, w, step_a):
            if px[x, y][3] < 16:
                clear_n += 1
    already_keyed = clear_n > 20

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

    key: tuple[int, int, int]
    chroma: int
    if already_keyed or len(samples) < 8:
        est = _estimate_key_from_transparent_neighbors(px, w, h)
        key = est or (255, 255, 255)
        chroma = max(key) - min(key)
    else:
        bucket = Counter(((r // 8) * 8, (g // 8) * 8, (b // 8) * 8) for r, g, b in samples)
        key = bucket.most_common(1)[0][0]
        chroma = max(key) - min(key)
        luma = sum(key) / 3
        if luma < 95 or chroma > 48:
            return False

    key_luma = sum(key) / 3.0

    def _is_bg(rgba: tuple[int, int, int, int], *, tol: int) -> bool:
        r, g, b, a = rgba
        if a < 16:
            return True
        if _dist2((r, g, b), key) > tol * tol:
            return False
        if abs((max(r, g, b) - min(r, g, b)) - chroma) > 40:
            return False
        if max(r, g, b) - min(r, g, b) > max(chroma + 28, 36) and abs((r + g + b) / 3 - key_luma) > 18:
            return False
        return True

    punched = 0
    if not already_keyed:
        edge_hits = 0
        for x in range(0, w, max(1, w // 16)):
            if _is_bg(px[x, 0], tol=color_tolerance) or _is_bg(px[x, h - 1], tol=color_tolerance):
                edge_hits += 1
        for y in range(0, h, max(1, h // 16)):
            if _is_bg(px[0, y], tol=color_tolerance) or _is_bg(px[w - 1, y], tol=color_tolerance):
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
        while stack:
            x, y = stack.pop()
            if x < 0 or y < 0 or x >= w or y >= h:
                continue
            i = y * w + x
            if visited[i]:
                continue
            visited[i] = 1
            rgba = px[x, y]
            if not _is_bg(rgba, tol=color_tolerance):
                continue
            if rgba[3] >= 16:
                px[x, y] = (rgba[0], rgba[1], rgba[2], 0)
                punched += 1
            stack.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

        ratio = punched / float(w * h)
        if ratio < min_punch_ratio or ratio > max_punch_ratio:
            return False

    # Enclosed holes (and leftover plate on already-keyed images).
    punched += _punch_bg_islands(
        px,
        w,
        h,
        key,
        tol=hole_tolerance if already_keyed else max(hole_tolerance, color_tolerance + 8),
        chroma=chroma,
        key_luma=key_luma,
    )

    _despill_fringe(px, w, h, key, fringe_tolerance=fringe_tolerance)

    im.save(p, format="PNG")
    return True
