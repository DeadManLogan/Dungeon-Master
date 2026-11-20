"""Compose a map image from a spec.

Variants
  dm      everything: room numbers, secret doors, traps, DM labels, hidden areas
  player  handout: no DM annotations, `hidden` areas/doors/features removed
  vtt     VTT upload: like player but keeps hidden areas (fog of war hides them),
          and normally rendered without a grid (the VTT draws its own).
          NOT for printing: it shows the secret rooms.
Reveal pieces (the hidden areas as found, for printed play) are built in reveal.py.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import textures
from .draw import Pen, font, mask, stamp
from .geometry import Model, door_angle
from .symbols import INK, IRON, SYMBOLS, WOOD, WOOD_D, GOLD

STAIRS_ROT = {"s": 0, "n": 180, "e": -90, "w": 90}


def _paint(canvas: Image.Image, geom, floor: str, ppg: int, seed: int, style: str):
    if geom.is_empty:
        return
    W, H = canvas.size
    m = mask(geom, W, H, ppg)
    bbox = m.getbbox()
    if not bbox:
        return
    x0, y0, x1, y1 = bbox
    t = textures.tile(floor, ppg, seed, style)
    tex = Image.new("RGB", (x1 - x0, y1 - y0))
    sx, sy = x0 - x0 % t.width, y0 - y0 % t.height
    for y in range(sy, y1, t.height):
        for x in range(sx, x1, t.width):
            tex.paste(t, (x - x0, y - y0))
    region = canvas.crop(bbox)
    canvas.paste(Image.composite(tex, region, m.crop(bbox)), (x0, y0))


def _darken(canvas: Image.Image, m: Image.Image, strength: float):
    a = np.asarray(canvas).astype(np.float32)
    k = np.asarray(m).astype(np.float32)[..., None] / 255.0
    a *= 1 - strength * k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), canvas.mode)


def _over(canvas: Image.Image, color, alpha: Image.Image):
    solid = Image.new(canvas.mode, canvas.size, color)
    return Image.composite(solid, canvas, alpha)


def _visible(item, variant):
    if variant != "dm" and item.get("dm_only"):
        return False
    if variant == "player" and item.get("hidden"):
        return False
    return True


def _feature(canvas, f, ppg):
    s = SYMBOLS[f["type"]]
    w, h = f["size"]
    rot = f.get("rot", 0)
    if f["type"] == "stairs":
        rot = STAIRS_ROT[f.get("down", "s")]
        if f["down"] in ("e", "w"):
            w, h = h, w
    ext = math.hypot(w, h) / 2 + 0.25
    p = Pen(f["at"], rot, ext, ppg, ss=3)
    s.fn(p, f, w, h)
    stamp(canvas, p, shadow=0.0 if s.layer == 0 else (0.35 if s.layer == 3 else 0.5))


def _door(canvas, d, ppg, variant, wall_w, style):
    x1, y1, x2, y2 = d["seg"]
    L = math.hypot(x2 - x1, y2 - y1)
    mid = ((x1 + x2) / 2, (y1 + y2) / 2)
    p = Pen(mid, math.degrees(door_angle(d)), L / 2 + 0.5, ppg)
    t = max(0.2, wall_w + 0.04)
    typ = d["type"]
    wood, wood_d = (WOOD, WOOD_D) if style == "vtt" else ("#ffffff", INK)
    if typ in ("door", "double", "locked"):
        p.rect(-L / 2 + 0.04, -t / 2, L / 2 - 0.04, t / 2, fill=wood, outline=INK, width=0.035)
        if typ == "double":
            p.line([(0, -t / 2), (0, t / 2)], fill=INK, width=0.03)
        else:
            p.line([(-L / 2 + 0.08, 0), (L / 2 - 0.08, 0)], fill=wood_d, width=0.012)
        if typ == "locked":
            p.circle(0, 0, 0.07, fill=GOLD, outline=INK, width=0.02)
        for u in (-L / 2, L / 2):  # jambs
            p.rect(u - 0.05, -t / 2 - 0.03, u + 0.05, t / 2 + 0.03, fill="#1c1a18")
    elif typ in ("portcullis", "bars"):
        bar = "#9a9aa6" if style == "vtt" else INK
        p.rect(-L / 2, -0.05, L / 2, 0.05, fill=bar, outline=INK, width=0.02)
        n = max(2, int(L / 0.2))
        for i in range(n + 1):
            u = -L / 2 + i * L / n
            p.circle(u, 0, 0.06, fill=bar, outline=INK, width=0.02)
    elif typ == "window":
        p.rect(-L / 2 + 0.03, -t * 0.3, L / 2 - 0.03, t * 0.3, fill="#a9d3e8", outline=INK, width=0.03)
    elif typ == "secret":
        if variant != "dm":
            return
        p.circle(0, 0, 0.24, fill="white", outline="#c4161c", width=0.035)
        p.text(0, 0.01, "S", size=0.34, fill="#c4161c")
    elif typ == "arch":
        return
    stamp(canvas, p, shadow=0.35)


def _room_number(canvas, text, at, ppg, size=0.55):
    w = 0.35 + 0.22 * len(text)
    p = Pen(at, 0, max(w, size) + 0.2, ppg)
    p.rrect(-w / 2, -size / 2, w / 2, size / 2, r=0.1, fill="#fbf8f0", outline=INK, width=0.04)
    p.text(0, 0.01, text, size=size * 0.68, fill=INK)
    stamp(canvas, p, shadow=0.35)


def _label(canvas, lb, ppg):
    txt = str(lb["text"])
    ext = max(1.0, lb["size"] * len(txt) * 0.4 + 0.5)
    p = Pen(lb["at"], 0, ext, ppg)
    p.text(0, 0, txt, size=lb["size"], fill=lb["color"], stroke="#f8f4ea", stroke_w=lb["size"] * 0.1)
    stamp(canvas, p, shadow=0)


def _title(canvas, meta, ppg):
    d = ImageDraw.Draw(canvas)
    f1 = font(int(ppg * 0.5))
    f2 = font(int(ppg * 0.28), bold=False)
    pad = int(ppg * 0.2)
    t = meta["title"]
    sub = meta.get("source") or ""
    w1 = d.textlength(t, font=f1)
    w2 = d.textlength(sub, font=f2) if sub else 0
    w = int(max(w1, w2) + pad * 2)
    h = int(ppg * (0.85 + (0.38 if sub else 0)))
    d.rectangle([pad, pad, pad + w, pad + h], fill=(250, 246, 235, 235), outline=INK, width=max(2, ppg // 30))
    d.text((pad * 2, pad + ppg * 0.15), t, font=f1, fill=INK)
    if sub:
        d.text((pad * 2, pad + ppg * 0.75), sub, font=f2, fill="#444")


def render(spec: dict, variant: str = "dm", grid: bool | None = None, ppg: int | None = None) -> Image.Image:
    meta = spec["meta"]
    ppg = int(ppg or meta["ppg"])
    gw, gh = meta["size"]
    W, H = int(round(gw * ppg)), int(round(gh * ppg))
    style, seed = meta["style"], int(meta["seed"])
    if grid is None:
        grid = variant != "vtt"
    model = Model(spec, variant)

    canvas = textures.fill(meta["background"], W, H, ppg, seed, style)
    for a, g in [x for x in model.areas if not x[0]["cut"]] + [x for x in model.areas if x[0]["cut"]]:
        _paint(canvas, g, a["floor"], ppg, seed, style)

    ww = float(meta["wall_width"])
    wall_poly = model.walls.buffer(ww / 2, cap_style="round", join_style="round") if not model.walls.is_empty else None
    wall_m = mask(wall_poly, W, H, ppg) if wall_poly is not None else Image.new("L", (W, H), 0)

    # ambient occlusion along walls
    ao = wall_m.filter(ImageFilter.GaussianBlur(ppg * 0.22))
    canvas = _darken(canvas, ao, 0.6 if style == "vtt" else 0.25)

    # grid
    mode = meta["grid_on"]
    if mode == "auto":
        mode = "floor" if meta["background"] in textures.NON_WALKABLE_BG else "all"
    if grid and mode != "none":
        g = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(g)
        lw = max(1, ppg // 60)
        for i in range(int(gw) + 1):
            d.line([(i * ppg, 0), (i * ppg, H)], fill=255, width=lw)
        for j in range(int(gh) + 1):
            d.line([(0, j * ppg), (W, j * ppg)], fill=255, width=lw)
        alpha = 0.28 if style == "vtt" else 0.55
        g = g.point(lambda v: int(v * alpha))
        if mode == "floor":
            from PIL import ImageChops
            g = ImageChops.multiply(g, mask(model.floor, W, H, ppg))
        canvas = _over(canvas, (20, 18, 16) if style == "vtt" else (120, 120, 120), g)

    canvas = canvas.convert("RGBA")
    feats = [f for f in spec["features"] if _visible(f, variant) and not model.in_hidden(f["at"])]
    for f in [f for f in feats if SYMBOLS[f["type"]].layer == 0]:
        _feature(canvas, f, ppg)

    # walls (with a soft outer shadow)
    if wall_poly is not None:
        sh = wall_m.filter(ImageFilter.GaussianBlur(ppg * 0.05)).point(lambda v: int(v * 0.6))
        canvas = _over(canvas, (0, 0, 0, 255), sh)
        canvas = _over(canvas, (28, 26, 24, 255) if style == "vtt" else (17, 17, 17, 255), wall_m)

    for d in model.doors:
        _door(canvas, d, ppg, variant, ww, style)

    for layer in (1, 2, 3):
        for f in [f for f in feats if SYMBOLS[f["type"]].layer == layer]:
            _feature(canvas, f, ppg)

    show_numbers = variant == "dm" or (variant == "player" and meta["player_numbers"])
    if show_numbers:
        for a, g in model.areas:
            if a.get("id") is None or a["cut"]:
                continue
            at = a.get("label_at")
            if at is None:
                c = g.centroid
                c = c if g.contains(c) else g.representative_point()
                at = (c.x, c.y)
            _room_number(canvas, str(a["id"]), at, ppg)

    for lb in spec["labels"]:
        if _visible(lb, variant) and not model.in_hidden(lb["at"]):
            _label(canvas, lb, ppg)

    if variant == "dm" and meta["show_title"]:
        _title(canvas, meta, ppg)

    return canvas.convert("RGB")


def preview(img: Image.Image, spec: dict, max_px: int = 2000) -> Image.Image:
    """Downscaled DM render with coordinate rulers, for checking placement."""
    gw, gh = spec["meta"]["size"]
    scale = min(1.0, max_px / max(img.size))
    small = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    cell = small.width / gw
    m = 28
    out = Image.new("RGB", (small.width + m * 2, small.height + m * 2), (245, 242, 235))
    out.paste(small, (m, m))
    d = ImageDraw.Draw(out, "RGBA")
    f = font(13, bold=True, family="sans")
    step = 1 if cell >= 26 else 2 if cell >= 13 else 5
    for i in range(0, int(gw) + 1):
        x = m + i * cell
        if i % 5 == 0:
            d.line([(x, m), (x, m + small.height)], fill=(220, 30, 30, 110), width=1)
        if i % step == 0 and i < gw:
            for y in (m / 2, m + small.height + m / 2):
                d.text((x + cell / 2, y), str(i), font=f, fill=(150, 20, 20) if i % 5 == 0 else (60, 60, 60), anchor="mm")
    for j in range(0, int(gh) + 1):
        y = m + j * cell
        if j % 5 == 0:
            d.line([(m, y), (m + small.width, y)], fill=(220, 30, 30, 110), width=1)
        if j % step == 0 and j < gh:
            for x in (m / 2, m + small.width + m / 2):
                d.text((x, y + cell / 2), str(j), font=f, fill=(150, 20, 20) if j % 5 == 0 else (60, 60, 60), anchor="mm")
    return out
