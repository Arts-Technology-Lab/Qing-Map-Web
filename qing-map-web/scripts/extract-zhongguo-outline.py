#!/usr/bin/env python3
"""
Extract 中國 border: yellow outer NW arc + southern/eastern red coast
(including Hainan & Taiwan) → one continuous closed loop.

Important: ignore the northern/western Handi red wall so the yellow
outer frontier defines Xinjiang / Mongolia / Manchuria / Tibet extent.
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
SRC = ROOT / "assets" / "overlays" / "source" / "zhongguo-outline.png"
FULL_SRC = Path(
    "/Users/cwy1013/Library/CloudStorage/OneDrive-TheUniversityofHongKong-Connect/"
    "HKU/2026-2027 Sem 1/234MB JPG File_Super Resolution_18438x10516px_DSC3891-Edit-Handi-Zhongguo.jpg.png"
)
OUT = ROOT / "data" / "overlays" / "zhongguo.json"
PREVIEW = ROOT / "assets" / "overlays" / "source" / "debug-zhongguo-preview.png"

Image.MAX_IMAGE_PIXELS = None

TAIWAN = {"center": (0.755, 0.735), "radii": (0.022, 0.042)}
HAINAN = {"center": (0.500, 0.835), "radii": (0.032, 0.026)}


def is_red(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 128:
        return False
    if r >= 150 and g <= 125 and b <= 125 and (r - max(g, b)) >= 40:
        return True
    hv, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (hv <= 0.05 or hv >= 0.95) and s >= 0.35 and v >= 0.35 and r >= 120


def is_yellow(r: int, g: int, b: int, a: int = 255) -> bool:
    if a < 128:
        return False
    if r >= 150 and g >= 120 and b <= 130 and (r + g) / 2 - b >= 40:
        return True
    hv, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 0.08 <= hv <= 0.23 and s >= 0.28 and v >= 0.40 and b < 170


def coastal_red(nx: float, ny: float) -> bool:
    """Keep Handi red only on south / east / island approaches — not the Great-Wall north rim."""
    if ny >= 0.58:
        return True  # south incl. Hainan approach
    if nx >= 0.66:
        return True  # east coast / Taiwan
    if nx >= 0.55 and ny >= 0.48:
        return True  # SE corner
    if 0.42 <= nx <= 0.62 and ny >= 0.72:
        return True  # Hainan bay
    return False


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


def paint_ellipse(draw: ImageDraw.ImageDraw, spec: dict, w: int, h: int):
    cx = spec["center"][0] * (w - 1)
    cy = spec["center"][1] * (h - 1)
    rx = spec["radii"][0] * (w - 1)
    ry = spec["radii"][1] * (h - 1)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    return cx, cy


def paint_bridge(draw, filled_mask, w, h, target, width):
    tx, ty = target
    bp = filled_mask.load()
    best = None
    best_d = 1e18
    step = max(2, min(w, h) // 400)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if bp[x, y] < 128:
                continue
            d = (x - tx) ** 2 + (y - ty) ** 2
            if d < best_d:
                best_d = d
                best = (x, y)
    if best:
        draw.line([best, (int(tx), int(ty))], fill=255, width=max(3, int(width)))


def load_image() -> Image.Image:
    need_full = True
    if SRC.exists():
        im = Image.open(SRC)
        if im.size[0] >= 2800:
            need_full = False
            print(f"Using {SRC.name} {im.size}")
            return im.convert("RGBA")
    if need_full and FULL_SRC.exists():
        print("Resampling Zhongguo source → 3072…")
        full = Image.open(FULL_SRC).convert("RGBA")
        tw = 3072
        th = int(round(full.size[1] * tw / full.size[0]))
        img = full.resize((tw, th), Image.Resampling.LANCZOS)
        SRC.parent.mkdir(parents=True, exist_ok=True)
        img.save(SRC, optimize=True)
        return img
    if SRC.exists():
        return Image.open(SRC).convert("RGBA")
    raise FileNotFoundError(FULL_SRC)


def main() -> int:
    img = load_image()
    w, h = img.size
    pixels = img.load()

    stroke = Image.new("L", (w, h), 0)
    sp = stroke.load()
    n_yel = n_red = n_skip = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            nx, ny = x / (w - 1), y / (h - 1)
            if is_yellow(r, g, b, a):
                sp[x, y] = 255
                n_yel += 1
            elif is_red(r, g, b, a):
                if coastal_red(nx, ny):
                    sp[x, y] = 255
                    n_red += 1
                else:
                    n_skip += 1
    print(f"yellow={n_yel} coastal_red={n_red} skipped_inner_red={n_skip}")

    # Seed in outer territories north of Handi wall (Mongolia / plateau band)
    seed = (int(0.42 * (w - 1)), int(0.28 * (h - 1)))
    best = None
    for k in (9, 13, 17, 21, 27, 35, 45, 55, 65, 75):
        odd = k if k % 2 else k + 1
        closed = stroke.filter(ImageFilter.MaxFilter(min(odd, 51)))
        # extra passes for large gaps
        if odd > 51:
            for _ in range((odd - 51) // 10):
                closed = closed.filter(ImageFilter.MaxFilter(21))
        cbp = closed.load()
        if cbp[seed[0], seed[1]] >= 128:
            # try alternate seed further west
            alt = (int(0.30 * (w - 1)), int(0.32 * (h - 1)))
            if cbp[alt[0], alt[1]] < 128:
                seed = alt
            else:
                print(f"r={odd}: seed blocked")
                continue
        ext, _ = flood_from(closed, (0, 0), w, h)
        if ext is None or ext[seed[1]][seed[0]]:
            print(f"r={odd}: not sealed (seed={seed[0]/w:.2f},{seed[1]/h:.2f})")
            continue
        interior, n = flood_from(closed, seed, w, h)
        if interior is None:
            continue
        print(f"r={odd}: SEALED interior={n} ({100*n/(w*h):.1f}%)")
        best = (odd, interior, n)
        # Greater China should be a large fraction of the map
        if n > w * h * 0.18:
            break

    if not best:
        print("Could not seal Zhongguo interior", file=sys.stderr)
        return 1

    _k, interior, n = best

    union = Image.new("L", (w, h), 0)
    up = union.load()
    for y in range(h):
        for x in range(w):
            if interior[y][x]:
                up[x, y] = 255
    draw = ImageDraw.Draw(union)
    tw_cx, tw_cy = paint_ellipse(draw, TAIWAN, w, h)
    hn_cx, hn_cy = paint_ellipse(draw, HAINAN, w, h)
    bridge_w = max(18, int(0.015 * w))
    paint_bridge(draw, union, w, h, (tw_cx, tw_cy), bridge_w)
    paint_bridge(draw, union, w, h, (hn_cx, hn_cy), bridge_w)
    union = union.filter(ImageFilter.MaxFilter(11))
    union = union.filter(ImageFilter.MinFilter(5))

    up = union.load()
    ext, _ = flood_from(union, (0, 0), w, h)
    if ext is None:
        print("Exterior flood failed", file=sys.stderr)
        return 1

    edge: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if up[x, y] < 128:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or ext[ny][nx]:
                    edge.append((x, y))
                    break
    print(f"Outer edge: {len(edge)}")

    path = order_boundary(edge)
    step = max(1, len(path) // 5000)
    sampled = [(float(x), float(y)) for x, y in path[::step]]
    simp = rdp(sampled, max(0.85, w / 1200))
    if len(simp) < 180:
        simp = sampled[:: max(1, len(sampled) // 320)]
    if simp[0] != simp[-1]:
        simp.append(simp[0])

    collection = {
        "version": 1,
        "mapId": "qing-object-painting",
        "groupId": "zhongguo",
        "title": "中國",
        "overlays": [
            {
                "id": "zhongguo",
                "title": "中國",
                "rings": [to_norm(simp, w, h)],
                "style": "crimson-glow",
            }
        ],
    }

    ring = collection["overlays"][0]["rings"][0]
    # Ensure Taiwan / Hainan lobes are enclosed (outer yellow+coast may miss them)
    ring = splice_island_lobe(ring, 0.755, 0.735, 0.026, 0.048)
    ring = splice_island_lobe(ring, 0.500, 0.840, 0.038, 0.030)
    collection["overlays"][0]["rings"] = [ring]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    prev = img.convert("RGB")
    dprev = ImageDraw.Draw(prev)
    pts = [(p["x"] * (w - 1), p["y"] * (h - 1)) for p in ring]
    dprev.line(pts, fill=(255, 45, 40), width=4)
    prev.resize((1024, int(1024 * h / w)), Image.Resampling.BILINEAR).save(PREVIEW)

    if w > 2048:
        img.resize((2048, int(round(h * 2048 / w))), Image.Resampling.LANCZOS).save(
            SRC, optimize=True
        )

    xs = [p["x"] for p in ring]
    ys = [p["y"] for p in ring]
    print(f"Wrote {OUT}")
    print(
        f"Zhongguo: {len(ring)} pts bbox x={min(xs):.3f}-{max(xs):.3f} "
        f"y={min(ys):.3f}-{max(ys):.3f}"
    )
    return 0


def point_in_ring(x: float, y: float, ring: list[dict[str, float]]) -> bool:
    n = len(ring) - 1
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]["x"], ring[i]["y"]
        xj, yj = ring[j]["x"], ring[j]["y"]
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def splice_island_lobe(
    ring: list[dict[str, float]],
    cx: float,
    cy: float,
    rx: float,
    ry: float,
) -> list[dict[str, float]]:
    if point_in_ring(cx, cy, ring):
        return ring
    body = ring[:-1] if ring[0] == ring[-1] else ring[:]
    bi = min(range(len(body)), key=lambda i: (body[i]["x"] - cx) ** 2 + (body[i]["y"] - cy) ** 2)
    mx = sum(p["x"] for p in body) / len(body)
    my = sum(p["y"] for p in body) / len(body)
    ell = []
    for i in range(48):
        t = 2 * math.pi * i / 48
        ell.append(
            {
                "x": round(cx + rx * math.cos(t), 5),
                "y": round(cy + ry * math.sin(t), 5),
            }
        )
    ei = min(
        range(len(ell)),
        key=lambda i: (ell[i]["x"] - body[bi]["x"]) ** 2 + (ell[i]["y"] - body[bi]["y"]) ** 2,
    )

    def route(start: int, step: int):
        out = []
        i = start
        for _ in range(len(ell)):
            out.append(ell[i])
            i = (i + step) % len(ell)
        return out

    r1, r2 = route(ei, 1), route(ei, -1)
    mid1, mid2 = r1[len(r1) // 2], r2[len(r2) // 2]
    d1 = (mid1["x"] - mx) ** 2 + (mid1["y"] - my) ** 2
    d2 = (mid2["x"] - mx) ** 2 + (mid2["y"] - my) ** 2
    arc = r1 if d1 >= d2 else r2
    new_body = body[: bi + 1] + arc[1:] + body[bi + 1 :]
    new_body.append(dict(new_body[0]))
    return new_body


if __name__ == "__main__":
    raise SystemExit(main())
