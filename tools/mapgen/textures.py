"""Procedural, seamlessly tiling floor textures.

Each texture is generated as a square tile TILE_SQ grid squares wide and
aligned to the grid, then tiled across the map. Noise is built in the
frequency domain, so it wraps around perfectly.
"""
from __future__ import annotations

import zlib

import numpy as np
from PIL import Image

TILE_SQ = 8


def _hex(c):
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def col(c):
    return _hex(c)[None, None, :]


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def blend(a, b, t):
    return a + (b - a) * t[..., None]


def noise(T, rng, size, aniso=(1.0, 1.0)):
    """Periodic smooth noise (mean 0, std 1) with features about `size` px."""
    white = rng.standard_normal((T, T)).astype(np.float32)
    F = np.fft.rfft2(white)
    fy = np.fft.fftfreq(T).astype(np.float32)[:, None]
    fx = np.fft.rfftfreq(T).astype(np.float32)[None, :]
    F *= np.exp(-(((fx * size * aniso[0]) ** 2) + ((fy * size * aniso[1]) ** 2)) * 4.0)
    n = np.fft.irfft2(F, s=(T, T)).astype(np.float32)
    n -= n.mean()
    n /= n.std() + 1e-6
    return n


def fbm(T, rng, octaves):
    out = np.zeros((T, T), np.float32)
    for size, w in octaves:
        out += noise(T, rng, size) * w
    return out / (out.std() + 1e-6)


def _grid(T):
    return np.mgrid[0:T, 0:T]


def _grout(fx, fy, period, width):
    d = np.minimum(np.minimum(fx, period - 1 - fx), np.minimum(fy, period - 1 - fy)).astype(np.float32)
    return np.clip(1 - (d - width * 0.5) / max(width, 1e-3), 0, 1)


