# Tracing a map from the campaign PDF

The goal is a faithful, gridded copy of the published map. Same shapes, same
numbers, same doors. Built as a spec so it gets clean VTT walls.

## 1. Get the cleanest source image

- First try the embedded image (`campaign/<book>/extracted/images/…`, see
  `images.json` → `likely_map`). It's usually the highest resolution.
- If the map is vector art, split across images, or has its labels as text, render
  the page instead:
  `python tools/pdf_extract.py render <book> --pages N --dpi 200`.
  Use `--clip 0.05,0.1,0.95,0.9` (page fractions) to crop to the map.
- Two-page spreads: render both pages and trace them as one map, with the second
  page's coordinates offset.

## 2. Find the grid

```
python tools/imgtool.py detect <image>
```

It prints the pitch (px per square) and offset. Then confirm it with:

```
python tools/imgtool.py grid <image> --cell <pitch> --offset <ox> <oy>
```

Read `<image dir>/_work/<name>_grid.png`. The red lines must sit on the map's own
grid lines across the **whole** image. Check both edges, because drift means the
pitch is slightly off: adjust it by ±0.1 px.

**No visible grid?** Many published maps print a scale bar ("1 square = 5 ft" or
"0 — 50 ft").
- Measure the scale bar in px with `crop`.
- Work out px per 5 ft and use that as `--cell`.
- Choose an offset so that the room walls fall on grid lines.

**10-ft squares?** Trace in source squares, then multiply every coordinate (and
`size`) by 2 so the result is in 5-ft squares. Or trace directly with
`--cell <pitch/2>`.

## 3. Read coordinates

- Work region by region. Use `python tools/imgtool.py crop <grid image> x0 y0 x1 y1 --scale 2`
  on the gridded image to zoom in.
- Yellow numbers are columns (x) and cyan numbers are rows (y). Each number names
  the square it sits in, so a wall on the line left of column 12 is at x = 12.
- Write rooms as `rect` when they're axis-aligned, and as `poly` otherwise (list the
  corners clockwise).
- Caves: trace roughly 8–16 points around each chamber and add `rough: 0.3` for the
  natural edge. Don't trace every wiggle.
- Note each door's opening: start and end on the wall line.
- Leave 1–2 squares of margin. If the source map starts at grid column 3, you may
  shift everything so the map starts at x = 1.

## 4. Compare and correct

After each `--only preview` render, run:

```
python tools/imgtool.py compare <source image> maps/<book>/<map>/_work/preview.png
```

Look at the comparison image. Fix mismatched room sizes, missing corridors, doors on
the wrong wall and wrong numbering, then repeat. Two or three rounds is normal.

## 5. Things the source shows that the spec expresses differently

| On the published map | In the spec |
|---|---|
| "S" on a wall | `type: secret` door (with a `note`) |
| Numbers in rooms | area `id` (use `label_at` if the centroid lands on furniture) |
| Trap symbol | `trap` feature with `label` + `note` |
| Stair glyph with arrows | `stairs` with `down:` |
| Dotted lines (ledges, illusory walls, elevation changes) | `walls` line with `hidden: true` if it's secret; otherwise a `label` and a note in `desc` |
| Water / chasm hatching | area with `floor: water` / `pit` and `walls: false` |
| Rubble / difficult terrain | `rubble` feature sized to the patch |
