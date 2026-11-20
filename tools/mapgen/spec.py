"""Load, default and validate a map spec (YAML).

Coordinates are in grid squares. Origin is the top-left corner of the map,
x grows to the right, y grows downwards. Integer values are grid-line
intersections; the centre of the square in column 3, row 5 is (3.5, 5.5).
"""
from __future__ import annotations

from pathlib import Path

import yaml

META_DEFAULTS = {
    "title": "Untitled Map",
    "source": "",           # e.g. "Lost Mine of Phandelver p.21"
    "size": [30, 20],       # width, height in squares
    "ppg": 100,             # pixels per grid square for PNG output
    "scale": "5 ft",        # what one square represents (informational)
    "style": "vtt",         # vtt (colour textures) | print (ink-friendly)
    "background": "rock",   # texture outside of areas
    "floor": "stone",       # default floor for areas without one
    "seed": 1,              # changes texture / rough-edge randomness
    "wall_width": 0.2,      # squares
    "grid_on": "auto",      # auto | floor | all | none
    "player_numbers": False,  # show room numbers on the player map
    "show_title": False,    # draw a title cartouche on the DM map
}

AREA_SHAPES = ("rect", "poly", "circle", "ellipse", "path")
AREA_KEYS = set(AREA_SHAPES) | {
    "id", "name", "floor", "walls", "cut", "rough", "width", "label_at",
    "desc", "page", "hidden", "seed", "merge",
}
DOOR_TYPES = ("door", "double", "locked", "secret", "portcullis", "arch", "window", "bars")
DOOR_KEYS = {"seg", "type", "note", "hidden"}
FEATURE_KEYS = {
    "type", "at", "size", "rot", "down", "dm_only", "label", "color", "blocks",
    "light", "seed", "count", "hidden", "note",
}
LIGHT_KEYS = {"at", "radius", "color", "intensity"}
LABEL_KEYS = {"text", "at", "size", "color", "dm_only", "hidden"}
TOP_KEYS = {"meta", "areas", "walls", "doors", "features", "lights", "labels"}


class SpecError(Exception):
    pass


def _num_list(v, n, what, errors):
    if not isinstance(v, (list, tuple)) or len(v) != n or not all(isinstance(x, (int, float)) for x in v):
        errors.append(f"{what}: expected a list of {n} numbers, got {v!r}")
        return False
    return True


def _points(v, what, errors, min_pts=2):
    if not isinstance(v, (list, tuple)) or len(v) < min_pts:
        errors.append(f"{what}: expected a list of at least {min_pts} [x, y] points")
        return False
    for p in v:
        if not _num_list(p, 2, what, errors):
            return False
    return True


def load(path: str | Path) -> dict:
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    spec = normalise(raw)
    spec["_path"] = str(path)
    spec["_slug"] = path.parent.name
    return spec


