#!/usr/bin/env python3
"""
Accurate Handi / Zhongguo outline extraction from hand-drawn strokes.

1. Seal stroke gaps with the smallest MaxFilter that closes the loop
2. Take the interior outer-contour (coarse, offset from ink)
3. Snap every contour sample back onto nearest original ink pixel
4. Mild RDP — keep the hand-drawn jaggedness

Zhongguo = yellow frontier ∪ coastal crimson (yellow alone does not close).
Handi islands = separate snapped rings (Taiwan / Hainan), never bridged.
"""

from __future__ import annotations

import colorsys
import json
import math
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
HANDI_FULL = Path(
    "/Users/cwy1013/Library/CloudStorage/OneDrive-TheUniversityofHongKong-Connect/"
    "HKU/2026-2027 Sem 1/234MB JPG File_Super Resolution_18438x10516px_DSC3891-Edit-Handi.jpg.png"
)
ZHONG_FULL = Path(
    "/Users/cwy1013/Library/CloudStorage/OneDrive-TheUniversityofHongKong-Connect/"
    "HKU/2026-2027 Sem 1/234MB JPG File_Super Resolution_18438x10516px_DSC3891-Edit-Handi-Zhongguo.jpg.png"
)
HANDI_OUT = ROOT / "data" / "overlays" / "handi-shibasheng.json"
ZHONG_OUT = ROOT / "data" / "overlays" / "zhongguo.json"
SRC_DIR = ROOT / "assets" / "overlays" / "source"
PREVIEW = SRC_DIR / "debug-compare-preview.png"

Image.MAX_IMAGE_PIXELS = None
WORK_W = 4096


def is_crimson(r, g, b, a=255):
    if a < 128:
        return False
    if r >= 175 and g <= 100 and b <= 100 and (r - max(g, b)) >= 65:
        return True
    hv, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (hv <= 0.035 or hv >= 0.96) and s >= 0.48 and v >= 0.45 and r >= 150 and g < 110


def is_yellow(r, g, b, a=255):
    if a < 128:
        return False
    if r >= 170 and g >= 145 and b <= 110 and (r + g) / 2 - b >= 55:
        return True
    hv, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return 0.10 <= hv <= 0.20 and s >= 0.40 and v >= 0.50 and b < 140


def load_work(path: Path) -> Image.Image:
    print(f"Loading {path.name}…")
    im = Image.open(path).convert("RGBA")
    th = int(round(im.size[1] * WORK_W / im.size[0]))
    return im.resize((WORK_W, th), Image.Resampling.LANCZOS)


def build_mask(img, pred) -> Image.Image:
    w, h = img.size
    px = img.load()
    m = Image.new("L", (w, h), 0)
    mp = m.load()
    n = 0
    for y in range(h):
        for x in range(w):
            if pred(*px[x, y]):
                mp[x, y] = 255
                n += 1
    print(f"  ink pixels: {n}")
    return m


def mask_coords(mask: Image.Image) -> np.ndarray:
    """Nx2 float array of (x, y) ink pixels."""
    arr = np.array(mask)
    ys, xs = np.where(arr >= 128)
    return np.stack([xs.astype(np.float64), ys.astype(np.float64)], axis=1)


def flood(barrier, start, w, h):
    bp = barrier.load()
    sx, sy = start
    if not (0 <= sx < w and 0 <= sy < h) or bp[sx, sy] >= 128:
        return None, 0
    vis = [[False] * w for _ in range(h)]
    q = deque([start])
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


def seal_interior(stroke: Image.Image, seed, min_frac=0.04, radii=None):
    w, h = stroke.size
    best = None
    for k in radii or (5, 7, 9, 11, 15, 21, 27, 35, 45, 55, 65, 75):
        odd = k if k % 2 else k + 1
        closed = stroke.filter(ImageFilter.MaxFilter(odd))
        cbp = closed.load()
        sx, sy = seed
        if cbp[sx, sy] >= 128:
            print(f"  r={odd}: seed blocked")
            continue
        ext, _ = flood(closed, (0, 0), w, h)
        if ext is None or ext[sy][sx]:
            print(f"  r={odd}: not sealed")
            continue
        interior, n = flood(closed, seed, w, h)
        if interior is None:
            continue
        print(f"  r={odd}: sealed interior={n} ({100 * n / (w * h):.1f}%)")
        best = (odd, interior, n, closed)
        if n > w * h * min_frac:
            break
    return best


