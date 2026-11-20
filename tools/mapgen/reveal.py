"""Reveal pieces: cut-outs of a map's hidden areas, for printed play.

On the player map the `hidden` areas are left out (blank rock). A reveal piece is
that region drawn as the party finds it: hidden rooms and passages shown, secret
doors drawn as ordinary doors, no DM annotations. It is cropped to the hidden
region plus a small margin and outlined with a dashed cut line. Printed at the
same scale as the player map, it lies on top of the blank rock and lines up with
the squares, so the DM can put it down when the secret is discovered.

Separate hidden regions (e.g. two secret rooms in different wings) become
separate pieces.
"""
from __future__ import annotations

import copy
import math

from PIL import Image, ImageDraw
from shapely.geometry import Polygon, box

from .draw import font, mask
from .geometry import Model, area_shape, polygons

CUT_MARGIN = 0.3   # squares of margin beyond the wall's outer edge


def revealed_spec(spec: dict) -> dict:
    """The map as it looks once every secret is found (render it as 'player')."""
    s = copy.deepcopy(spec)
    for key in ("areas", "walls", "doors", "features", "labels"):
        for item in s.get(key, []):
            if isinstance(item, dict) and "hidden" in item:
                item["hidden"] = False
    for d in s.get("doors", []):
        if d["type"] == "secret":
            d["type"] = "door"
    return s


def regions(spec: dict) -> list[dict]:
    """Hidden regions of the player map, one per piece, top-left first."""
    model = Model(spec, "player")
    hr = model.hidden_region
    if hr.is_empty:
        return []
    meta = spec["meta"]
    W, H = meta["size"]
    grown = hr.buffer(float(meta["wall_width"]) / 2 + CUT_MARGIN, join_style="mitre")
    grown = grown.intersection(box(0, 0, W, H))
    seed = int(meta["seed"])
    shapes = [(a, area_shape(a, seed * 1000 + i)) for i, a in enumerate(spec["areas"])]
    out = []
    # Holes are filled (rock inside a ring of passages): nobody wants to cut a hole
    # out of paper, and the rock there looks the same on both prints.
    solid = [Polygon(g.exterior) for g in polygons(grown)]
    for g in sorted(solid, key=lambda g: (g.bounds[1], g.bounds[0])):
        inside = [a for a, sh in shapes if a["hidden"] and sh.intersects(g)]
        keyed = [f"{a['id']} {a.get('name', '')}".strip() for a in inside if a.get("id") is not None]
        names = keyed or [a.get("name", "hidden area") for a in inside[:1]]
        out.append({"geom": g, "name": ", ".join(names) or "hidden area"})
    return out


def _dashed(draw: ImageDraw.ImageDraw, pts, width: int, dash: float, fill):
    """Draw a closed dashed polyline (pixel coordinates)."""
    on, carry = True, dash
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while pos < seg - 1e-9:
            step = min(carry, seg - pos)
            if on:
                a, b = pos / seg, (pos + step) / seg
                draw.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a),
                           (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=fill, width=width)
            pos += step
            carry -= step
            if carry <= 1e-9:
                on, carry = not on, dash


def pieces(spec: dict, img: Image.Image, blank_rock: bool = False) -> list[dict]:
    """Cut the reveal pieces out of `img` (a render of `revealed_spec(spec)`).

    Returns dicts with: name, image (RGBA, transparent outside the cut line),
    squares (c0, r0, c1, r1) = the grid squares the image covers, ppg.
    With blank_rock, rock inside the cut line is white (matches the print PDF)."""
    meta = spec["meta"]
    gw, gh = meta["size"]
    ppg = img.width / gw
    base = img.convert("RGB")
    if blank_rock:
        from .textures import NON_WALKABLE_BG
        if meta["background"] in NON_WALKABLE_BG:
            full = Model(revealed_spec(spec), "player")
            keep = mask(full.floor.buffer(float(meta["wall_width"]) * 0.6), img.width, img.height, ppg)
            base = Image.composite(base, Image.new("RGB", base.size, "white"), keep)
    out = []
    for r in regions(spec):
        g = r["geom"]
        minx, miny, maxx, maxy = g.bounds
        c0, r0 = max(0, math.floor(minx)), max(0, math.floor(miny))
        c1, r1 = min(gw, math.ceil(maxx)), min(gh, math.ceil(maxy))
        px = (int(c0 * ppg), int(r0 * ppg), int(c1 * ppg), int(r1 * ppg))
        alpha = mask(g, img.width, img.height, ppg).crop(px)
        piece = base.crop(px).convert("RGBA")
        piece.putalpha(alpha)
        d = ImageDraw.Draw(piece)
        lw = max(2, int(ppg * 0.025))
        for poly in polygons(g.buffer(-lw / ppg / 2, join_style="mitre")):
            for ring in [poly.exterior, *poly.interiors]:
                pts = [((x - c0) * ppg, (y - r0) * ppg) for x, y in ring.coords]
                _dashed(d, pts, lw, ppg * 0.12, (90, 90, 90, 255))
        out.append({"name": r["name"], "image": piece, "squares": (c0, r0, c1, r1), "ppg": ppg})
    return out


def sheet(spec: dict, plist: list[dict]) -> Image.Image:
    """All pieces side by side on one transparent PNG, each with a caption."""
    ppg = plist[0]["ppg"]
    pad = int(ppg * 0.3)
    cap = int(ppg * 0.45)
    f = font(int(ppg * 0.22), bold=False, family="sans")
    W = sum(p["image"].width for p in plist) + pad * (len(plist) + 1)
    H = max(p["image"].height for p in plist) + cap + pad * 2
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    x = pad
    for i, p in enumerate(plist, 1):
        c0, r0, c1, r1 = p["squares"]
        label = f"Reveal {i}: {p['name']}  (squares x{c0}–{c1 - 1}, y{r0}–{r1 - 1})"
        d.text((x, pad), label, font=f, fill=(40, 40, 40, 255))
        out.alpha_composite(p["image"], (x, pad + cap))
        x += p["image"].width + pad
    return out
