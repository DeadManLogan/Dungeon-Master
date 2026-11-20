"""Top-down map symbols (furniture, terrain features, light sources...).

Each symbol draws with a Pen in local units: (0, 0) is the symbol centre,
w x h is the footprint in squares before rotation. Add new symbols with the
@sym decorator; they become available to specs immediately.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

INK = "#1a1a1a"
WOOD, WOOD_D, WOOD_L = "#7a4f2a", "#4a2f18", "#a06d3e"
STONE, STONE_D, STONE_L = "#8d8880", "#55514b", "#b3aea5"
IRON, GOLD = "#3b3b40", "#d4a838"
FIRE_O, FIRE_Y, FIRE_R = "#ff8a1e", "#ffd34a", "#c8380e"


@dataclass
class Sym:
    fn: Callable
    size: list
    layer: int = 1          # 0 floor-level, 1 objects, 2 canopy, 3 DM annotations
    blocks: bool = False    # blocks sight in the VTT export
    light: float = 0        # default light radius (squares) in the VTT export
    dm_only: bool = False
    desc: str = ""


SYMBOLS: dict[str, Sym] = {}


def sym(name, size=(1, 1), layer=1, blocks=False, light=0, dm_only=False, desc="", aliases=()):
    def deco(fn):
        s = Sym(fn, list(size), layer, blocks, light, dm_only, desc or (fn.__doc__ or "").strip())
        SYMBOLS[name] = s
        for a in aliases:
            SYMBOLS[a] = s
        return fn
    return deco


def _rng(f):
    return np.random.default_rng(int(f.get("seed", 1)) * 7919 + 17)


def _flame(p, u, v, r):
    p.circle(u, v, r * 1.8, fill=(255, 160, 60, 50))
    p.circle(u, v, r * 1.25, fill=(255, 170, 70, 90))
    p.circle(u, v, r, fill=FIRE_O)
    p.circle(u - r * 0.1, v - r * 0.1, r * 0.6, fill=FIRE_Y)


# ------------------------------------------------------------ architecture
@sym("stairs", size=(1, 2), layer=0, desc="Stairs; set down: n|s|e|w (side that goes down, drawn darker). size in final orientation.")
def s_stairs(p, f, w, h):
    # Rotation is handled by the renderer (down -> rot); here w x h is local.
    steps = max(3, int(round(h / 0.25)))
    for i in range(steps):
        v0 = -h / 2 + i * h / steps
        t = i / max(1, steps - 1)
        c = tuple(int(a + (b - a) * t) for a, b in ((190, 70), (184, 66), (172, 60)))
        p.rect(-w / 2, v0, w / 2, v0 + h / steps, fill=c, outline=INK, width=0.015)
    p.rect(-w / 2, -h / 2, w / 2, h / 2, outline=INK, width=0.04)


@sym("ladder", size=(0.5, 1), layer=1)
def s_ladder(p, f, w, h):
    """Ladder (rails along h)."""
    for u in (-w / 2 + 0.05, w / 2 - 0.05):
        p.line([(u, -h / 2), (u, h / 2)], fill=WOOD_D, width=0.06)
    n = max(2, int(h / 0.22))
    for i in range(n):
        v = -h / 2 + (i + 0.5) * h / n
        p.line([(-w / 2 + 0.05, v), (w / 2 - 0.05, v)], fill=WOOD, width=0.05)


@sym("pillar", size=(0.8, 0.8), blocks=True, aliases=("column",))
def s_pillar(p, f, w, h):
    """Round stone pillar (blocks sight)."""
    r = w / 2
    p.circle(0, 0, r, fill=STONE_D, outline=INK, width=0.04)
    p.circle(-r * 0.12, -r * 0.12, r * 0.75, fill=STONE)
    p.circle(-r * 0.25, -r * 0.25, r * 0.35, fill=STONE_L)


@sym("pillar_square", size=(0.8, 0.8), blocks=True)
def s_pillar_sq(p, f, w, h):
    """Square stone pillar (blocks sight)."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=STONE_D, outline=INK, width=0.04)
    p.rect(-w / 2 + 0.08, -h / 2 + 0.08, w / 2 - 0.12, h / 2 - 0.12, fill=STONE)


