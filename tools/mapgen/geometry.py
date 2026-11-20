"""Turn a spec into shapely geometry: floors, walls, door cuts."""
from __future__ import annotations

import math

import numpy as np
from shapely import affinity
from shapely.geometry import (GeometryCollection, LineString, MultiLineString,
                              MultiPolygon, Point, Polygon, box)
from shapely.ops import linemerge, unary_union

EMPTY = GeometryCollection()


def polygons(g):
    """Yield Polygon parts of any geometry."""
    if g is None or g.is_empty:
        return
    if isinstance(g, Polygon):
        yield g
    elif hasattr(g, "geoms"):
        for p in g.geoms:
            yield from polygons(p)


def lines(g):
    """Yield LineString parts of any geometry (rings become closed lines)."""
    if g is None or g.is_empty:
        return
    if isinstance(g, LineString):
        yield LineString(g.coords)
    elif isinstance(g, Polygon):
        yield LineString(g.exterior.coords)
        for r in g.interiors:
            yield LineString(r.coords)
    elif hasattr(g, "geoms"):
        for p in g.geoms:
            yield from lines(p)


def _rough_ring(coords, amount, rng, step=0.3):
    ring = LineString(coords)
    L = ring.length
    n = max(12, int(L / step))
    pts = np.array([ring.interpolate(i * L / n).coords[0] for i in range(n)])
    # smooth circular noise: large wobble + fine jitter
    big = rng.standard_normal(n)
    k = max(3, int(1.2 / step))
    kern = np.hanning(2 * k + 1)
    kern /= kern.sum()
    big = np.real(np.fft.ifft(np.fft.fft(big) * np.fft.fft(np.pad(kern, (0, n - len(kern))) if n > len(kern) else kern[:n])))
    big = big / (big.std() + 1e-9)
    fine = rng.standard_normal(n) * 0.35
    disp = (big + fine) * amount
    prev = np.roll(pts, 1, axis=0)
    nxt = np.roll(pts, -1, axis=0)
    t = nxt - prev
    nrm = np.stack([-t[:, 1], t[:, 0]], axis=1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
    out = pts + nrm * disp[:, None]
    return [tuple(p) for p in out]


def roughen(g, amount, rng):
    if amount <= 0:
        return g
    parts = []
    for p in polygons(g):
        ext = _rough_ring(p.exterior.coords, amount, rng)
        holes = [_rough_ring(r.coords, amount, rng) for r in p.interiors]
        parts.append(Polygon(ext, holes).buffer(0))
    return unary_union(parts) if parts else g


def area_shape(a: dict, seed: int):
    s = a["shape"]
    v = a[s]
    if s == "rect":
        x, y, w, h = v
        g = box(x, y, x + w, y + h)
    elif s == "poly":
        g = Polygon(v).buffer(0)
    elif s == "circle":
        cx, cy, r = v
        g = Point(cx, cy).buffer(r, quad_segs=24)
    elif s == "ellipse":
        cx, cy, rx, ry = v
        g = affinity.scale(Point(cx, cy).buffer(1, quad_segs=24), rx, ry)
    elif s == "path":
        g = LineString(v).buffer(a["width"] / 2, cap_style="flat", join_style="mitre", mitre_limit=3)
    else:  # pragma: no cover
        raise ValueError(s)
    if a.get("rough"):
        rng = np.random.default_rng(a.get("seed", seed))
        g = roughen(g, float(a["rough"]), rng)
    return g


def seg_line(d):
    x1, y1, x2, y2 = d["seg"]
    return LineString([(x1, y1), (x2, y2)])


class Model:
    """All derived geometry for one variant of a map."""

    def __init__(self, spec: dict, variant: str = "dm"):
        self.spec = spec
        self.variant = variant
        meta = spec["meta"]
        seed = int(meta["seed"])
        W, H = meta["size"]
        self.bounds = box(0, 0, W, H)
        hide = variant == "player"   # player handout hides 'hidden' things; VTT keeps them (fog handles it)

        self.areas = []
        hidden = []
        for i, a in enumerate(spec["areas"]):
            g = area_shape(a, seed * 1000 + i)
            if hide and a["hidden"]:
                hidden.append(g)
                continue
            self.areas.append((a, g))

        walled = [g for a, g in self.areas if a["walls"] and not a["cut"]]
        cuts = [g for a, g in self.areas if a["cut"]]
        cut_u = unary_union(cuts) if cuts else EMPTY
        self.walkable = unary_union(walled).difference(cut_u) if walled else EMPTY
        floors = [g for a, g in self.areas if not a["cut"]]
        self.floor = unary_union(floors).difference(cut_u) if floors else EMPTY
        # region removed from this variant (hidden areas not overlapped by visible floor)
        self.hidden_region = unary_union(hidden).difference(self.floor) if hidden else EMPTY

        wall_parts = [self.walkable.boundary] if not self.walkable.is_empty else []
        # Numbered rooms that touch/overlap are separated by a wall along the
        # shared edge (unnumbered areas like corridors merge freely; merge: true opts out).
        rooms = [(a, g) for a, g in self.areas
                 if a["walls"] and not a["cut"] and a.get("id") is not None and not a.get("merge")]
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                gi, gj = rooms[i][1], rooms[j][1]
                if gi.intersects(gj):
                    shared = gi.boundary.intersection(gj).difference(cut_u)
                    if shared.length > 1e-6:
                        wall_parts.append(shared)
        for w in spec["walls"]:
            if hide and w["hidden"]:
                continue
            wall_parts.append(LineString(w["line"]))
        # Every door segment is also a wall line (so a secret door, or a door
        # placed where two areas merge, still separates them); doors that open
        # are then cut back out.
        self.doors = [d for d in spec["doors"] if not (hide and d["hidden"])]
        wall_parts += [seg_line(d) for d in self.doors]
        base = unary_union(wall_parts) if wall_parts else EMPTY
        base = base.intersection(self.bounds.buffer(0.5))

        cut_doors = [seg_line(d).buffer(0.02, cap_style="flat") for d in self.doors if d["type"] != "secret"]
        self.walls = base.difference(unary_union(cut_doors)) if cut_doors and not base.is_empty else base
        self.walls = linemerge(list(lines(self.walls))) if not self.walls.is_empty else EMPTY

        # door portals for the VTT (things that open)
        self.portals = [d for d in self.doors if d["type"] in ("door", "double", "locked", "portcullis", "bars")]

    def in_hidden(self, at) -> bool:
        return not self.hidden_region.is_empty and self.hidden_region.contains(Point(*at))

    # ---- helpers used by check / export ----
    def wall_polylines(self, tolerance=0.03):
        out = []
        for ln in lines(self.walls):
            ln = ln.simplify(tolerance)
            if ln.length > 1e-6:
                out.append(list(ln.coords))
        return out


def door_angle(d):
    x1, y1, x2, y2 = d["seg"]
    return math.atan2(y2 - y1, x2 - x1)
