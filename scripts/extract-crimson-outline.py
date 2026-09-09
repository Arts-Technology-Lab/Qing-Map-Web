#!/usr/bin/env python3
"""
Build Handi overlay as ONE continuous closed loop that:
  - follows the eighteen-provinces rim (gaps filled)
  - includes Hainan inside the loop
  - encloses Taiwan inside the loop

Method:
  1) Close mainland crimson strokes and flood-fill the Handi interior
  2) Paint Taiwan + Hainan enclosures into the same mask
  3) Trace the outer boundary of the union → a single ring
"""

from __future__ import annotations

import colorsys
import json
import math
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "overlays" / "source" / "handi-outline.png"
FULL_SRC = Path(
    "/Users/cwy1013/Library/CloudStorage/OneDrive-TheUniversityofHongKong-Connect/"
    "HKU/2026-2027 Sem 1/234MB JPG File_Super Resolution_18438x10516px_DSC3891-Edit-Handi.jpg.png"
)
OUT = ROOT / "data" / "overlays" / "handi-shibasheng.json"
PREVIEW = ROOT / "assets" / "overlays" / "source" / "debug-stitched-preview.png"

Image.MAX_IMAGE_PIXELS = None

# Island enclosure centers/radii in normalized image space (used as fallbacks
# and to expand detected stroke bboxes).
TAIWAN = {"center": (0.755, 0.735), "radii": (0.022, 0.042)}
HAINAN = {"center": (0.500, 0.835), "radii": (0.032, 0.026)}


def is_crimson(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 128:
        return False
    if r >= 170 and g <= 110 and b <= 110 and (r - max(g, b)) >= 55:
        return True
    hv, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (hv <= 0.045 or hv >= 0.955) and s >= 0.42 and v >= 0.42 and r >= 140


def connected_components(bp, w: int, h: int, min_size: int = 40):
    seen = [[False] * w for _ in range(h)]
    comps: list[list[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if bp[x, y] < 128 or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and not seen[ny][nx]
                            and bp[nx, ny] >= 128
                        ):
                            seen[ny][nx] = True
                            stack.append((nx, ny))
            if len(cells) >= min_size:
                comps.append(cells)
    return comps


def centroid(cells: list[tuple[int, int]]) -> tuple[float, float]:
    return (
        sum(c[0] for c in cells) / len(cells),
        sum(c[1] for c in cells) / len(cells),
    )


def flood_from(barrier, start: tuple[int, int], w: int, h: int):
    bp = barrier.load()
    sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h) or bp[sx, sy] >= 128:
        return None, 0
    vis = [[False] * w for _ in range(h)]
    q: deque[tuple[int, int]] = deque([start])
    vis[sy][sx] = True
    n = 0
    while q:
        x, y = q.popleft()
        n += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not vis[ny][nx] and bp[nx, ny] < 128:
                vis[ny][nx] = True
                q.append((nx, ny))
    return vis, n


def rdp(points: list[tuple[float, float]], epsilon: float):
    if len(points) < 3:
        return points[:]
    start, end = points[0], points[-1]
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    denom = dx * dx + dy * dy
    max_d = -1.0
    idx = 0
    for i in range(1, len(points) - 1):
        px, py = points[i]
        if denom == 0:
            d = math.hypot(px - sx, py - sy)
        else:
            t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / denom))
            d = math.hypot(px - (sx + t * dx), py - (sy + t * dy))
        if d > max_d:
            max_d = d
            idx = i
    if max_d > epsilon:
        return rdp(points[: idx + 1], epsilon)[:-1] + rdp(points[idx:], epsilon)
    return [start, end]


