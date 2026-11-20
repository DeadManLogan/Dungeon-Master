# Map spec reference (`maps/<book>/<map>/map.yaml`)

Run `python -m tools.mapgen catalog` for the live list of floors, door types and
features. Open `tools/mapgen/catalog.png` to see what each one looks like.

## Coordinates

- Units are **grid squares**. Origin is the **top-left**. x goes right, y goes **down**.
- Integers are grid-line intersections. The square in column 3, row 5 spans
  x 3–4 and y 5–6, and its centre is `[3.5, 5.5]`.
- Rooms and walls sit on integers (grid lines). Furniture usually sits on centres (`.5`).
- In the preview rulers each number names a **square**, not a line: the label "12"
  sits over the square from x = 12 to 13. Red lines mark every 5th grid line.

## meta

| key | default | notes |
|---|---|---|
| title | "Untitled Map" | Shown in the DM cartouche when `show_title: true` |
| source | "" | Book and page, e.g. `"Chapter 3, p.41"` |
| size | [30, 20] | Width and height in squares. Leave 1–2 squares of margin around the dungeon |
| ppg | 100 | Pixels per square. Keep `size × ppg ≤ 8192` px on the long side |
| scale | "5 ft" | Informational |
| style | vtt | `vtt` = colour textures. `print` = ink-friendly hatching |
| background | rock | Texture outside all areas. Use `rock`/`void` for dungeons, `grass`/`dirt`/`sand`/`snow`/`water` outdoors |
| floor | stone | Default floor for areas |
| seed | 1 | Change it to re-roll texture and rough-edge randomness |
| wall_width | 0.2 | In squares |
| grid_on | auto | `auto`: grid only on floors when the background is rock-like, everywhere otherwise. Also `floor`, `all`, `none` |
| player_numbers | false | Show room numbers on the player handout |
| show_title | false | Title box on the DM map |

## areas (floors and rooms) — drawn in list order, later ones on top

Exactly one shape per area:

```yaml
rect:    [x, y, w, h]
poly:    [[x,y], [x,y], ...]          # any polygon, ≥3 points
circle:  [cx, cy, r]
ellipse: [cx, cy, rx, ry]
path:    [[x,y], [x,y], ...]          # corridor along a centre-line
width:   1                            # path width in squares (square ends, mitred corners)
```

Other keys:

| key | default | meaning |
|---|---|---|
| id | — | Room number from the source. Drawn on the DM map and used in the key. **Touching numbered rooms get a wall on their shared edge** |
| name, desc, page | — | Go into `<map>_key.md`. Keep `desc` to a short DM summary, not the read-aloud text |
| floor | meta.floor | Any floor texture |
| walls | true | false = paints the floor only (pools, roads, rugs of texture, outdoor patches). It doesn't change the walkable outline |
| cut | false | true = solid rock carved out of the floor (thick pillars, rock islands). Gets walls round it |
| rough | 0 | Wobbly natural edge, in squares. Caves 0.25–0.45, pools 0.2–0.3 |
| hidden | false | Secret area. Removed from the **player handout** together with everything inside it. Kept on the VTT image, where fog of war hides it |
| merge | false | A numbered room that should open into its neighbours with no wall |
| label_at | centroid | Where to put the room number |
| seed | — | Per-area rough-edge seed |

How walls come out:
- The outline of the union of all `walls: true` areas becomes the walls.
- Areas without an `id` (corridors, alcoves) merge into whatever they touch.
- Numbered rooms that touch are separated by a wall unless `merge: true`.

## walls — extra wall lines

```yaml
walls:
  - [[8, 19], [8, 24]]                 # polyline
  - {line: [[2,2],[5,2]], hidden: true}
```

## doors — a segment across the opening, from wall to wall

```yaml
doors:
  - {seg: [x1, y1, x2, y2], type: door, note: "DM note → key"}
```