def normalise(raw: dict) -> dict:
    from .symbols import SYMBOLS
    from .textures import FLOORS

    errors: list[str] = []
    for k in raw:
        if k not in TOP_KEYS:
            errors.append(f"unknown top-level key '{k}' (allowed: {sorted(TOP_KEYS)})")

    meta = dict(META_DEFAULTS)
    meta.update(raw.get("meta") or {})
    for k in meta:
        if k not in META_DEFAULTS:
            errors.append(f"meta: unknown key '{k}'")
    _num_list(meta["size"], 2, "meta.size", errors)
    if meta["style"] not in ("vtt", "print"):
        errors.append("meta.style must be 'vtt' or 'print'")
    for k in ("background", "floor"):
        if meta[k] not in FLOORS:
            errors.append(f"meta.{k}: unknown floor '{meta[k]}' (known: {', '.join(sorted(FLOORS))})")

    areas = []
    for i, a in enumerate(raw.get("areas") or []):
        tag = f"areas[{i}]" + (f" (id {a.get('id')})" if isinstance(a, dict) and "id" in a else "")
        if not isinstance(a, dict):
            errors.append(f"{tag}: must be a mapping")
            continue
        for k in a:
            if k not in AREA_KEYS:
                errors.append(f"{tag}: unknown key '{k}'")
        shapes = [s for s in AREA_SHAPES if s in a]
        if len(shapes) != 1:
            errors.append(f"{tag}: needs exactly one of {AREA_SHAPES}")
            continue
        s = shapes[0]
        ok = {
            "rect": lambda: _num_list(a[s], 4, f"{tag}.rect [x, y, w, h]", errors),
            "circle": lambda: _num_list(a[s], 3, f"{tag}.circle [cx, cy, r]", errors),
            "ellipse": lambda: _num_list(a[s], 4, f"{tag}.ellipse [cx, cy, rx, ry]", errors),
            "poly": lambda: _points(a[s], f"{tag}.poly", errors, 3),
            "path": lambda: _points(a[s], f"{tag}.path", errors, 2),
        }[s]()
        if not ok:
            continue
        a = dict(a)
        a["shape"] = s
        a.setdefault("cut", False)
        a.setdefault("floor", meta["background"] if a["cut"] else meta["floor"])
        a.setdefault("walls", True)
        a.setdefault("rough", 0)
        a.setdefault("hidden", False)
        if s == "path":
            a.setdefault("width", 1)
        if a["floor"] not in FLOORS:
            errors.append(f"{tag}: unknown floor '{a['floor']}' (known: {', '.join(sorted(FLOORS))})")
        areas.append(a)

    walls = []
    for i, w in enumerate(raw.get("walls") or []):
        pts = w.get("line") if isinstance(w, dict) else w
        if _points(pts, f"walls[{i}]", errors):
            walls.append({"line": pts, "hidden": bool(w.get("hidden", False)) if isinstance(w, dict) else False})

    doors = []
    for i, d in enumerate(raw.get("doors") or []):
        tag = f"doors[{i}]"
        if not isinstance(d, dict):
            errors.append(f"{tag}: must be a mapping with 'seg'")
            continue
        for k in d:
            if k not in DOOR_KEYS:
                errors.append(f"{tag}: unknown key '{k}'")
        if not _num_list(d.get("seg"), 4, f"{tag}.seg [x1, y1, x2, y2]", errors):
            continue
        d = dict(d)
        d.setdefault("type", "door")
        d.setdefault("hidden", False)
        if d["type"] not in DOOR_TYPES:
            errors.append(f"{tag}: unknown type '{d['type']}' (known: {', '.join(DOOR_TYPES)})")
        doors.append(d)

    features = []
    for i, f in enumerate(raw.get("features") or []):
        tag = f"features[{i}]"
        if not isinstance(f, dict):
            errors.append(f"{tag}: must be a mapping")
            continue
        for k in f:
            if k not in FEATURE_KEYS:
                errors.append(f"{tag}: unknown key '{k}'")
        t = f.get("type")
        if t not in SYMBOLS:
            errors.append(f"{tag}: unknown feature type '{t}' (known: {', '.join(sorted(SYMBOLS))})")
            continue
        if not _num_list(f.get("at"), 2, f"{tag}.at [x, y]", errors):
            continue
        sym = SYMBOLS[t]
        f = dict(f)
        size = f.get("size", sym.size)
        if isinstance(size, (int, float)):
            size = [size, size]
        f["size"] = list(size)
        f.setdefault("rot", 0)
        f.setdefault("dm_only", sym.dm_only)
        f.setdefault("blocks", sym.blocks)
        f.setdefault("hidden", False)
        f.setdefault("seed", i + 1)
        if sym.light and "light" not in f:
            f["light"] = sym.light
        if t == "stairs":
            f.setdefault("down", "s")
            if f["down"] not in ("n", "s", "e", "w"):
                errors.append(f"{tag}: stairs.down must be n, s, e or w")
        features.append(f)

    lights = []
    for i, l in enumerate(raw.get("lights") or []):
        if not isinstance(l, dict) or not _num_list(l.get("at"), 2, f"lights[{i}].at", errors):
            continue
        for k in l:
            if k not in LIGHT_KEYS:
                errors.append(f"lights[{i}]: unknown key '{k}'")
        l = dict(l)
        l.setdefault("radius", 4)
        l.setdefault("color", "#ffd9a0")
        l.setdefault("intensity", 1.0)
        lights.append(l)

    labels = []
    for i, lb in enumerate(raw.get("labels") or []):
        if not isinstance(lb, dict) or "text" not in lb or not _num_list(lb.get("at"), 2, f"labels[{i}].at", errors):
            errors.append(f"labels[{i}]: needs 'text' and 'at'") if isinstance(lb, dict) and "text" not in lb else None
            continue
        for k in lb:
            if k not in LABEL_KEYS:
                errors.append(f"labels[{i}]: unknown key '{k}'")
        lb = dict(lb)
        lb.setdefault("size", 0.5)
        lb.setdefault("color", "#1a1a1a")
        lb.setdefault("dm_only", False)
        lb.setdefault("hidden", False)
        labels.append(lb)

    if errors:
        raise SpecError("Map spec has problems:\n  - " + "\n  - ".join(errors))

    return {"meta": meta, "areas": areas, "walls": walls, "doors": doors,
            "features": features, "lights": lights, "labels": labels}
