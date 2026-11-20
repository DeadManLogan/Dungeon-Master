"""mapgen — render battle maps from YAML specs.

Maps are grouped by book: maps/<book>/<map>/map.yaml, where <book> is the same
folder name as campaign/<book>/.

  python -m tools.mapgen render maps/<book>/<map>/map.yaml [--only dm,player,vtt,uvtt,key,preview,print] [--paper a4]
  python -m tools.mapgen all    [--book <book>] [--only ...] [--examples]      re-render every map (or one book's)
  python -m tools.mapgen check  maps/<book>/<map>/map.yaml
  python -m tools.mapgen new    <book>/<map> [--title "..."] [--size 30x20] [--background rock] [--floor stone]
  python -m tools.mapgen catalog [--sheet]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUTS = ["dm", "player", "vtt", "uvtt", "key", "preview"]


def cmd_render(args):
    from . import export, render, spec as specmod
    try:
        spec = specmod.load(args.map)
    except specmod.SpecError as e:
        print(e, file=sys.stderr)
        return 2
    slug = spec["_slug"]
    folder = Path(args.map).parent
    work = folder / "_work"
    outs = args.only.split(",") if args.only else list(DEFAULT_OUTPUTS)
    if args.print and "print" not in outs:
        outs.append("print")
    t0 = time.time()
    written = []
    cache = {}

    def get(variant, grid=None, ppg=None):
        k = (variant, grid, ppg)
        if k not in cache:
            cache[k] = render.render(spec, variant, grid=grid, ppg=ppg)
        return cache[k]

    if "dm" in outs:
        p = folder / f"{slug}_dm.png"; get("dm").save(p, compress_level=3); written.append(p)
    if "player" in outs:
        p = folder / f"{slug}_player.png"; get("player").save(p, compress_level=3); written.append(p)
    if "vtt" in outs or "uvtt" in outs:
        img = get("vtt", grid=False)
        if "vtt" in outs:
            p = folder / f"{slug}_vtt.png"; img.save(p, compress_level=3); written.append(p)
        if "uvtt" in outs:
            p = folder / f"{slug}.dd2vtt"
            p.write_text(json.dumps(export.uvtt(spec, img)), encoding="utf-8"); written.append(p)
    if "key" in outs:
        p = folder / f"{slug}_key.md"; p.write_text(export.key_markdown(spec), encoding="utf-8"); written.append(p)
    if "preview" in outs:
        work.mkdir(exist_ok=True)
        p = work / "preview.png"
        render.preview(get("dm"), spec).save(p); written.append(p)
    if "print" in outs:
        ppg = max(int(spec["meta"]["ppg"]), 150)
        img = get("player", grid=True, ppg=ppg)
        p = folder / f"{slug}_print-{args.paper}.pdf"
        n = export.print_pdf(img, spec, p, paper=args.paper)
        written.append(p)
        print(f"print: {n} pages at 1 inch per square")
    big = max(spec["meta"]["size"]) * spec["meta"]["ppg"]
    if big > 8192:
        print(f"WARN image is {big}px on its long side; many VTTs/GPUs cap textures at 8192px — "
              f"lower meta.ppg to {int(8192 // max(spec['meta']['size']))} or less")
    for w in export.check(spec):
        print("WARN", w)
    for p in written:
        print("wrote", p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)
    print(f"done in {time.time() - t0:.1f}s")
    return 0


def cmd_all(args):
    rc = 0
    base = ROOT / "maps" / (args.book or "")
    if not base.is_dir():
        print(f"No folder {base.relative_to(ROOT)}", file=sys.stderr)
        return 1
    for m in sorted(base.rglob("map.yaml")):
        if "_examples" in m.parts and not args.examples and args.book != "_examples":
            continue
        print(f"== {m.parent.relative_to(ROOT)}")
        args.map = str(m)
        rc |= cmd_render(args)
    return rc


def cmd_check(args):
    from . import export, spec as specmod
    try:
        spec = specmod.load(args.map)
    except specmod.SpecError as e:
        print(e, file=sys.stderr)
        return 2
    warns = export.check(spec)
    for w in warns:
        print("WARN", w)
    print("OK" if not warns else f"{len(warns)} warning(s)")
    return 0


TEMPLATE = """\
# Map spec — see .claude/skills/map-create/spec-reference.md
meta:
  title: "{title}"
  source: ""            # book + page, e.g. "Chapter 2, p.34"
  size: [{w}, {h}]       # squares (width, height)
  ppg: 100              # pixels per square
  background: {background}
  floor: {floor}
  seed: 1

