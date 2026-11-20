"""Render a visual catalogue of every floor texture and feature symbol."""
from __future__ import annotations

from .render import render
from .spec import normalise
from .symbols import SYMBOLS
from .textures import FLOORS


def sheet(path, ppg: int = 60):
    floors = sorted(FLOORS)
    seen, feats = set(), []
    for name, s in SYMBOLS.items():
        if id(s) not in seen:
            seen.add(id(s))
            feats.append(name)
    cols = 8
    cw, ch = 4, 4
    frows = -(-len(floors) // cols)
    srows = -(-len(feats) // cols)
    W, H = cols * cw, (frows + srows) * ch + 1
    areas, features, labels = [], [], []
    for i, fl in enumerate(floors):
        x, y = (i % cols) * cw, (i // cols) * ch
        areas.append({"rect": [x + 0.5, y + 0.5, cw - 1, ch - 1.6], "floor": fl, "walls": False})
        labels.append({"text": fl, "at": [x + cw / 2, y + ch - 0.6], "size": 0.45})
    y0 = frows * ch + 1
    for i, ft in enumerate(feats):
        x, y = (i % cols) * cw, y0 + (i // cols) * ch
        areas.append({"rect": [x + 0.3, y + 0.3, cw - 0.6, ch - 0.6], "floor": "stone"})
        f = {"type": ft, "at": [x + cw / 2, y + ch / 2 - 0.4]}
        if ft == "stairs":
            f["size"] = [1, 2]
        if SYMBOLS[ft].size[0] > 2.5:
            f["size"] = 2.6
        features.append(f)
        labels.append({"text": ft, "at": [x + cw / 2, y + ch - 0.75], "size": 0.42})
    spec = normalise({"meta": {"title": "catalog", "size": [W, H], "ppg": ppg, "background": "parchment"},
                      "areas": areas, "features": features, "labels": labels})
    render(spec, "dm").save(path, optimize=True)
    return path