# ---------------------------------------------------------------- textures
def t_stone(T, p, rng):
    yy, xx = _grid(T)
    n = T // p
    cy, cx = yy // p, xx // p
    tone = rng.standard_normal((n, n)).astype(np.float32)
    tone2 = rng.standard_normal((n, n)).astype(np.float32)
    split = rng.random((n, n)) < 0.35
    fx, fy = xx % p, yy % p
    sp = split[cy, cx]
    t = np.where(sp & (fy >= p // 2), tone2[cy, cx], tone[cy, cx])
    out = blend(col("#6f6a63"), col("#9a948a"), sig(t * 0.55 + fbm(T, rng, [(p * 1.5, 1), (p * .3, .5)]) * 0.6))
    out += noise(T, rng, 1.5)[..., None] * 5
    g = max(1.0, p * 0.035)
    d = np.minimum(np.minimum(fx, p - 1 - fx), np.minimum(fy, p - 1 - fy)).astype(np.float32)
    d = np.where(sp, np.minimum(d, np.abs(fy - p / 2 + 0.5)), d)
    m = np.clip(1 - (d - g * 0.5) / g, 0, 1)
    return out * (1 - 0.35 * m[..., None])


def t_tile(T, p, rng):
    q = max(4, p // 2)
    yy, xx = _grid(T)
    n = T // q + 1
    tone = rng.standard_normal((n, n)).astype(np.float32)
    t = tone[yy // q, xx // q]
    out = blend(col("#7d766b"), col("#a49c8e"), sig(t * 0.5 + noise(T, rng, p) * 0.5))
    out += noise(T, rng, 1.5)[..., None] * 4
    m = _grout(xx % q, yy % q, q, max(1.0, p * 0.03))
    return out * (1 - 0.45 * m[..., None])


def t_checker(T, p, rng):
    yy, xx = _grid(T)
    chk = ((yy // p + xx // p) % 2).astype(np.float32)
    out = blend(col("#c9c2b3"), col("#3e3a35"), chk)
    out += fbm(T, rng, [(p, 1), (p * .2, .4)])[..., None] * 6
    m = _grout(xx % p, yy % p, p, max(1.0, p * 0.02))
    return out * (1 - 0.3 * m[..., None])


def t_marble(T, p, rng):
    yy, xx = _grid(T)
    n = fbm(T, rng, [(p * 2, 1), (p * .5, .5), (p * .12, .25)])
    veins = np.abs(np.sin((xx + yy) * (2 * np.pi / T) * 2 + n * 3.0))
    v = np.clip(1 - veins / 0.08, 0, 1)
    out = blend(col("#d9d4ca"), col("#ece8e0"), sig(noise(T, rng, p) * 0.8))
    out = blend(out, col("#8c867c"), v * 0.6)
    m = _grout(xx % p, yy % p, p, max(1.0, p * 0.02))
    return out * (1 - 0.25 * m[..., None])


def t_wood(T, p, rng):
    yy, xx = _grid(T)
    nrows = TILE_SQ * 4
    ph = T / nrows
    row = (yy / ph).astype(int)
    k_row = rng.integers(2, 5, nrows)  # planks per tile per row
    off = rng.random(nrows) * T
    L = T / k_row[row]
    pos = (xx + off[row]) % T
    pid = (pos / L).astype(int)
    tone = rng.standard_normal((nrows, 8)).astype(np.float32)
    t = tone[row, pid]
    grain = noise(T, rng, p * 0.05, aniso=(14, 1))
    out = blend(col("#6e4524"), col("#9a6a3c"), sig(t * 0.7 + grain * 0.5))
    out += noise(T, rng, 1.2)[..., None] * 3
    gap_h = np.abs((yy - row * ph) - 0) < max(1.0, p * 0.012)
    gap_v = (pos % L) < max(1.0, p * 0.015)
    gap = (gap_h | gap_v)[..., None]
    return np.where(gap, out * 0.45, out)


def _contours(n, freq, width):
    r = np.abs(np.sin(n * freq))
    return np.clip(1 - r / width, 0, 1)


def t_water(T, p, rng, deep=False):
    n = fbm(T, rng, [(p * 2.5, 1), (p * .7, .4)])
    lo, hi = ("#12324a", "#1d4a68") if deep else ("#1e5375", "#3482a6")
    out = blend(col(lo), col(hi), sig(n * 1.2))
    rip = _contours(fbm(T, rng, [(p * 0.9, 1), (p * .3, .3)]), 2.5, 0.06)
    return blend(out, col("#b3dcec"), rip * (0.22 if deep else 0.35))


def t_deep_water(T, p, rng):
    return t_water(T, p, rng, deep=True)


def t_lava(T, p, rng):
    n = fbm(T, rng, [(p * 1.5, 1), (p * .4, .5)])
    out = blend(col("#3b0a03"), col("#9a1f07"), sig(n * 1.5))
    cr = _contours(fbm(T, rng, [(p * 0.8, 1), (p * .25, .4)]), 2.0, 0.12)
    out = blend(out, col("#ff8a1a"), cr * 0.9)
    return blend(out, col("#ffe27a"), np.clip(cr - 0.6, 0, 1) * 1.5)


def _ground(lo, hi, T, p, rng, speck=8, big=1.2):
    n = fbm(T, rng, [(p * 3, 1), (p * .8, .6), (p * .2, .3)])
    out = blend(col(lo), col(hi), sig(n * big))
    out += noise(T, rng, 1.2)[..., None] * speck
    return out


def t_cave(T, p, rng):
    return _ground("#544d45", "#7d756a", T, p, rng, speck=6)


def t_dirt(T, p, rng):
    return _ground("#5c4430", "#86684a", T, p, rng, speck=7)


def t_mud(T, p, rng):
    out = _ground("#2f241a", "#4f3c2b", T, p, rng, speck=5)
    wet = np.clip(noise(T, rng, p * .6) - 0.8, 0, 1)
    return blend(out, col("#6b5a48"), wet * 0.6)


def t_grass(T, p, rng):
    out = _ground("#3f5c25", "#6b8a37", T, p, rng, speck=4)
    blades = noise(T, rng, 1.0)
    out[..., 1] += blades * 9
    tufts = np.clip(noise(T, rng, p * .15) - 1.4, 0, 1)
    return blend(out, col("#2c4219"), tufts * 0.6)


def t_sand(T, p, rng):
    out = _ground("#bfa271", "#dcc596", T, p, rng, speck=9, big=0.8)
    dunes = _contours(noise(T, rng, p * 2.0, aniso=(1, 0.5)), 3.0, 0.15)
    return blend(out, col("#a88d5e"), dunes * 0.18)


def t_snow(T, p, rng):
    return _ground("#d6dee5", "#f6f9fb", T, p, rng, speck=3, big=0.9)


def t_ice(T, p, rng):
    out = _ground("#9fc6d8", "#d3ebf4", T, p, rng, speck=2)
    cr = _contours(fbm(T, rng, [(p * 1.2, 1), (p * .3, .5)]), 1.5, 0.03)
    return blend(out, col("#eefaff"), cr * 0.8)


def t_cobble(T, p, rng):
    k = max(2, round(T / (p * 0.45)))
    c = T / k
    pts = rng.random((k, k, 2)) * 0.7 + 0.15
    yy, xx = _grid(T)
    gx, gy = xx / c, yy / c
    ix, iy = np.floor(gx).astype(int), np.floor(gy).astype(int)
    F1 = np.full((T, T), 9.0, np.float32)
    F2 = np.full((T, T), 9.0, np.float32)
    idx = np.zeros((T, T), np.int32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = (ix + dx) % k, (iy + dy) % k
            px = ix + dx + pts[ny, nx, 0]
            py = iy + dy + pts[ny, nx, 1]
            d = np.sqrt((gx - px) ** 2 + (gy - py) ** 2).astype(np.float32)
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d))
            idx = np.where(closer, ny * k + nx, idx)
            F1 = np.where(closer, d, F1)
    tone = rng.standard_normal(k * k).astype(np.float32)[idx]
    out = blend(col("#645f58"), col("#958e83"), sig(tone * 0.6 + noise(T, rng, p) * 0.4))
    out += noise(T, rng, 1.3)[..., None] * 5
    edge = F2 - F1
    m = np.clip(1 - (edge - 0.03) / 0.08, 0, 1)
    return out * (1 - 0.6 * m[..., None])


def t_carpet(T, p, rng):
    out = _ground("#5e1616", "#7f2222", T, p, rng, speck=6, big=0.5)
    return out


def t_rock(T, p, rng):
    out = _ground("#2b2926", "#45413c", T, p, rng, speck=5, big=1.0)
    yy, xx = _grid(T)
    strata = _contours(noise(T, rng, p * 1.5) + (xx - yy) * (6 / T), 3.0, 0.08)
    return blend(out, col("#1e1c1a"), strata * 0.35)


def t_void(T, p, rng):
    return _ground("#08080a", "#141418", T, p, rng, speck=2, big=0.5)


def t_pit(T, p, rng):
    return _ground("#050505", "#121110", T, p, rng, speck=2, big=0.6)


def t_parchment(T, p, rng):
    return _ground("#d8c9a6", "#ece1c6", T, p, rng, speck=4, big=0.7)


FLOORS = {
    "stone": t_stone, "tile": t_tile, "checker": t_checker, "marble": t_marble,
    "wood": t_wood, "cobble": t_cobble, "carpet": t_carpet,
    "cave": t_cave, "dirt": t_dirt, "mud": t_mud, "grass": t_grass, "sand": t_sand,
    "snow": t_snow, "ice": t_ice,
    "water": t_water, "deep_water": t_deep_water, "lava": t_lava,
    "rock": t_rock, "void": t_void, "pit": t_pit, "parchment": t_parchment,
}

# Which floors players can stand on — used to decide where the grid is drawn
# when grid_on: auto and the background is not walkable.
NON_WALKABLE_BG = {"rock", "void", "pit", "parchment", "deep_water", "lava"}

PRINT_TINT = {
    "water": "#d4e6f1", "deep_water": "#b9d3e6", "lava": "#f3c9b5", "grass": "#e2ecd5",
    "pit": "#3a3a3a", "void": "#ffffff", "carpet": "#efdcdc",
}


def _print_version(arr, name, T, p, rng):
    if name in ("rock", "parchment"):
        yy, xx = _grid(T)
        period = max(4, p * 0.14)
        hatch = ((xx + yy) % period) < max(1.0, p * 0.018)
        brk = noise(T, rng, p * 0.25) > -0.6
        out = np.full((T, T, 3), 255, np.float32)
        out[hatch & brk] = 70
        return out
    if name in PRINT_TINT:
        base = col(PRINT_TINT[name])
        g = arr.mean(axis=2, keepdims=True)
        return base - (g.mean() - g) * 0.15
    g = arr.mean(axis=2, keepdims=True)
    lum = 255 - (255 - g) * 0.12
    return np.repeat(lum, 3, axis=2)


_cache: dict = {}


def tile(name: str, ppg: int, seed: int, style: str = "vtt") -> Image.Image:
    key = (name, ppg, seed, style)
    if key not in _cache:
        T = TILE_SQ * ppg
        rng = np.random.default_rng(zlib.crc32(f"{name}:{seed}".encode()))
        arr = FLOORS[name](T, ppg, rng)
        if style == "print":
            arr = _print_version(arr, name, T, ppg, rng)
        _cache[key] = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return _cache[key]


def fill(name: str, W: int, H: int, ppg: int, seed: int, style: str = "vtt") -> Image.Image:
    t = tile(name, ppg, seed, style)
    out = Image.new("RGB", (W, H))
    for y in range(0, H, t.height):
        for x in range(0, W, t.width):
            out.paste(t, (x, y))
    return out
