"""Exports: Universal VTT (.dd2vtt), DM key (markdown), tiled print PDF, lint."""
from __future__ import annotations

import base64
import io
import json
import math

from PIL import Image, ImageDraw
from shapely.geometry import Point
from shapely.ops import unary_union

from .draw import font
from .geometry import Model, door_angle, polygons, seg_line
from .symbols import SYMBOLS


# ------------------------------------------------------------ Universal VTT
def _argb(hex_color: str) -> str:
    return "ff" + hex_color.lstrip("#").lower()[:6]


def uvtt(spec: dict, image: Image.Image) -> dict:
    """Universal VTT JSON (Foundry 'Universal Battlemap Importer', Arkenforge,
    Owlbear/Roll20 importers...). Coordinates are in grid units."""
    meta = spec["meta"]
    gw, gh = meta["size"]
    model = Model(spec, "vtt")
    buf = io.BytesIO()
    image.save(buf, "PNG", compress_level=3)

    portals = []
    for d in model.portals:
        x1, y1, x2, y2 = d["seg"]
        portals.append({
            "position": {"x": (x1 + x2) / 2, "y": (y1 + y2) / 2},
            "bounds": [{"x": x1, "y": y1}, {"x": x2, "y": y2}],
            "rotation": door_angle(d),
            "closed": True,
            "freestanding": False,
        })

    objects = []
    for f in spec["features"]:
        if not f.get("blocks") or f.get("dm_only"):
            continue
        w, h = f["size"]
        x, y = f["at"]
        if f["type"] in ("pillar", "column", "stalagmite", "boulder", "tree", "tree_canopy"):
            ring = Point(x, y).buffer(min(w, h) / 2 * 0.9, quad_segs=3).exterior.coords
        else:
            ring = [(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2), (x - w / 2, y - h / 2)]
        objects.append([{"x": px, "y": py} for px, py in ring])

    lights = []
    for f in spec["features"]:
        if f.get("light") and not f.get("dm_only"):
            lights.append({"position": {"x": f["at"][0], "y": f["at"][1]}, "range": float(f["light"]),
                           "intensity": 1.0, "color": _argb("#ffd9a0"), "shadows": True})
    for l in spec["lights"]:
        lights.append({"position": {"x": l["at"][0], "y": l["at"][1]}, "range": float(l["radius"]),
                       "intensity": float(l["intensity"]), "color": _argb(l["color"]), "shadows": True})

    return {
        "format": 0.3,
        "resolution": {
            "map_origin": {"x": 0, "y": 0},
            "map_size": {"x": gw, "y": gh},
            "pixels_per_grid": image.width / gw,
        },
        "line_of_sight": [[{"x": x, "y": y} for x, y in pl] for pl in model.wall_polylines()],
        "objects_line_of_sight": objects,
        "portals": portals,
        "environment": {"baked_lighting": False, "ambient_light": "ffffffff"},
        "lights": lights,
        "image": base64.b64encode(buf.getvalue()).decode("ascii"),
    }


# ------------------------------------------------------------ DM key
def key_markdown(spec: dict) -> str:
    meta = spec["meta"]
    out = [f"# {meta['title']} — DM key", ""]
    if meta.get("source"):
        out += [f"*Source: {meta['source']}*", ""]
    out += [f"Grid: {meta['size'][0]} × {meta['size'][1]} squares, 1 square = {meta['scale']}.", ""]
    for a in spec["areas"]:
        if a.get("id") is None:
            continue
        head = f"## {a['id']}. {a.get('name', '')}".rstrip()
        if a.get("page"):
            head += f" (p. {a['page']})"
        out.append(head)
        if a.get("hidden"):
            out.append("*Hidden area — not on the player handout.*")
        if a.get("desc"):
            out.append(str(a["desc"]).strip())
        out.append("")
    secrets = [d for d in spec["doors"] if d["type"] == "secret" or d.get("note")]
    notes = [f for f in spec["features"] if f.get("note") or (f.get("dm_only") and f.get("label"))]
    if secrets or notes:
        out += ["## Doors, traps & markers", ""]
        for d in secrets:
            x1, y1, x2, y2 = d["seg"]
            out.append(f"- **{d['type']}** door at ({x1},{y1})–({x2},{y2}): {d.get('note', '')}".rstrip(": "))
        for f in notes:
            out.append(f"- **{f['type']}** {f.get('label', '')} at ({f['at'][0]},{f['at'][1]}): {f.get('note', '')}".rstrip(": "))
        out.append("")
    return "\n".join(out)


# ------------------------------------------------------------ print PDF
PAPER = {"letter": (8.5, 11.0), "a4": (8.27, 11.69)}


