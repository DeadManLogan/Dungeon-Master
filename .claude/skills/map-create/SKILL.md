---
name: map-create
description: Create or revise a battle map, dungeon map or encounter map for the campaign, as VTT-ready PNGs, a Universal VTT (.dd2vtt) file with walls/doors/lights, a DM key and optional print PDF. Use when the user asks for a map of a location, room, dungeon, encounter, building or outdoor area (from the campaign PDF or made up), or asks to change an existing map.
---

# Map creation

Maps are **code**, grouped by book. Each one is `maps/<book>/<map>/map.yaml`
(`<book>` = the same folder name as `campaign/<book>/`), rendered by
`python -m tools.mapgen`. Never hand-edit the PNGs. Change the YAML and re-render.
The full spec format is in [spec-reference.md](spec-reference.md). Read it before
writing or changing a spec. Tracing a map from the PDF is covered in
[tracing.md](tracing.md).

## 0. Pin down the request (only ask if genuinely unclear)

- **Which location?** A chapter/area name or page, or "an encounter map for X".
- **Source:** trace the PDF's map, build it from the text when the book has no map,
  or design an original one.
- **Scope:** a whole dungeon, one level, or a single room or encounter area. For huge
  sites, split by level or wing.

Defaults (don't ask): 5-ft squares, `ppg: 100`, `vtt` style. Outputs are DM, player,
reveal and VTT PNGs, `.dd2vtt`, the key and the preview. The DM prints maps, so the
final render uses `--print` (see `CLAUDE.md` › Table preferences).

## 1. Gather the source material

1. Read `campaign/<book>/index.md` to find the chapter, pages and whether the book has a
   map. If the campaign hasn't been ingested yet, run the `campaign-ingest` skill first.
2. Read the keyed area text: `campaign/<book>/extracted/pages/pNNNN.txt`, or
   `python tools/pdf_extract.py search <book> "<area name>"`. Note per area:
   number, name, size and shape, exits, doors (locked, secret, trapped), features
   and furniture, light, hazards, creatures (as DM markers only).
3. If the book has a map, find the image through `images.json` / `contact_*.png`.
   Or render the page with
   `python tools/pdf_extract.py render <book> --pages N --dpi 200`, then follow
   [tracing.md](tracing.md).

## 2. Scaffold

```
python -m tools.mapgen new <book>/<map> --title "<Title>" --size WxH [--background rock|grass|...] [--floor stone|cave|...]
```

`<map>` is lowercase-kebab and names the place within the book, e.g.
`lost-mine-of-phandelver/cragmaw-hideout`, `…/wave-echo-cave-level-1`. It is also
the prefix of the output files (`<map>_vtt.png`). Below, `maps/<book>/<map>/` is
written `<folder>`.

## 3. Write the spec

- Fill `meta.source` with book + page. Use the source's room numbers as `id`, and
  give each room a one-line DM `desc` plus a `page`.
- Lay out rooms first, then corridors, doors, features, then DM markers and traps.
- **Secrets never leak to the player map.** Secret doors use `type: secret`.
  Secret rooms and the passages leading to them use `hidden: true`. Traps, monsters
  and notes go in `trap` / `marker` features (DM-only).
- When the source is vague, make sensible choices and record them as you go (for
  the report in step 6).

## 4. Iterate until it's right (the core loop)

```
python -m tools.mapgen render <folder>/map.yaml --only preview      # ~5 s
```

Then **look at** `<folder>/_work/preview.png` with the Read tool. The preview is
the DM map with coordinate rulers. Check:

- every `WARN` line printed: fix it or consciously accept it (e.g. regions linked
  only by stairs)
- room shapes and proportions against the source (`python tools/imgtool.py compare <source> <preview>`)
- doors are on the right walls and fully span their openings
- nothing sits in rock or on a wall; nothing overlaps a room number (move it with
  `label_at`)
- the numbering matches the book

Repeat until it matches. Zoom with `tools/imgtool.py crop` when the preview is too
small to judge a detail.

## 5. Final render

```
python -m tools.mapgen render <folder>/map.yaml            # dm, player, reveal, vtt, dd2vtt, key, preview
python -m tools.mapgen render <folder>/map.yaml --print    # + <map>_print-a3.pdf and <map>_reveal_print-a3.pdf
```

- Look at the **player** PNG once to confirm that no secret door, hidden room, trap
  or marker shows.
- If the map has `hidden` areas, look at `<map>_reveal.png`. Each piece should show
  the hidden rooms as found (secret doors drawn as doors) and nothing DM-only. To
  check that it lines up, paste it onto the player PNG at its squares (the caption
  gives them; 1 square = `ppg` px). Secret doors between two *visible* rooms get no
  piece: the DM just describes them, so mention it in the report.

## 6. Book-keeping and report

- Add or update the row in `maps/README.md`, under the book's heading (map, title, source pages, status).
- Mark the map as done in the `campaign/<book>/index.md` maps table.
- Tell the user:
  - which files to use. For the table, print `_print-a3.pdf` (players) and
    `_reveal_print-a3.pdf` (keep it hidden until the secret is found). For a VTT,
    use `.dd2vtt` or `_vtt.png`. `_dm.png` and the key are for the DM only.
    Never suggest printing `_vtt.png` for players: it shows the hidden rooms.
  - any assumptions or deviations from the book
  - anything they should check in play: things the VTT export can't express,
    like windows or secret doors needing a manual flip

## Revising a map

1. Edit the YAML.
2. Run `--only preview` and look at it.
3. Run the full render.

Keep `seed` unchanged unless the user wants a different random look. Changing it
re-rolls cave edges.

## Limits — say so instead of faking it

- The output is a clean, textured schematic in the style of a modern VTT battlemap,
  not painted art. If the user wants painterly maps, suggest Dungeondraft or a
  similar tool, using this map as the layout reference.
- Regional and overland maps (hex crawls, kingdoms) are not supported by this
  renderer yet. Offer to extend `tools/mapgen` rather than producing something poor.
- New furniture or terrain: add a symbol in `tools/mapgen/symbols.py` (`@sym`
  decorator) or a texture in `textures.py` (`FLOORS`). Re-render the catalog
  (`python -m tools.mapgen catalog --sheet`) and update `spec-reference.md` if
  usage is non-obvious.