@sym("statue", size=(1, 1), blocks=True)
def s_statue(p, f, w, h):
    """Statue on a plinth."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=STONE_D, outline=INK, width=0.04)
    p.rect(-w / 2 + 0.07, -h / 2 + 0.07, w / 2 - 0.07, h / 2 - 0.07, fill=STONE)
    p.ellipse(0, 0.05, w * 0.34, h * 0.16, fill=STONE_L, outline=INK, width=0.025)
    p.circle(0, -0.02, min(w, h) * 0.13, fill="#c9c4ba", outline=INK, width=0.025)


@sym("rubble", size=(1, 1), layer=0)
def s_rubble(p, f, w, h):
    """Scattered rubble / difficult terrain. count: number of stones."""
    rng = _rng(f)
    n = int(f.get("count", max(6, int(w * h * 9))))
    for _ in range(n):
        u, v = rng.uniform(-w / 2, w / 2), rng.uniform(-h / 2, h / 2)
        r = rng.uniform(0.04, 0.13)
        k = rng.integers(5, 8)
        pts = [(u + r * rng.uniform(0.6, 1.1) * math.cos(2 * math.pi * i / k),
                v + r * rng.uniform(0.6, 1.1) * math.sin(2 * math.pi * i / k)) for i in range(k)]
        g = int(rng.uniform(95, 150))
        p.poly(pts, fill=(g, g - 4, g - 9), outline=INK, width=0.012)


@sym("boulder", size=(1, 1), blocks=True)
def s_boulder(p, f, w, h):
    """Large boulder (blocks sight)."""
    rng = _rng(f)
    k = 11
    pts = [(w / 2 * rng.uniform(0.75, 1.0) * math.cos(2 * math.pi * i / k),
            h / 2 * rng.uniform(0.75, 1.0) * math.sin(2 * math.pi * i / k)) for i in range(k)]
    p.poly(pts, fill="#6d6962", outline=INK, width=0.04)
    p.poly([(u * 0.6 - w * 0.08, v * 0.6 - h * 0.08) for u, v in pts], fill="#8b867e")
    p.poly([(u * 0.25 - w * 0.15, v * 0.25 - h * 0.15) for u, v in pts], fill="#a5a097")


@sym("stalagmite", size=(0.6, 0.6), blocks=True)
def s_stalagmite(p, f, w, h):
    """Stalagmite / rock spire."""
    r = w / 2
    for i, c in enumerate(("#4d4842", "#635d55", "#7b746a", "#958d82")):
        p.circle(-r * 0.08 * i, -r * 0.08 * i, r * (1 - i * 0.22), fill=c, outline=INK if i == 0 else None, width=0.03)


@sym("pit", size=(1, 1), layer=0)
def s_pit(p, f, w, h):
    """Open pit (round)."""
    p.ellipse(0, 0, w / 2, h / 2, fill="#2a2724", outline=INK, width=0.04)
    p.ellipse(0.03, 0.04, w / 2 * 0.8, h / 2 * 0.8, fill="#121110")
    p.ellipse(0.06, 0.07, w / 2 * 0.5, h / 2 * 0.5, fill="#050505")


@sym("trapdoor", size=(1, 1), layer=0)
def s_trapdoor(p, f, w, h):
    """Wooden trapdoor in the floor."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=WOOD, outline=INK, width=0.04)
    for i in range(1, 4):
        u = -w / 2 + i * w / 4
        p.line([(u, -h / 2), (u, h / 2)], fill=WOOD_D, width=0.02)
    for v in (-h / 4, h / 4):
        p.rect(-w / 2 + 0.05, v - 0.04, -w / 2 + 0.3, v + 0.04, fill=IRON)
    p.circle(w / 2 - 0.18, 0, 0.07, outline=IRON, width=0.03)


@sym("well", size=(1.2, 1.2), blocks=False)
def s_well(p, f, w, h):
    """Stone well."""
    r = w / 2
    p.circle(0, 0, r, fill=STONE, outline=INK, width=0.04)
    p.circle(0, 0, r * 0.68, fill="#10202a", outline=INK, width=0.03)
    p.line([(-r, 0), (r, 0)], fill=WOOD_D, width=0.07)