Types:
- `door`, `double`, `locked`, `portcullis`, `bars`: VTT doors.
- `arch`: opening, nothing drawn.
- `window`: drawn as glass but left out of the VTT walls, so tokens can see and move through. Add a window wall in the VTT by hand if it matters.
- `secret`: stays a wall, with an **S** on the DM map only.

A door segment always counts as a wall line, and the door then cuts its opening.
So a door can go:
- on an existing wall (room edge, shared edge, `walls:` line), or
- across a merged opening such as where a corridor meets a room.

Make the door span the whole opening. A 2-wide corridor meeting a room's west wall
at x = 13, y 12–14 → `seg: [13, 12, 13, 14]`. The checker warns when a door end
doesn't touch a wall.

## features

```yaml
features:
  - {type: chest, at: [5, 3], rot: 90, size: [0.8, 0.55], label: "", note: "→ key", dm_only: false, hidden: false}
  - {type: stairs, at: [3.5, 13], size: [2, 2], down: e}   # down: side that descends (drawn darker)
  - {type: torch, at: [6.5, 10.3], rot: 0}                 # rot 0 = mounted on a wall to its north
  - {type: rubble, at: [5, 5], size: [3, 2], count: 30}
  - {type: marker, at: [17, 11], label: A, color: "#c4161c"}   # DM-only encounter marker
  - {type: trap, at: [10.5, 13.5], label: T1, note: "2d6 darts"}
```

- `size`: one number or [w, h] in squares, before rotation (stairs are the exception: size is in final orientation).
- `rot`: degrees clockwise.
- `color` recolours: rug, bed, altar cloth, magic_circle, tree, mushrooms, crystals, cauldron, tent, marker.
- `blocks`: override sight-blocking in the VTT export (pillar, statue, boulder and stalagmite block by default).
- `light: N`: light radius in the VTT. Torch 4, brazier 4, campfire 6 and candles 2 by default.
- `dm_only`: DM map only. Traps and markers are dm_only by default.

Facing at `rot: 0`: chairs, beds, thrones, sarcophagi and carts have their back/head
to the north. Bookshelves and chest locks face south.

## lights (extra VTT light sources with no symbol)

```yaml
lights:
  - {at: [10, 4], radius: 6, color: "#9fd0ff", intensity: 0.8}
```

## labels

```yaml
labels:
  - {text: "to Phandalin", at: [3, 16.6], size: 0.35, color: "#1a1a1a", dm_only: false}
```

## Recipes

**Corridor between rooms.** Use a `path` (or `rect`) with no id. It merges into
the rooms. Add a door where it meets a room if the source shows one.

**Room inside a room / partition.** Use a `walls:` line plus a `door` on it.

**Cave.** One or more `poly` areas with `floor: cave`, `rough: 0.35`. Connect
cave chambers with rough `path`s (`rough: 0.2`). Rough edges can swallow features
near the wall, so keep features about 0.7 squares inside or trust the checker.

**Underground river / pool.** `walls: false`, `floor: water`, `rough: 0.25`, layered
over the cave floor. For a river: `path` with `width: 3`. Cross it with a `bridge`
feature (`rot: 90` for an east–west bridge).

**Chasm.** `floor: pit` area with `walls: false` (still walkable for the VTT, so
mark it in `desc`). Use `cut: true` if it should block sight like a wall.

**Outdoor encounter.**
1. Set `background: grass` and `grid_on: all`.
2. Add buildings as `rect` with `floor: wood`; their walls draw automatically.
3. Doors go on the building edges, and `window` doors work for windows.
4. Roads are `path` areas with `walls: false`, `floor: dirt` or `cobble`, `rough: 0.15`.
5. Use `tree`, `bush` and `boulder` features.

**Secret room.** Give the room and its passage `hidden: true`. Put a `secret`
door where the passage meets the visible room, and add a `note` on the door.

**Multi-level site.** Make one map per level (`<site>-level-1`, `<site>-level-2`).
Mark stairs on both, and put a matching `label` ("to level 2") next to each.