areas:
  - id: 1
    name: First room
    rect: [2, 2, 8, 6]
    desc: ""

walls: []
doors: []
features: []
labels: []
"""


def cmd_new(args):
    parts = args.slug.replace("\\", "/").strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        print("give the map as <book>/<map>, e.g. the-delian-tomb/hilltop-ruin "
              "(<book> = the folder name under campaign/)", file=sys.stderr)
        return 1
    book, slug = parts
    if book != "_examples" and not (ROOT / "campaign" / book).is_dir():
        books = sorted(d.name for d in (ROOT / "campaign").iterdir() if d.is_dir())
        print(f"WARN no campaign/{book}/ folder; books so far: {books}")
    folder = ROOT / "maps" / book / slug
    if (folder / "map.yaml").exists():
        print(f"{folder / 'map.yaml'} already exists", file=sys.stderr)
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    w, h = (int(x) for x in args.size.lower().split("x"))
    (folder / "map.yaml").write_text(TEMPLATE.format(title=args.title or slug.replace("-", " ").title(),
                                                     w=w, h=h, background=args.background, floor=args.floor), encoding="utf-8")
    print("created", (folder / "map.yaml").relative_to(ROOT))
    return 0


def cmd_catalog(args):
    from .spec import DOOR_TYPES
    from .symbols import SYMBOLS
    from .textures import FLOORS
    print("FLOORS:", ", ".join(sorted(FLOORS)))
    print("DOOR TYPES:", ", ".join(DOOR_TYPES))
    print("FEATURES (default size | layer | flags):")
    seen = {}
    for name, s in SYMBOLS.items():
        seen.setdefault(id(s), []).append(name)
    for names in seen.values():
        s = SYMBOLS[names[0]]
        flags = [x for x, on in (("blocks", s.blocks), (f"light {s.light}", s.light), ("dm-only", s.dm_only)) if on]
        alias = f" (alias: {', '.join(names[1:])})" if len(names) > 1 else ""
        print(f"  {names[0]:<14} {str(s.size):<12} L{s.layer} {' '.join(flags):<16} {s.desc}{alias}")
    if args.sheet:
        from .catalog import sheet
        p = sheet(ROOT / "tools" / "mapgen" / "catalog.png")
        print("wrote", p.relative_to(ROOT))
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="mapgen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("map"); r.add_argument("--only", help=",".join(DEFAULT_OUTPUTS + ["print"]))
    r.add_argument("--print", action="store_true", help="also build the tiled print PDF")
    r.add_argument("--paper", default="letter", choices=["letter", "a4"])
    r.set_defaults(fn=cmd_render)
    a = sub.add_parser("all", help="re-render every maps/**/map.yaml")
    a.add_argument("--book", help="only this book's maps"); a.add_argument("--only"); a.add_argument("--print", action="store_true")
    a.add_argument("--paper", default="letter", choices=["letter", "a4"]); a.add_argument("--examples", action="store_true")
    a.set_defaults(fn=cmd_all)
    c = sub.add_parser("check"); c.add_argument("map"); c.set_defaults(fn=cmd_check)
    n = sub.add_parser("new"); n.add_argument("slug", metavar="book/map"); n.add_argument("--title"); n.add_argument("--size", default="30x20")
    n.add_argument("--background", default="rock"); n.add_argument("--floor", default="stone"); n.set_defaults(fn=cmd_new)
    k = sub.add_parser("catalog"); k.add_argument("--sheet", action="store_true"); k.set_defaults(fn=cmd_catalog)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