@sym("fountain", size=(2, 2))
def s_fountain(p, f, w, h):
    """Round fountain with basin."""
    r = w / 2
    p.circle(0, 0, r, fill=STONE, outline=INK, width=0.04)
    p.circle(0, 0, r * 0.84, fill="#2d6e92", outline=STONE_D, width=0.03)
    for i in range(3):
        p.circle(0, 0, r * (0.3 + 0.17 * i), outline=(190, 225, 240, 120), width=0.015)
    p.circle(0, 0, r * 0.18, fill=STONE_L, outline=INK, width=0.03)


@sym("magic_circle", size=(3, 3), layer=0)
def s_magic_circle(p, f, w, h):
    """Arcane circle inscribed in the floor. color: line colour."""
    c = f.get("color", "#8f5fe0")
    r = w / 2
    p.circle(0, 0, r, outline=c, width=0.05)
    p.circle(0, 0, r * 0.86, outline=c, width=0.025)
    pts = [(r * 0.86 * math.cos(math.radians(-90 + i * 144)), r * 0.86 * math.sin(math.radians(-90 + i * 144))) for i in range(6)]
    p.line(pts, fill=c, width=0.03)
    for i in range(24):
        a = 2 * math.pi * i / 24
        p.line([(r * 0.88 * math.cos(a), r * 0.88 * math.sin(a)), (r * 0.98 * math.cos(a), r * 0.98 * math.sin(a))], fill=c, width=0.02)


@sym("web", size=(1.5, 1.5), layer=2)
def s_web(p, f, w, h):
    """Spider web."""
    c = (235, 235, 235, 170)
    r = w / 2
    n = 9
    for i in range(n):
        a = 2 * math.pi * i / n
        p.line([(0, 0), (r * math.cos(a), r * math.sin(a))], fill=c, width=0.012)
    for k in range(1, 5):
        rr = r * k / 4.3
        p.line([(rr * math.cos(2 * math.pi * i / n), rr * math.sin(2 * math.pi * i / n)) for i in range(n + 1)], fill=c, width=0.01)


@sym("bridge", size=(1, 3), layer=0)
def s_bridge(p, f, w, h):
    """Plank bridge, planks across w, length h. Use rot to orient."""
    n = max(3, int(h / 0.2))
    for i in range(n):
        v0 = -h / 2 + i * h / n
        p.rect(-w / 2, v0 + 0.01, w / 2, v0 + h / n - 0.01, fill=WOOD if i % 2 else WOOD_L, outline=WOOD_D, width=0.012)
    for u in (-w / 2, w / 2):
        p.line([(u, -h / 2), (u, h / 2)], fill="#5b4632", width=0.05)


@sym("rug", size=(2, 3), layer=0)
def s_rug(p, f, w, h):
    """Rug / carpet. color: main colour."""
    c = f.get("color", "#7c1f24")
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=c, outline="#3a0e10", width=0.03)
    p.rect(-w / 2 + 0.12, -h / 2 + 0.12, w / 2 - 0.12, h / 2 - 0.12, outline=GOLD, width=0.04)
    p.poly([(0, -h / 2 + 0.35), (w / 2 - 0.35, 0), (0, h / 2 - 0.35), (-w / 2 + 0.35, 0)], outline=GOLD, width=0.03)


# ------------------------------------------------------------ furniture
@sym("table", size=(2, 1))
def s_table(p, f, w, h):
    """Rectangular table."""
    p.rrect(-w / 2, -h / 2, w / 2, h / 2, r=0.06, fill=WOOD, outline=INK, width=0.035)
    p.rrect(-w / 2 + 0.07, -h / 2 + 0.07, w / 2 - 0.07, h / 2 - 0.07, r=0.04, fill=WOOD_L)
    for i in range(1, int(h / 0.25)):
        v = -h / 2 + i * 0.25
        p.line([(-w / 2 + 0.07, v), (w / 2 - 0.07, v)], fill=WOOD, width=0.01)


@sym("round_table", size=(1.5, 1.5))
def s_round_table(p, f, w, h):
    """Round table."""
    p.circle(0, 0, w / 2, fill=WOOD, outline=INK, width=0.035)
    p.circle(0, 0, w / 2 - 0.07, fill=WOOD_L)