def order_boundary(edge: list[tuple[int, int]]) -> list[tuple[int, int]]:
    rem = set(edge)
    start = min(rem, key=lambda p: (p[1], p[0]))
    path = [start]
    rem.remove(start)
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    guard = len(edge) * 2 + 10
    while rem and len(path) < guard:
        cx, cy = path[-1]
        found = None
        for dx, dy in dirs:
            n = (cx + dx, cy + dy)
            if n in rem:
                found = n
                break
        if found is None:
            found = min(rem, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
            if (found[0] - cx) ** 2 + (found[1] - cy) ** 2 > 25:
                break
        path.append(found)
        rem.remove(found)
    return path


def to_norm(pts: list[tuple[float, float]], w: int, h: int):
    ring = [
        {
            "x": round(max(0.0, min(1.0, x / max(w - 1, 1))), 5),
            "y": round(max(0.0, min(1.0, y / max(h - 1, 1))), 5),
        }
        for x, y in pts
    ]
    if ring and (ring[0]["x"] != ring[-1]["x"] or ring[0]["y"] != ring[-1]["y"]):
        ring.append({"x": ring[0]["x"], "y": ring[0]["y"]})
    return ring


def load_working_image() -> Image.Image:
    if SRC.exists():
        img = Image.open(SRC).convert("RGBA")
        if img.size[0] >= 2048:
            print(f"Using existing source {img.size[0]}×{img.size[1]}")
            return img
    if FULL_SRC.exists():
        print("Resampling full Handi → 3072…")
        full = Image.open(FULL_SRC).convert("RGBA")
        tw = 3072
        th = int(round(full.size[1] * tw / full.size[0]))
        img = full.resize((tw, th), Image.Resampling.LANCZOS)
        img.save(SRC, optimize=True)
        return img
    if not SRC.exists():
        raise FileNotFoundError(SRC)
    return Image.open(SRC).convert("RGBA")


def paint_ellipse(draw: ImageDraw.ImageDraw, spec: dict, w: int, h: int, pts=None):
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        rx = max((max(xs) - min(xs)) / 2 * 1.5, spec["radii"][0] * (w - 1))
        ry = max((max(ys) - min(ys)) / 2 * 1.5, spec["radii"][1] * (h - 1))
        if spec["radii"][1] > spec["radii"][0] and ry < rx * 1.25:
            ry = rx * 1.45
    else:
        cx = spec["center"][0] * (w - 1)
        cy = spec["center"][1] * (h - 1)
        rx = spec["radii"][0] * (w - 1)
        ry = spec["radii"][1] * (h - 1)
    bbox = [cx - rx, cy - ry, cx + rx, cy + ry]
    draw.ellipse(bbox, fill=255)
    return cx, cy, rx, ry


def paint_bridge(
    draw: ImageDraw.ImageDraw,
    interior,
    w: int,
    h: int,
    target: tuple[float, float],
    width: float,
):
    """Thick line from nearest mainland-interior pixel to an island center."""
    tx, ty = target
    best = None
    best_d = 1e18
    # subsample search for speed
    step = max(2, min(w, h) // 400)
    for y in range(0, h, step):
        row = interior[y]
        for x in range(0, w, step):
            if not row[x]:
                continue
            d = (x - tx) ** 2 + (y - ty) ** 2
            if d < best_d:
                best_d = d
                best = (x, y)
    if best is None:
        return
    draw.line([best, (tx, ty)], fill=255, width=max(3, int(width)))


def main() -> int:
    img = load_working_image()
    w, h = img.size
    pixels = img.load()

    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if is_crimson(r, g, b, a):
                mp[x, y] = 255

    comps = connected_components(mask.load(), w, h, min_size=30)
    mainland_mask = Image.new("L", (w, h), 0)
    mmp = mainland_mask.load()
    taiwan_pts: list[tuple[int, int]] = []
    hainan_pts: list[tuple[int, int]] = []

    for cells in comps:
        cx, cy = centroid(cells)
        nx, ny = cx / (w - 1), cy / (h - 1)
        xs = (max(c[0] for c in cells) - min(c[0] for c in cells)) / (w - 1)
        ys = (max(c[1] for c in cells) - min(c[1] for c in cells)) / (h - 1)
        span = max(xs, ys)
        if nx > 0.70 and 0.60 < ny < 0.88 and span < 0.14:
            taiwan_pts.extend(cells)
        elif 0.38 < nx < 0.64 and ny > 0.74 and span < 0.16:
            hainan_pts.extend(cells)
        else:
            for x, y in cells:
                mmp[x, y] = 255

    print(f"Detected stroke pts — taiwan={len(taiwan_pts)} hainan={len(hainan_pts)}")

    seed = (int(0.52 * (w - 1)), int(0.48 * (h - 1)))
    best = None
    for k in (5, 7, 9, 11, 15, 21, 31, 41, 51):
        odd = k if k % 2 else k + 1
        closed = mainland_mask.filter(ImageFilter.MaxFilter(odd))
        if closed.load()[seed[0], seed[1]] >= 128:
            print(f"r={odd}: seed blocked")
            continue
        ext, _ = flood_from(closed, (0, 0), w, h)
        if ext is None or ext[seed[1]][seed[0]]:
            print(f"r={odd}: not sealed")
            continue
        interior, n = flood_from(closed, seed, w, h)
        if interior is None:
            continue
        print(f"r={odd}: SEALED interior={n}")
        best = (odd, interior, n)
        if n > w * h * 0.05:
            break

    if not best:
        print("Could not seal mainland interior", file=sys.stderr)
        return 1

    _k, interior, n = best
    print(f"Mainland interior {n} px")

    # Union mask: Handi interior + island enclosures + bridges so one outer loop wraps all
    union = Image.new("L", (w, h), 0)
    up = union.load()
    for y in range(h):
        for x in range(w):
            if interior[y][x]:
                up[x, y] = 255
    draw = ImageDraw.Draw(union)

    tw_cx, tw_cy, tw_rx, tw_ry = paint_ellipse(draw, TAIWAN, w, h, taiwan_pts or None)
    hn_cx, hn_cy, hn_rx, hn_ry = paint_ellipse(draw, HAINAN, w, h, hainan_pts or None)

    bridge_w = max(14, int(0.012 * w))
    paint_bridge(draw, interior, w, h, (tw_cx, tw_cy), bridge_w)
    paint_bridge(draw, interior, w, h, (hn_cx, hn_cy), bridge_w)

    # Close so bridges/islands fuse cleanly with the coast
    union = union.filter(ImageFilter.MaxFilter(11))
    union = union.filter(ImageFilter.MinFilter(5))

    # Outer boundary of the union (edge of filled region vs exterior)
    up = union.load()
    ext, _ = flood_from(union, (0, 0), w, h)
    if ext is None:
        print("Union exterior flood failed", file=sys.stderr)
        return 1

    edge: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if up[x, y] < 128:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or up[nx, ny] < 128 or ext[ny][nx]:
                    # pixel on filled region adjacent to empty / exterior
                    if not (0 <= nx < w and 0 <= ny < h) or up[nx, ny] < 128:
                        edge.append((x, y))
                        break

    # Prefer boundary between filled and exterior specifically
    edge2: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if up[x, y] < 128:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or ext[ny][nx]:
                    edge2.append((x, y))
                    break
    edge = edge2 if len(edge2) > 100 else edge
    print(f"Outer edge pixels: {len(edge)}")

    path = order_boundary(edge)
    print(f"Ordered path: {len(path)}")
    # Keep enough detail for a smooth continuous rim (~250–450 pts)
    step = max(1, len(path) // 4000)
    sampled = [(float(x), float(y)) for x, y in path[::step]]
    simp = rdp(sampled, max(0.9, w / 1200))
    if len(simp) < 180:
        simp = rdp(sampled, max(0.6, w / 1600))
    if len(simp) < 120:
        simp = sampled[:: max(1, len(sampled) // 280)]
    if simp[0] != simp[-1]:
        simp.append(simp[0])
    print(f"Simplified loop: {len(simp)} pts")

    collection = {
        "version": 1,
        "mapId": "qing-object-painting",
        "groupId": "handi-shibasheng",
        "title": "漢地十八省",
        "overlays": [
            {
                "id": "handi-shibasheng",
                "title": "漢地十八省",
                "rings": [to_norm(simp, w, h)],
                "style": "crimson-glow",
            }
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prev = img.convert("RGB")
    dprev = ImageDraw.Draw(prev)
    dprev.line([(p[0], p[1]) for p in simp], fill=(255, 40, 45), width=4)
    prev.resize((1024, int(1024 * h / w)), Image.Resampling.BILINEAR).save(PREVIEW)

    if w > 2048:
        img.resize((2048, int(round(h * 2048 / w))), Image.Resampling.LANCZOS).save(
            SRC, optimize=True
        )

    ring = collection["overlays"][0]["rings"][0]
    xs = [p["x"] for p in ring]
    ys = [p["y"] for p in ring]
    print(f"Wrote {OUT}")
    print(
        f"Single loop: {len(ring)} pts, closed={ring[0]==ring[-1]}, "
        f"bbox x={min(xs):.3f}-{max(xs):.3f} y={min(ys):.3f}-{max(ys):.3f}"
    )
    print(f"Preview: {PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