def order_boundary(edge):
    rem = set(edge)
    start = min(rem, key=lambda p: (p[1], p[0]))
    path = [start]
    rem.remove(start)
    dirs = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    while rem and len(path) < len(edge) * 2:
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


def contour_from_interior(interior, w, h):
    edge = []
    for y in range(h):
        row = interior[y]
        for x in range(w):
            if not row[x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or not interior[ny][nx]:
                    edge.append((x, y))
                    break
    print(f"  edge pixels: {len(edge)}")
    return order_boundary(edge)


def rdp(points, eps):
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
    if max_d > eps:
        return rdp(points[: idx + 1], eps)[:-1] + rdp(points[idx:], eps)
    return [start, end]


def snap_to_ink(
    path,
    ink_xy: np.ndarray,
    search_r: float = 48.0,
    sample_step: int = 2,
    outward_from: tuple[float, float] | None = None,
):
    """Project coarse contour onto nearest ink pixels (chunked KD-style brute)."""
    if ink_xy.size == 0:
        return [(float(x), float(y)) for x, y in path]
    pts = path[:: max(1, sample_step)]
    snapped = []
    r2 = search_r * search_r
    cell = max(8.0, search_r / 2)
    buckets: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(ink_xy):
        key = (int(x // cell), int(y // cell))
        buckets.setdefault(key, []).append(i)

    prev = None
    cont_r2 = (search_r * 0.55) ** 2
    ox = oy = 0.0
    if outward_from is not None:
        ox, oy = outward_from
    for x, y in pts:
        fx, fy = float(x), float(y)
        best_i = None
        best_score = 1e18
        cx, cy = int(fx // cell), int(fy // cell)
        span = 2
        for gx in range(cx - span, cx + span + 1):
            for gy in range(cy - span, cy + span + 1):
                for i in buckets.get((gx, gy), ()):
                    dx = ink_xy[i, 0] - fx
                    dy = ink_xy[i, 1] - fy
                    d = dx * dx + dy * dy
                    if d > r2:
                        continue
                    score = d
                    if prev is not None:
                        pdx = ink_xy[i, 0] - prev[0]
                        pdy = ink_xy[i, 1] - prev[1]
                        pd = pdx * pdx + pdy * pdy
                        if pd > cont_r2:
                            score += pd * 4.0
                        else:
                            score += pd * 0.15
                    if outward_from is not None:
                        # Prefer outer side of thick marker (farther from interior seed)
                        od = (ink_xy[i, 0] - ox) ** 2 + (ink_xy[i, 1] - oy) ** 2
                        score -= 0.35 * od
                    if score < best_score:
                        best_score = score
                        best_i = i
        if best_i is None:
            if prev is not None:
                snapped.append(prev)
            continue
        p = (float(ink_xy[best_i, 0]), float(ink_xy[best_i, 1]))
        if prev is not None and (p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2 < 0.25:
            continue
        snapped.append(p)
        prev = p

    if len(snapped) < 8:
        return [(float(x), float(y)) for x, y in path]
    return snapped


def smooth_then_resnap(
    path,
    ink_xy: np.ndarray,
    window: int = 7,
    outward_from: tuple[float, float] | None = None,
):
    """Moving-average to kill pixel stair-steps, then project back onto ink."""
    if len(path) < window + 2 or ink_xy.size == 0:
        return path
    pts = list(path)
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    half = window // 2
    sm = []
    for i in range(n):
        xs = ys = 0.0
        for k in range(-half, half + 1):
            x, y = pts[(i + k) % n]
            xs += x
            ys += y
        sm.append((xs / window, ys / window))
    sm.append(sm[0])
    return snap_to_ink(sm, ink_xy, search_r=20.0, sample_step=1, outward_from=outward_from)


def densify_simplify(path, w, target=320, eps_div=2200):
    if len(path) < 3:
        return path[:]
    if len(path) > target * 3:
        step = max(1, len(path) // (target * 2))
        sampled = path[::step]
    else:
        sampled = path
    simp = rdp(sampled, max(0.7, w / eps_div))
    if len(simp) < target * 0.55:
        step2 = max(1, len(path) // target)
        simp = path[::step2]
    if simp[0] != simp[-1]:
        simp = list(simp) + [simp[0]]
    return [(float(x), float(y)) for x, y in simp]


def to_norm(pts, w, h):
    ring = [
        {
            "x": round(max(0.0, min(1.0, x / max(w - 1, 1))), 5),
            "y": round(max(0.0, min(1.0, y / max(h - 1, 1))), 5),
        }
        for x, y in pts
    ]
    if ring and ring[0] != ring[-1]:
        ring.append(dict(ring[0]))
    return ring


def components(mask, min_size=30):
    w, h = mask.size
    bp = mask.load()
    seen = [[False] * w for _ in range(h)]
    comps = []
    for y in range(h):
        for x in range(w):
            if bp[x, y] < 128 or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == dy == 0:
                            continue
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and bp[nx, ny] >= 128:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
            if len(cells) >= min_size:
                comps.append(cells)
    comps.sort(key=len, reverse=True)
    return comps


def order_chain(cells):
    rem = set(cells)
    start = min(rem, key=lambda p: (p[0], p[1]))
    path = [start]
    rem.remove(start)
    while rem:
        cx, cy = path[-1]
        cand = None
        best = 1e18
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                n = (cx + dx, cy + dy)
                if n in rem:
                    d = dx * dx + dy * dy
                    if d < best:
                        best = d
                        cand = n
        if cand is None:
            cand = min(rem, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
            if (cand[0] - cx) ** 2 + (cand[1] - cy) ** 2 > 25:
                break
        path.append(cand)
        rem.remove(cand)
    return [(float(x), float(y)) for x, y in path]


def island_ring_from_cells(cells, w, h, target=140):
    """
    Radial outer hull of the island doodle (farthest ink per angle), then light
    simplify — follows the drawn circle instead of shrinking to an inner rim.
    """
    if len(cells) < 12:
        return None
    cx = sum(p[0] for p in cells) / len(cells)
    cy = sum(p[1] for p in cells) / len(cells)
    bins = 180
    best = [None] * bins
    for x, y in cells:
        ang = math.atan2(y - cy, x - cx)
        bi = int((ang + math.pi) / (2 * math.pi) * bins) % bins
        d = (x - cx) ** 2 + (y - cy) ** 2
        if best[bi] is None or d > best[bi][0]:
            best[bi] = (d, float(x), float(y))
    ring = [(b[1], b[2]) for b in best if b is not None]
    if len(ring) < 24:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return densify_simplify(ring, w, target=target, eps_div=9000)


def hainan_ring(mask, w, h):
    """
    Hainan stroke is often 8-connected to the mainland south coast.
    Crop the island doodle ROI (below the coast strip) and take the radial hull.
    """
    mp = mask.load()
    cells = []
    # Below Leizhou coast; around the drawn Hainan circle
    for y in range(int(0.808 * (h - 1)), int(0.875 * (h - 1))):
        for x in range(int(0.468 * (w - 1)), int(0.555 * (w - 1))):
            if mp[x, y] >= 128:
                cells.append((x, y))
    if len(cells) < 80:
        # slightly wider fallback ROI
        cells = []
        for y in range(int(0.800 * (h - 1)), int(0.885 * (h - 1))):
            for x in range(int(0.455 * (w - 1)), int(0.565 * (w - 1))):
                if mp[x, y] >= 128:
                    cells.append((x, y))
    if len(cells) < 40:
        return None
    # Drop residual mainland-coast pixels: keep only points near island centroid band
    cx = sum(c[0] for c in cells) / len(cells)
    cy = sum(c[1] for c in cells) / len(cells)
    # Prefer geometric center of the doodle, not mass near coast
    cy = max(cy, 0.825 * (h - 1))
    cx = min(max(cx, 0.490 * (w - 1)), 0.530 * (w - 1))
    max_r2 = (0.045 * (w - 1)) ** 2
    focused = [c for c in cells if (c[0] - cx) ** 2 + (c[1] - cy) ** 2 <= max_r2]
    if len(focused) < 40:
        focused = cells
    print(f"  hainan ROI cells={len(cells)} focused={len(focused)}")
    return island_ring_from_cells(focused, w, h, target=120)


def island_rings(mask, w, h):
    comps = components(mask, min_size=40)
    tw_cells = None
    for cells in comps:
        cx = sum(c[0] for c in cells) / len(cells)
        cy = sum(c[1] for c in cells) / len(cells)
        nx, ny = cx / (w - 1), cy / (h - 1)
        xs = (max(c[0] for c in cells) - min(c[0] for c in cells)) / (w - 1)
        ys = (max(c[1] for c in cells) - min(c[1] for c in cells)) / (h - 1)
        span = max(xs, ys)
        if nx > 0.70 and 0.62 < ny < 0.86 and span < 0.12:
            if tw_cells is None or len(cells) > len(tw_cells):
                tw_cells = cells

    tw = island_ring_from_cells(tw_cells, w, h, target=120) if tw_cells else None
    hn = hainan_ring(mask, w, h)
    print(f"  islands: taiwan={'yes' if tw else 'NO'} hainan={'yes' if hn else 'NO'}")

    def ellipse(cxn, cyn, rxn, ryn, n=48):
        cx, cy = cxn * (w - 1), cyn * (h - 1)
        rx, ry = rxn * (w - 1), ryn * (h - 1)
        pts = [
            (cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
        pts.append(pts[0])
        return pts

    return tw or ellipse(0.755, 0.74, 0.015, 0.030), hn or ellipse(0.505, 0.830, 0.022, 0.020)


def write_json_wh(path, group_id, title, rings_px, style, w, h):
    data = {
        "version": 1,
        "mapId": "qing-object-painting",
        "groupId": group_id,
        "title": title,
        "overlays": [
            {
                "id": group_id,
                "title": title,
                "rings": [to_norm(r, w, h) for r in rings_px],
                "style": style,
            }
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.name}: {len(rings_px)} rings, pts={[len(r) for r in rings_px]} style={style}")


def westernmost_yellow_path(ymask: Image.Image, w: int, h: int, x_lim=0.38, y0=0.02, y1=0.82):
    """
    Outermost western frontier from yellow ink: westernmost yellow in each
    horizontal band. Captures Qing western claim bulges the seal contour skips.
    """
    mp = ymask.load()
    x_max = int(x_lim * (w - 1))
    ya, yb = int(y0 * (h - 1)), int(y1 * (h - 1))
    band = 3
    pts = []
    for y in range(ya, yb + 1, 2):
        xs = []
        for yy in range(max(ya, y - band), min(yb, y + band) + 1):
            for x in range(0, x_max + 1):
                if mp[x, yy] >= 128:
                    xs.append(x)
        if xs:
            pts.append((float(min(xs)), float(y)))
    if len(pts) < 20:
        return None
    cleaned = [pts[0]]
    for p in pts[1:]:
        if (p[0] - cleaned[-1][0]) ** 2 + (p[1] - cleaned[-1][1]) ** 2 >= 4:
            cleaned.append(p)
    ink_xy = mask_coords(ymask)
    west_ink = ink_xy[ink_xy[:, 0] <= x_max + 8]
    snapped = snap_to_ink(cleaned, west_ink, search_r=28.0, sample_step=1)
    snapped = smooth_then_resnap(snapped, west_ink, window=5)
    return densify_simplify(snapped, w, target=220, eps_div=5000)


def splice_west_frontier(loop, west_path, w, h, x_cut=0.32):
    """Replace the western arc of the sealed loop with outermost yellow path."""
    if not west_path or len(west_path) < 10:
        return loop
    pts = list(loop)
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)
    west_set = {i for i, (x, y) in enumerate(pts) if x / (w - 1) < x_cut}
    if len(west_set) < 5:
        return loop
    marked = [i in west_set for i in range(n)]

    wraps = marked[0] and marked[-1] and not all(marked)
    if wraps:
        a = 0
        while a < n and marked[a]:
            a += 1
        b = n - 1
        while b >= 0 and marked[b]:
            b -= 1
        start, end = b + 1, a
        before = pts[(start - 1) % n]
        keep = pts[end:start]
    else:
        best = (0, 0, 0)
        i = 0
        while i < n:
            if not marked[i]:
                i += 1
                continue
            j = i
            while j < n and marked[j]:
                j += 1
            if j - i > best[2]:
                best = (i, j, j - i)
            i = j
        start, end, length = best
        before = pts[(start - 1) % n]
        keep_head = pts[:start]
        keep_tail = pts[end:]
        keep = None

    wp = list(west_path)
    if wp[0] == wp[-1]:
        wp = wp[:-1]
    d_fwd = (wp[0][0] - before[0]) ** 2 + (wp[0][1] - before[1]) ** 2
    d_rev = (wp[-1][0] - before[0]) ** 2 + (wp[-1][1] - before[1]) ** 2
    if d_rev < d_fwd:
        wp = list(reversed(wp))

    if wraps:
        merged = keep + wp
        removed = n - len(keep)
    else:
        merged = keep_head + wp + keep_tail
        removed = end - start
    if merged[0] != merged[-1]:
        merged.append(merged[0])
    print(f"  spliced western yellow: {removed} sealed pts → {len(wp)} yellow pts")
    return densify_simplify(merged, w, target=650, eps_div=4000)


def extract_snapped_loop(stroke_mask, seed, ink_xy, min_frac, label):
    sealed = seal_interior(stroke_mask, seed, min_frac=min_frac)
    if not sealed:
        return None
    _k, interior, _n, _closed = sealed
    edge = contour_from_interior(interior, stroke_mask.size[0], stroke_mask.size[1])
    print(f"  {label}: snapping {len(edge)} edge pts → ink ({len(ink_xy)} pixels)…")
    outward = (float(seed[0]), float(seed[1]))
    snapped = snap_to_ink(edge, ink_xy, search_r=56.0, sample_step=2, outward_from=outward)
    snapped = smooth_then_resnap(snapped, ink_xy, window=9, outward_from=outward)
    print(f"  {label}: snapped samples={len(snapped)}")
    # Keep nearly all snapped samples — RDP only kills sub-pixel stair noise
    loop = densify_simplify(snapped, stroke_mask.size[0], target=700, eps_div=4500)
    return loop


def main(argv: list[str] | None = None):
    args = argv if argv is not None else sys.argv[1:]
    zhong_only = "--zhong-only" in args
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    mainland = tw = hn = None
    w = h = None
    hmask = None

    if not zhong_only:
        # --- Handi ---
        print("=== Handi ===")
        himg = load_work(HANDI_FULL)
        w, h = himg.size
        himg.save(SRC_DIR / "handi-outline.png", optimize=True)
        hmask = build_mask(himg, is_crimson)
        hink = mask_coords(hmask)
        seed = (int(0.52 * (w - 1)), int(0.50 * (h - 1)))
        mainland = extract_snapped_loop(hmask, seed, hink, min_frac=0.05, label="handi")
        if not mainland:
            print("Handi seal failed", file=sys.stderr)
            return 1
        tw, hn = island_rings(hmask, w, h)
        write_json_wh(HANDI_OUT, "handi-shibasheng", "漢地十八省", [mainland, tw, hn], "crimson-glow", w, h)
    else:
        print("=== Handi (skip; --zhong-only) ===")
        # reuse island rings from existing Handi JSON scaled at extract time from Zhong source
        pass

    # --- Zhongguo (outermost Qing frontier + islands) ---
    print("=== Zhongguo ===")
    zimg = load_work(ZHONG_FULL)
    w2, h2 = zimg.size
    zimg.save(SRC_DIR / "zhongguo-outline.png", optimize=True)
    ymask = build_mask(zimg, is_yellow)
    cmask = build_mask(zimg, is_crimson)

    # Yellow alone rarely seals (coast was drawn in crimson). Union coastal crimson
    # so the empire loop closes on the outermost coast while keeping the new western yellow.
    union = ymask.copy()
    up = union.load()
    cp = cmask.load()
    for y in range(h2):
        for x in range(w2):
            if cp[x, y] < 128:
                continue
            nx, ny = x / (w2 - 1), y / (h2 - 1)
            # east / south / coastal Handi stroke to close the empire loop
            if ny >= 0.48 or nx >= 0.62 or (nx >= 0.55 and ny >= 0.35):
                up[x, y] = 255

    y_xy = mask_coords(ymask)
    c_xy = mask_coords(cmask)
    if len(y_xy) and len(c_xy):
        cell = 16.0
        buckets: dict[tuple[int, int], list[int]] = {}
        for i, (x, y) in enumerate(y_xy):
            buckets.setdefault((int(x // cell), int(y // cell)), []).append(i)

        def near_yellow(x, y, lim2=400.0):
            cx, cy = int(x // cell), int(y // cell)
            for gx in range(cx - 2, cx + 3):
                for gy in range(cy - 2, cy + 3):
                    for i in buckets.get((gx, gy), ()):
                        dx = y_xy[i, 0] - x
                        dy = y_xy[i, 1] - y
                        if dx * dx + dy * dy < lim2:
                            return True
            return False

        coast = []
        for x, y in c_xy:
            nx, ny = x / (w2 - 1), y / (h2 - 1)
            if ny >= 0.48 or nx >= 0.62 or (nx >= 0.55 and ny >= 0.35):
                if not near_yellow(x, y):
                    coast.append((x, y))
        ink_xy = np.vstack([y_xy, np.array(coast, dtype=np.float64)]) if coast else y_xy
        print(f"  snap ink: yellow={len(y_xy)} + coastal crimson={len(coast)}")
    else:
        ink_xy = y_xy if len(y_xy) else c_xy

    zloop = None
    for sxn, syn in (
        (0.40, 0.28),
        (0.50, 0.35),
        (0.35, 0.40),
        (0.55, 0.45),
        (0.45, 0.50),
        (0.25, 0.45),  # western interior after frontier expansion
    ):
        seed2 = (int(sxn * (w2 - 1)), int(syn * (h2 - 1)))
        print(f"  try seed ({sxn:.2f},{syn:.2f})")
        zloop = extract_snapped_loop(union, seed2, ink_xy, min_frac=0.10, label="zhongguo")
        if zloop:
            break
    if not zloop:
        print("  coastal union failed; full crimson∪yellow…")
        union2 = ymask.copy()
        u2 = union2.load()
        for y in range(h2):
            for x in range(w2):
                if cp[x, y] >= 128:
                    u2[x, y] = 255
        seed2 = (int(0.52 * (w2 - 1)), int(0.45 * (h2 - 1)))
        zloop = extract_snapped_loop(union2, seed2, ink_xy, min_frac=0.10, label="zhongguo")
    if not zloop:
        print("Zhongguo seal failed", file=sys.stderr)
        return 1

    # Force outermost western Qing claim (updated yellow frontier)
    west = westernmost_yellow_path(ymask, w2, h2)
    if west:
        print(f"  western yellow path pts={len(west)}")
        zloop = splice_west_frontier(zloop, west, w2, h2, x_cut=0.34)
    else:
        print("  warning: no western yellow path")

    # China = outermost empire loop + Taiwan / Hainan
    z_tw, z_hn = island_rings(cmask, w2, h2)
    write_json_wh(
        ZHONG_OUT,
        "zhongguo",
        "中國",
        [zloop, z_tw, z_hn],
        "yellow-glow",
        w2,
        h2,
    )

    # Preview
    prev = zimg.convert("RGB")
    d = ImageDraw.Draw(prev)
    yp = ymask.load()
    cpaint = cmask.load()
    for y in range(0, h2, 1):
        for x in range(0, w2, 1):
            if yp[x, y] >= 128:
                d.point((x, y), fill=(255, 210, 40))
            if cpaint[x, y] >= 128:
                d.point((x, y), fill=(255, 40, 40))
    for loop, col in (
        (zloop, (80, 255, 80)),
        (z_tw, (80, 255, 80)),
        (z_hn, (80, 255, 80)),
    ):
        d.line([(p[0], p[1]) for p in loop], fill=col, width=3)
    if mainland is not None:
        sx, sy = w2 / w, h2 / h
        for loop in (mainland, tw, hn):
            d.line([(p[0] * sx, p[1] * sy) for p in loop], fill=(0, 255, 255), width=2)
    prev.resize((1600, int(1600 * h2 / w2)), Image.Resampling.BILINEAR).save(PREVIEW)
    print(f"Preview (yellow/red=ink, lime=zhongguo outermost+islands): {PREVIEW}")

    # West QA crop: yellow ink vs new lime loop
    west = prev.crop((0, 0, int(0.38 * w2), int(0.72 * h2)))
    west.resize((900, int(900 * west.size[1] / west.size[0])), Image.Resampling.BILINEAR).save(
        SRC_DIR / "qa-west-new-ink.jpg", quality=92
    )

    for name in ("handi-outline.png", "zhongguo-outline.png"):
        p = SRC_DIR / name
        if not p.exists():
            continue
        im = Image.open(p)
        if im.size[0] > 2048:
            twid = 2048
            th = int(round(im.size[1] * twid / im.size[0]))
            im.resize((twid, th), Image.Resampling.LANCZOS).save(p, optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