@sym("chair", size=(0.5, 0.5))
def s_chair(p, f, w, h):
    """Chair (back towards -v / north at rot 0)."""
    p.rect(-w / 2, -h / 2 + 0.1, w / 2, h / 2, fill=WOOD_L, outline=INK, width=0.025)
    p.rect(-w / 2, -h / 2, w / 2, -h / 2 + 0.12, fill=WOOD_D, outline=INK, width=0.025)


@sym("bench", size=(2, 0.4))
def s_bench(p, f, w, h):
    """Bench."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=WOOD, outline=INK, width=0.03)


@sym("bed", size=(1, 2))
def s_bed(p, f, w, h):
    """Bed (pillow towards -v / north at rot 0). color: blanket."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=WOOD_D, outline=INK, width=0.035)
    p.rect(-w / 2 + 0.06, -h / 2 + 0.06, w / 2 - 0.06, h / 2 - 0.06, fill="#e8e2d4")
    p.rrect(-w / 2 + 0.12, -h / 2 + 0.1, w / 2 - 0.12, -h / 2 + 0.38, r=0.06, fill="#f8f5ee", outline="#9a9488", width=0.015)
    p.rect(-w / 2 + 0.06, -h / 2 + 0.5, w / 2 - 0.06, h / 2 - 0.06, fill=f.get("color", "#3f5f8a"))


@sym("bookshelf", size=(2, 0.5), blocks=False, aliases=("bookcase",))
def s_bookshelf(p, f, w, h):
    """Bookshelf (books face +v / south at rot 0)."""
    rng = _rng(f)
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=WOOD_D, outline=INK, width=0.035)
    u = -w / 2 + 0.05
    cols = ["#7a2a24", "#2e4c6e", "#3b5e34", "#8a6d2c", "#5a3a6b", "#6b5a4a"]
    while u < w / 2 - 0.08:
        bw = rng.uniform(0.05, 0.11)
        p.rect(u, -h / 2 + 0.07, min(u + bw, w / 2 - 0.05), h / 2 - 0.05, fill=cols[rng.integers(len(cols))])
        u += bw + 0.01


@sym("chest", size=(0.8, 0.55))
def s_chest(p, f, w, h):
    """Treasure chest (lock faces +v / south)."""
    p.rrect(-w / 2, -h / 2, w / 2, h / 2, r=0.04, fill=WOOD, outline=INK, width=0.035)
    p.line([(-w / 2, -h / 2 + h * 0.4), (w / 2, -h / 2 + h * 0.4)], fill=WOOD_D, width=0.025)
    for u in (-w / 2 + 0.14, w / 2 - 0.14):
        p.rect(u - 0.035, -h / 2, u + 0.035, h / 2, fill=IRON)
    p.rect(-0.06, h / 2 - 0.13, 0.06, h / 2 - 0.01, fill=GOLD, outline=INK, width=0.015)


@sym("crate", size=(0.8, 0.8))
def s_crate(p, f, w, h):
    """Wooden crate."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=WOOD_L, outline=INK, width=0.035)
    p.rect(-w / 2 + 0.08, -h / 2 + 0.08, w / 2 - 0.08, h / 2 - 0.08, outline=WOOD_D, width=0.03)
    p.line([(-w / 2 + 0.08, -h / 2 + 0.08), (w / 2 - 0.08, h / 2 - 0.08)], fill=WOOD_D, width=0.04)


@sym("barrel", size=(0.7, 0.7))
def s_barrel(p, f, w, h):
    """Barrel."""
    r = w / 2
    p.circle(0, 0, r, fill=WOOD, outline=INK, width=0.035)
    p.circle(0, 0, r * 0.82, outline=IRON, width=0.03)
    p.circle(0, 0, r * 0.62, fill=WOOD_L, outline=WOOD_D, width=0.015)
    for k in (-0.2, 0, 0.2):
        p.line([(k * r * 2, -r * 0.6), (k * r * 2, r * 0.6)], fill=WOOD_D, width=0.01)


@sym("sacks", size=(0.8, 0.8))
def s_sacks(p, f, w, h):
    """Pile of sacks."""
    for (u, v) in ((-0.15, -0.1), (0.15, -0.05), (0, 0.15)):
        p.ellipse(u * w * 1.2, v * h * 1.2, w * 0.27, h * 0.22, fill="#b8a179", outline=INK, width=0.02)


@sym("altar", size=(2, 1))
def s_altar(p, f, w, h):
    """Stone altar with cloth and candles. color: cloth."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=STONE, outline=INK, width=0.04)
    p.rect(-w / 2 + 0.06, -h / 2 + 0.06, w / 2 - 0.06, h / 2 - 0.06, fill=STONE_L)
    p.rect(-w * 0.18, -h / 2, w * 0.18, h / 2, fill=f.get("color", "#7c1f24"))
    for u in (-w / 2 + 0.2, w / 2 - 0.2):
        _flame(p, u, -h / 2 + 0.2, 0.05)


