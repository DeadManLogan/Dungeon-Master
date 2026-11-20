"""Low-level raster helpers: anti-aliased masks, a rotating 'Pen', fonts."""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .geometry import polygons

LANCZOS = Image.Resampling.LANCZOS


@lru_cache(maxsize=64)
def font(px: int, bold: bool = True, family: str = "georgia"):
    names = {
        ("georgia", True): ["georgiab.ttf", "Georgia Bold.ttf", "DejaVuSerif-Bold.ttf"],
        ("georgia", False): ["georgia.ttf", "Georgia.ttf", "DejaVuSerif.ttf"],
        ("sans", True): ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"],
        ("sans", False): ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"],
    }[(family, bold)]
    for n in names:
        try:
            return ImageFont.truetype(n, max(6, int(px)))
        except OSError:
            continue
    return ImageFont.load_default(max(6, int(px)))


def mask(geom, W: int, H: int, ppg: float, ss: int = 3) -> Image.Image:
    """Rasterise polygonal geometry into an anti-aliased L mask (W x H px)."""
    out = Image.new("L", (W, H), 0)
    if geom is None or geom.is_empty:
        return out
    for poly in polygons(geom):
        minx, miny, maxx, maxy = poly.bounds
        x0 = max(0, int(math.floor(minx * ppg)) - 1)
        y0 = max(0, int(math.floor(miny * ppg)) - 1)
        x1 = min(W, int(math.ceil(maxx * ppg)) + 1)
        y1 = min(H, int(math.ceil(maxy * ppg)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        loc = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss), 0)
        d = ImageDraw.Draw(loc)

        def tr(coords):
            return [((x * ppg - x0) * ss, (y * ppg - y0) * ss) for x, y in coords]

        d.polygon(tr(poly.exterior.coords), fill=255)
        for r in poly.interiors:
            d.polygon(tr(r.coords), fill=0)
        loc = loc.resize((x1 - x0, y1 - y0), Image.Resampling.BOX)
        region = out.crop((x0, y0, x1, y1))
        out.paste(ImageChops.lighter(region, loc), (x0, y0))
    return out


def paste_rgba(canvas: Image.Image, img: Image.Image, x: int, y: int):
    """alpha_composite that tolerates negative / out-of-bounds offsets."""
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    w = min(img.width - sx0, canvas.width - dx0)
    h = min(img.height - sy0, canvas.height - dy0)
    if w <= 0 or h <= 0:
        return
    canvas.alpha_composite(img.crop((sx0, sy0, sx0 + w, sy0 + h)), (dx0, dy0))


class Pen:
    """Draw in symbol-local units (squares), rotated and placed on the map.

    (u, v) are offsets in squares from the symbol centre; rotation is applied
    so symbol code never worries about orientation. Rendered supersampled and
    downsampled for anti-aliasing.
    """

    def __init__(self, at, rot_deg: float, extent: float, ppg: int, ss: int = 4):
        self.cx, self.cy = at
        self.ppg, self.ss = ppg, ss
        r = math.radians(rot_deg)
        self.c, self.s = math.cos(r), math.sin(r)
        self.ox = int(math.floor((self.cx - extent) * ppg))
        self.oy = int(math.floor((self.cy - extent) * ppg))
        w = int(math.ceil((self.cx + extent) * ppg)) - self.ox
        h = int(math.ceil((self.cy + extent) * ppg)) - self.oy
        self.size = (max(1, w), max(1, h))
        self.img = Image.new("RGBA", (self.size[0] * ss, self.size[1] * ss), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img, "RGBA")  # blend semi-transparent ink
        self.k = ppg * ss

    def P(self, u, v):
        x = self.cx + u * self.c - v * self.s
        y = self.cy + u * self.s + v * self.c
        return ((x * self.ppg - self.ox) * self.ss, (y * self.ppg - self.oy) * self.ss)

    def W(self, w):
        return max(1, int(round(w * self.k)))

    def poly(self, pts, fill=None, outline=None, width=0.03):
        P = [self.P(u, v) for u, v in pts]
        if fill:
            self.d.polygon(P, fill=fill)
        if outline:
            self.d.line(P + [P[0], P[1]], fill=outline, width=self.W(width), joint="curve")

    def rect(self, u0, v0, u1, v1, **kw):
        self.poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], **kw)

    def rrect(self, u0, v0, u1, v1, r=0.08, n=6, **kw):
        pts = []
        for (cu, cv, a0) in ((u1 - r, v0 + r, -90), (u1 - r, v1 - r, 0), (u0 + r, v1 - r, 90), (u0 + r, v0 + r, 180)):
            for i in range(n + 1):
                a = math.radians(a0 + 90 * i / n)
                pts.append((cu + r * math.cos(a), cv + r * math.sin(a)))
        self.poly(pts, **kw)

    def ellipse(self, u, v, ru, rv=None, n=40, **kw):
        rv = ru if rv is None else rv
        pts = [(u + ru * math.cos(2 * math.pi * i / n), v + rv * math.sin(2 * math.pi * i / n)) for i in range(n)]
        self.poly(pts, **kw)

    circle = ellipse

    def line(self, pts, fill="#1a1a1a", width=0.03):
        self.d.line([self.P(u, v) for u, v in pts], fill=fill, width=self.W(width), joint="curve")

    def text(self, u, v, txt, size=0.5, fill="#1a1a1a", stroke=None, stroke_w=0.05, bold=True):
        f = font(int(size * self.k), bold)
        kw = {}
        if stroke:
            kw = {"stroke_width": self.W(stroke_w), "stroke_fill": stroke}
        self.d.text(self.P(u, v), txt, font=f, fill=fill, anchor="mm", **kw)

    def finish(self):
        return self.img.resize(self.size, LANCZOS)


def stamp(canvas: Image.Image, pen: Pen, shadow: float = 0.5):
    img = pen.finish()
    if shadow > 0:
        a = img.getchannel("A").filter(ImageFilter.GaussianBlur(max(1, pen.ppg * 0.035)))
        a = a.point(lambda v: int(v * shadow))
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sh.putalpha(a)
        off = max(1, int(pen.ppg * 0.04))
        paste_rgba(canvas, sh, pen.ox + off, pen.oy + off)
    paste_rgba(canvas, img, pen.ox, pen.oy)