def print_pdf(img: Image.Image, spec: dict, path, paper: str = "letter", margin: float = 0.3):
    """Tile a gridded map across pages at 1 inch per square (miniature scale).

    Outside the walls is blanked to white (saves ink) when the background is
    not walkable, and pages with nothing on them are skipped."""
    from .draw import mask
    from .textures import NON_WALKABLE_BG
    meta = spec["meta"]
    gw, gh = meta["size"]
    ppg = img.width / gw
    model = Model(spec, "player")
    keep = mask(model.floor.buffer(float(meta["wall_width"]) * 0.6), img.width, img.height, ppg)
    if meta["background"] in NON_WALKABLE_BG:
        img = Image.composite(img, Image.new("RGB", img.size, "white"), keep)
    else:
        keep = Image.new("L", img.size, 255)
    pw, ph = PAPER[paper]
    best = None
    for (W, H) in ((pw, ph), (ph, pw)):
        cols_per = int(W - 2 * margin)
        rows_per = int(H - 2 * margin - 0.2)
        n = math.ceil(gw / cols_per) * math.ceil(gh / rows_per)
        if best is None or n < best[0]:
            best = (n, W, H, cols_per, rows_per)
    _, W, H, cp, rp = best
    pages = []
    nx, ny = math.ceil(gw / cp), math.ceil(gh / rp)
    f = font(int(ppg * 0.16), bold=False, family="sans")

    # overview page
    ov = Image.new("RGB", (int(W * ppg), int(H * ppg)), "white")
    d = ImageDraw.Draw(ov)
    avail_w, avail_h = ov.width - 2 * margin * ppg, ov.height - 2 * margin * ppg - ppg * 0.6
    s = min(avail_w / img.width, avail_h / img.height)
    thumb = img.resize((int(img.width * s), int(img.height * s)), Image.Resampling.LANCZOS)
    ox, oy = int(margin * ppg), int(margin * ppg + ppg * 0.6)
    ov.paste(thumb, (ox, oy))
    d.text((ox, int(margin * ppg)), f"{spec['meta']['title']} — 1 square = 1 inch (— = blank page, not printed)", font=font(int(ppg * 0.25)), fill="black")
    for j in range(ny):
        for i in range(nx):
            x0, y0 = ox + i * cp * ppg * s, oy + j * rp * ppg * s
            x1, y1 = ox + min(gw, (i + 1) * cp) * ppg * s, oy + min(gh, (j + 1) * rp) * ppg * s
            empty = _empty(keep, i, j, cp, rp, gw, gh, ppg)
            d.rectangle([x0, y0, x1, y1], outline=(200, 200, 200) if empty else (200, 0, 0), width=3)
            d.text(((x0 + x1) / 2, (y0 + y1) / 2), "—" if empty else f"{chr(65 + j)}{i + 1}",
                   font=font(int(ppg * 0.35)), fill=(200, 0, 0), anchor="mm")
    pages.append(ov)

    for j in range(ny):
        for i in range(nx):
            if _empty(keep, i, j, cp, rp, gw, gh, ppg):
                continue
            page = Image.new("RGB", (int(W * ppg), int(H * ppg)), "white")
            c0, r0 = i * cp, j * rp
            c1, r1 = min(gw, c0 + cp), min(gh, r0 + rp)
            crop = img.crop((int(c0 * ppg), int(r0 * ppg), int(c1 * ppg), int(r1 * ppg)))
            px, py = int(margin * ppg), int(margin * ppg + ppg * 0.2)
            page.paste(crop, (px, py))
            dd = ImageDraw.Draw(page)
            dd.rectangle([px, py, px + crop.width, py + crop.height], outline="black", width=1)
            dd.text((px, int(margin * ppg * 0.5)), f"{spec['meta']['title']}  ·  page {chr(65 + j)}{i + 1}  ·  squares x{c0}–{c1 - 1}, y{r0}–{r1 - 1}", font=f, fill="black")
            pages.append(page)
    pages[0].save(path, "PDF", resolution=ppg, save_all=True, append_images=pages[1:])
    return len(pages) - 1


def _empty(keep, i, j, cp, rp, gw, gh, ppg):
    box_ = (int(i * cp * ppg), int(j * rp * ppg), int(min(gw, (i + 1) * cp) * ppg), int(min(gh, (j + 1) * rp) * ppg))
    return keep.crop(box_).getbbox() is None


# ------------------------------------------------------------ lint
def check(spec: dict) -> list[str]:
    """Return a list of human-readable warnings about likely mistakes."""
    warn = []
    meta = spec["meta"]
    gw, gh = meta["size"]
    model = Model(spec, "dm")
    from shapely.geometry import box
    bounds = box(0, 0, gw, gh)

    for a, g in model.areas:
        name = f"area {a.get('id', a.get('name', '?'))}"
        if not g.within(bounds.buffer(0.01)):
            warn.append(f"{name} extends outside the {gw}x{gh} map")
        if g.is_empty or g.area < 0.05:
            warn.append(f"{name} has (almost) no area")

    floor = model.floor
    for i, f in enumerate(spec["features"]):
        if SYMBOLS[f["type"]].layer == 3:
            continue
        pt = Point(*f["at"])
        if not floor.is_empty and floor.distance(pt) > 0.15 and meta["background"] in ("rock", "void"):
            warn.append(f"feature #{i} {f['type']} at {f['at']} sits in solid {meta['background']} (not on any floor)")

    walls = model.walls
    for i, d in enumerate(spec["doors"]):
        ln = seg_line(d)
        if ln.length < 0.3:
            warn.append(f"door #{i} is very short ({ln.length:.2f} squares)")
        mid = ln.interpolate(0.5, normalized=True)
        if not floor.is_empty and floor.distance(mid) > 0.3:
            warn.append(f"door #{i} {d['seg']} is not next to any floor")
        if not walls.is_empty and d["type"] != "secret":
            a, b = Point(ln.coords[0]), Point(ln.coords[-1])
            if walls.distance(a) > 0.25 or walls.distance(b) > 0.25:
                warn.append(f"door #{i} {d['seg']}: an end doesn't touch a wall — gap beside the door, or door off its opening")

    # connectivity: walkable regions linked by doors
    if not model.walkable.is_empty:
        links = [seg_line(d).buffer(0.3) for d in spec["doors"]]
        joined = unary_union([model.walkable.buffer(0.01)] + links)
        comps = list(polygons(joined))
        if len(comps) > 1:
            groups = []
            for c in comps:
                ids = [str(a.get("id", a.get("name", "?"))) for a, g in model.areas
                       if a["walls"] and not a["cut"] and c.intersects(g)]
                groups.append("[" + ", ".join(ids) + "]")
            warn.append(f"walkable space is split into {len(comps)} unconnected parts: {' '.join(groups)} "
                        "(fine if intended, e.g. reached by stairs/teleport)")
    return warn