@sym("throne", size=(1, 1))
def s_throne(p, f, w, h):
    """Throne (back towards -v / north at rot 0)."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill="#5b3d22", outline=INK, width=0.035)
    p.rect(-w / 2, -h / 2, w / 2, -h / 2 + 0.25, fill=GOLD, outline=INK, width=0.025)
    p.rect(-w / 2 + 0.15, -h / 2 + 0.25, w / 2 - 0.15, h / 2 - 0.05, fill="#7c1f24")
    for u in (-w / 2 + 0.07, w / 2 - 0.07):
        p.line([(u, -h / 2 + 0.25), (u, h / 2)], fill=GOLD, width=0.06)


@sym("sarcophagus", size=(1, 2), aliases=("tomb",))
def s_sarcophagus(p, f, w, h):
    """Stone sarcophagus (head towards -v / north)."""
    pts = [(-w * 0.35, -h / 2), (w * 0.35, -h / 2), (w / 2, -h * 0.25), (w * 0.38, h / 2), (-w * 0.38, h / 2), (-w / 2, -h * 0.25)]
    p.poly(pts, fill=STONE, outline=INK, width=0.04)
    p.poly([(u * 0.78, v * 0.85) for u, v in pts], fill=STONE_L, outline=STONE_D, width=0.02)
    p.line([(0, -h * 0.3), (0, h * 0.3)], fill=STONE_D, width=0.04)
    p.line([(-w * 0.2, -h * 0.12), (w * 0.2, -h * 0.12)], fill=STONE_D, width=0.04)


@sym("coffin", size=(0.8, 1.8))
def s_coffin(p, f, w, h):
    """Wooden coffin."""
    pts = [(-w * 0.3, -h / 2), (w * 0.3, -h / 2), (w / 2, -h * 0.22), (w * 0.3, h / 2), (-w * 0.3, h / 2), (-w / 2, -h * 0.22)]
    p.poly(pts, fill=WOOD_D, outline=INK, width=0.035)
    p.poly([(u * 0.8, v * 0.88) for u, v in pts], fill=WOOD)


@sym("cauldron", size=(0.9, 0.9))
def s_cauldron(p, f, w, h):
    """Iron cauldron. color: contents."""
    r = w / 2
    p.circle(0, 0, r, fill=IRON, outline=INK, width=0.04)
    p.circle(0, 0, r * 0.75, fill=f.get("color", "#5f9a3a"))
    p.circle(-r * 0.2, -r * 0.2, r * 0.15, fill=(255, 255, 255, 90))


@sym("cage", size=(1.5, 1.5))
def s_cage(p, f, w, h):
    """Iron cage."""
    p.rect(-w / 2, -h / 2, w / 2, h / 2, outline=IRON, width=0.06)
    n = max(2, int(w / 0.25))
    for i in range(1, n):
        u = -w / 2 + i * w / n
        p.line([(u, -h / 2), (u, h / 2)], fill=IRON, width=0.025)


@sym("cart", size=(1.2, 2))
def s_cart(p, f, w, h):
    """Cart / wagon (handle towards -v / north)."""
    for v in (-h * 0.2, h * 0.3):
        for u in (-w / 2 - 0.05, w / 2 + 0.05):
            p.rect(u - 0.08, v - 0.25, u + 0.08, v + 0.25, fill=IRON)
    p.rect(-w / 2, -h * 0.4, w / 2, h / 2, fill=WOOD, outline=INK, width=0.035)
    p.line([(0, -h * 0.4), (0, -h / 2 - 0.2)], fill=WOOD_D, width=0.07)


@sym("tent", size=(2, 2))
def s_tent(p, f, w, h):
    """Tent seen from above. color: canvas."""
    c = f.get("color", "#cdbb92")
    p.poly([(-w / 2, -h / 2), (0, -h / 2), (0, h / 2), (-w / 2, h / 2)], fill=c, outline=INK, width=0.035)
    p.poly([(0, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (0, h / 2)], fill="#a8966e", outline=INK, width=0.035)
    p.line([(0, -h / 2), (0, h / 2)], fill=INK, width=0.04)


@sym("weapon_stand", size=(0.8, 0.8))
def s_weapon_stand(p, f, w, h):
    """Weapon stand / rack holding a sword. color: blade glow (e.g. a magic weapon)."""
    glow = f.get("color")
    if glow:
        p.circle(0, 0, w * 0.55, fill=glow + "55" if len(glow) == 7 else glow)
    p.rect(-w / 2, -0.08, w / 2, 0.08, fill=WOOD_D, outline=INK, width=0.025)
    for u in (-w / 2 + 0.06, w / 2 - 0.06):
        p.rect(u - 0.06, -0.14, u + 0.06, 0.14, fill=WOOD, outline=INK, width=0.02)
    p.poly([(-w * 0.42, -0.03), (w * 0.3, -0.03), (w * 0.42, 0), (w * 0.3, 0.03), (-w * 0.42, 0.03)], fill="#dfe6ee", outline=INK, width=0.012)
    p.rect(-w * 0.42, -0.12, -w * 0.38, 0.12, fill=GOLD, outline=INK, width=0.01)


@sym("tapestry", size=(2, 0.25))
def s_tapestry(p, f, w, h):
    """Wall hanging; place against a wall, long side along it. color: cloth."""
    c = f.get("color", "#6b2a7a")
    p.rect(-w / 2, -h / 2, w / 2, h / 2, fill=c, outline=INK, width=0.025)
    p.line([(-w / 2, -h / 2 + 0.04), (w / 2, -h / 2 + 0.04)], fill=GOLD, width=0.035)
    n = max(3, int(w / 0.15))
    for i in range(n + 1):
        u = -w / 2 + i * w / n
        p.line([(u, h / 2), (u, h / 2 + 0.06)], fill=GOLD, width=0.015)


# ------------------------------------------------------------ nature
@sym("tree", size=(2, 2), layer=2, aliases=("tree_canopy",))
def s_tree(p, f, w, h):
    """Tree canopy. color: foliage."""
    rng = _rng(f)
    base = f.get("color", "#3d6b2a")
    r = w / 2
    p.circle(0, 0, r, fill="#2a4a1c", outline=INK, width=0.03)
    for _ in range(7):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.45)
        p.circle(d * math.cos(a), d * math.sin(a), r * rng.uniform(0.35, 0.55), fill=base)
    for _ in range(5):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.4)
        p.circle(d * math.cos(a) - r * 0.1, d * math.sin(a) - r * 0.1, r * rng.uniform(0.15, 0.3), fill="#5a8c3a")


@sym("bush", size=(1, 1), layer=1)
def s_bush(p, f, w, h):
    """Bush / shrub."""
    rng = _rng(f)
    r = w / 2
    for _ in range(6):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.45)
        p.circle(d * math.cos(a), d * math.sin(a), r * rng.uniform(0.35, 0.55), fill="#355e24", outline=INK, width=0.02)
    for _ in range(4):
        a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.4)
        p.circle(d * math.cos(a), d * math.sin(a), r * 0.2, fill="#4f7f33")


@sym("mushrooms", size=(0.8, 0.8))
def s_mushrooms(p, f, w, h):
    """Cluster of mushrooms. color: caps."""
    rng = _rng(f)
    c = f.get("color", "#9c4a8a")
    for _ in range(4):
        u, v = rng.uniform(-w / 3, w / 3), rng.uniform(-h / 3, h / 3)
        r = rng.uniform(0.1, 0.18)
        p.circle(u, v, r, fill=c, outline=INK, width=0.02)
        p.circle(u - r * 0.3, v - r * 0.3, r * 0.2, fill=(255, 255, 255, 180))


@sym("crystals", size=(0.8, 0.8))
def s_crystals(p, f, w, h):
    """Crystal cluster. color: crystal colour."""
    rng = _rng(f)
    c = f.get("color", "#7fd3e8")
    for _ in range(5):
        a = rng.uniform(0, 2 * math.pi)
        L, t = rng.uniform(0.2, 0.4) * w, 0.06
        ca, sa = math.cos(a), math.sin(a)
        pts = [(0, 0), (L * 0.7 * ca - t * sa, L * 0.7 * sa + t * ca), (L * ca, L * sa), (L * 0.7 * ca + t * sa, L * 0.7 * sa - t * ca)]
        p.poly(pts, fill=c, outline=INK, width=0.015)


@sym("bones", size=(0.8, 0.8), layer=0)
def s_bones(p, f, w, h):
    """Scattered bones and a skull."""
    rng = _rng(f)
    for _ in range(4):
        u, v, a = rng.uniform(-w / 3, w / 3), rng.uniform(-h / 3, h / 3), rng.uniform(0, math.pi)
        L = rng.uniform(0.12, 0.22)
        p.line([(u - L * math.cos(a), v - L * math.sin(a)), (u + L * math.cos(a), v + L * math.sin(a))], fill="#e6dfcc", width=0.04)
    p.circle(w * 0.15, -h * 0.1, 0.1, fill="#eee8d6", outline=INK, width=0.015)
    for du in (-0.035, 0.035):
        p.circle(w * 0.15 + du, -h * 0.1, 0.022, fill=INK)


# ------------------------------------------------------------ light sources
@sym("torch", size=(0.5, 0.5), light=4)
def s_torch(p, f, w, h):
    """Wall torch; rot 0 = mounted on a wall to its north (rot 90 east, 180 south, 270 west). Light 4."""
    p.rect(-0.05, -h / 2, 0.05, 0.05, fill=IRON, outline=INK, width=0.015)
    _flame(p, 0, 0.06, w * 0.2)


@sym("candles", size=(0.4, 0.4), light=2)
def s_candles(p, f, w, h):
    """A few candles (light 2)."""
    for u, v in ((-0.1, 0.05), (0.08, -0.06), (0.1, 0.1)):
        p.circle(u, v, 0.045, fill="#f1ead2", outline=INK, width=0.01)
        _flame(p, u, v, 0.025)


@sym("brazier", size=(0.8, 0.8), light=4)
def s_brazier(p, f, w, h):
    """Brazier (light 4)."""
    r = w / 2
    p.circle(0, 0, r, fill=IRON, outline=INK, width=0.04)
    p.circle(0, 0, r * 0.75, fill="#5a1b08")
    _flame(p, 0, 0, r * 0.5)


@sym("campfire", size=(1, 1), light=6, aliases=("firepit",))
def s_campfire(p, f, w, h):
    """Campfire ringed with stones (light 6)."""
    r = w / 2
    for i in range(9):
        a = 2 * math.pi * i / 9
        p.circle(r * 0.8 * math.cos(a), r * 0.8 * math.sin(a), r * 0.18, fill=STONE, outline=INK, width=0.02)
    p.line([(-r * 0.5, -r * 0.3), (r * 0.5, r * 0.3)], fill=WOOD_D, width=0.09)
    p.line([(-r * 0.5, r * 0.3), (r * 0.5, -r * 0.3)], fill=WOOD_D, width=0.09)
    _flame(p, 0, 0, r * 0.35)


# ------------------------------------------------------------ DM annotations
@sym("trap", size=(1, 1), layer=3, dm_only=True)
def s_trap(p, f, w, h):
    """Trap marker (DM only). label: short text, default 'T'."""
    red = "#c4161c"
    lab = str(f.get("label", "T"))
    p.rect(-w / 2 + 0.05, -h / 2 + 0.05, w / 2 - 0.05, h / 2 - 0.05, outline=red, width=0.05)
    size = min(w, h) * (0.5 if len(lab) <= 1 else 0.85 / len(lab))
    p.text(0, 0, lab, size=size, fill=red, stroke="white", stroke_w=0.03)


@sym("marker", size=(0.6, 0.6), layer=3, dm_only=True)
def s_marker(p, f, w, h):
    """Lettered marker for encounters/notes (DM only). label, color."""
    p.circle(0, 0, w / 2, fill=f.get("color", "#c4161c"), outline="white", width=0.05)
    lab = str(f.get("label", "!"))
    p.text(0, 0.01, lab, size=w * (0.6 if len(lab) <= 1 else 0.85 / len(lab)), fill="white")
