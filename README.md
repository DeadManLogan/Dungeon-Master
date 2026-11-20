# Dungeon-Master

A DM prep workspace, built to be driven by Claude Code. Put a campaign PDF in and
ask for maps; later this will cover items, NPCs and session notes too.

> **These notes are maintained.** When the folder layout or the workflow changes,
> this README is updated in the same change. `CLAUDE.md` holds the same rules,
> written for Claude.

## Setup

```
python -m pip install -r requirements.txt
```

## How this repo works

### The idea in one line

**The book is input, the YAML is the work, the images are output.** Anything
generated can be rebuilt with one command, so git only keeps what took effort to make.

### Folders

| Folder | Holds | Who writes it | In git? |
|---|---|---|---|
| `campaign/` | **Source material:** the books and what's pulled out of them. Reference only; nothing we create lives here | you (PDFs), the ingest tool | see below |
| `campaign/README.md` | The list of books | Claude | yes |
| `campaign/<book>/` | **One folder per book**, named in lowercase-kebab, e.g. `the-delian-tomb/`. The same name is used under `maps/` | you | — |
| `campaign/<book>/<file>.pdf` | The book itself (one PDF per folder) | you | no (copyrighted) |
| `campaign/<book>/extracted/` | Text of every page, the book's images, thumbnail sheets. Lets Claude search the book without re-reading the PDF | `pdf_extract.py ingest` | no (rebuildable) |
| `campaign/<book>/index.md` | The lookup table for that book: sections, locations, maps, items, NPCs → page numbers. Everything else starts here | Claude | yes |
| `maps/` | **Our maps**, grouped by book. `maps/README.md` lists them all | Claude | see below |
| `maps/<book>/` | All maps for one book: the book's own maps and any originals for its locations | Claude | — |
| `maps/<book>/<map>/map.yaml` | One map as data: rooms, walls, doors, furniture, secrets. The source of truth | Claude (you can edit it too) | yes |
| `maps/<book>/<map>/*.png, *.dd2vtt, *.pdf` | Rendered images and VTT files, named `<map>_…` | `mapgen render` | no (rebuildable) |
| `maps/<book>/<map>/<map>_key.md` | Room-by-room DM notes for the map | `mapgen render` | yes |
| `maps/<book>/<map>/_work/` | Previews and comparison images Claude uses while checking a map | tools | no |
| `maps/_examples/` | A reference map that shows off every spec feature (not a book) | Claude | yes |
| `items/` | *(future)* homebrew or adapted magic items | — | yes |
| `npcs/` | *(future)* NPC sheets: personality, stats, voice notes | — | yes |
| `sessions/` | *(future)* session prep and recaps | — | yes |
| `tools/` | The Python tools (below) | Claude | yes |
| `.claude/skills/` | Step-by-step playbooks Claude follows: `campaign-ingest`, `map-create` | Claude | yes |
| `CLAUDE.md` | House rules for Claude: conventions and your table preferences | Claude / you | yes |

Today that looks like:

```
campaign/
  README.md
  the-delian-tomb/
    The_Delian_Tomb.pdf        (ignored)
    extracted/                 (ignored)
    index.md
maps/
  README.md
  the-delian-tomb/
    tomb/
      map.yaml  tomb_key.md  tomb_dm.png  tomb_player.png  tomb_reveal.png  tomb_vtt.png  tomb.dd2vtt
      tomb_print-a3.pdf  tomb_reveal_print-a3.pdf
    (hilltop-ruin/, mabbett-farm/ … would go here)
  _examples/sunken-crypt/
```

### Workflow

```
 1. You add a book         campaign/<book>/<file>.pdf   (one folder per book; Claude fixes the name if needed)
          │
 2. Ingest (once per book) "here's the PDF"  → campaign-ingest skill
          │                 extracts text + images into campaign/<book>/extracted/,
          │                 finds the maps, writes campaign/<book>/index.md
          │
 3. Ask for a map          "make the map for X"  → map-create skill
          │                 a. find X in the book's index.md, read its pages
          │                 b. trace the book's map on a grid (or design one from the text)
          │                 c. write maps/<book>/<map>/map.yaml
          │                 d. render a preview → Claude looks at it, compares with the book, fixes, repeats
          │                 e. final render: DM / player / VTT images, .dd2vtt, key
          │                 f. update maps/README.md and the maps table in the book's index.md
          │
 4. Use it                 table: print _print-a3.pdf, keep _reveal_print-a3.pdf hidden until the secret is found
          │                 VTT: <map>.dd2vtt (or _vtt.png) · you: _dm.png + _key.md
          │
 5. Change it              "move the door", "add a campfire"  → Claude edits map.yaml and re-renders
```

The rules that make this reliable:
- **Claude looks at every map before calling it done.**
- **Secrets never reach the player map.** Secret doors, hidden rooms, traps and
  monster markers are marked as such in the YAML and are stripped automatically.
  Hidden rooms come back as separate reveal pieces when the party finds them.
- **No long read-aloud text is copied from the book.** Notes are short summaries
  with page numbers.

## What a map folder contains

| file | use it for |
|---|---|
| `<map>_print-a3.pdf` | **Print this for the table.** The player map at 1 inch per square, tiled across A3 sheets (tape them together). Rock is white to save ink. The first page is an assembly guide; don't print it if you don't need it |
| `<map>_reveal_print-a3.pdf` | **Reveal pieces**, only for maps with secret areas. Each hidden area as the party finds it (secret doors shown as doors), same scale. Cut along the dashed line and lay it on the player print when the secret is discovered. Keep it out of sight until then |
| `<map>_reveal.png` | The same reveal pieces as an image, with the squares each one covers |
| `<map>_vtt.png` | Upload to any VTT (no grid; the VTT draws it). 100 px per square. **Don't print it for players: it shows the secret rooms** |
| `<map>.dd2vtt` | Universal VTT: image + walls + doors + lights. Foundry: *Universal Battlemap Importer* module. Also Arkenforge, Owlbear Rodeo extensions, Roll20 (API script) |
| `<map>_player.png` | Gridded player map as an image. Secrets removed. For printing, prefer the PDF (sharper, right scale, less ink) |
| `<map>_dm.png` | Your copy: room numbers, secret doors, traps, encounter markers |
| `<map>_key.md` | Room-by-room DM notes with page refs |

## Tools

```
python -m tools.mapgen new <book>/<map> --title "…" --size 30x20
python -m tools.mapgen render maps/<book>/<map>/map.yaml [--only preview] [--print] [--paper a3|a4|letter]
python -m tools.mapgen all [--book <book>]     # re-render every map (e.g. on a new machine)
python -m tools.mapgen catalog [--sheet]       # floors / doors / features (see tools/mapgen/catalog.png)
python tools/pdf_extract.py ingest campaign/<book>/<file>.pdf
python tools/pdf_extract.py render|search <book> …
python tools/imgtool.py detect|grid|crop|compare …
```

Example: [maps/_examples/sunken-crypt/map.yaml](maps/_examples/sunken-crypt/map.yaml).

## Optional tools

None are required for maps.

- **Tesseract OCR**: only needed if the campaign PDF is a scan with no text layer.
  `winget install UB-Mannheim.TesseractOCR`
- **Foundry VTT + Universal Battlemap Importer**: imports `.dd2vtt` with walls,
  doors and lights in one step.
- **Dungeondraft** (paid): if you ever want hand-painted maps, use our map as the
  layout reference.

## Changelog of decisions

- 2026-11-19: Repo set up. Maps are YAML rendered by `tools/mapgen`. Generated files are git-ignored.
- 2026-11-20: Defaults accepted: VTT play, 100 px per square, no print PDFs unless asked. *The Delian Tomb* ingested; tomb map done.
- 2026-11-20: **Everything grouped by book.** `campaign/<book>/` holds the PDF, its `extracted/` data and its `index.md`; maps live in `maps/<book>/<map>/` under the same book name. `campaign/source/` and the top-level `campaign/index.md` / `campaign/extracted/` are gone. The tomb map moved from `maps/delian-tomb/` to `maps/the-delian-tomb/tomb/` (output files are now `tomb_*`).
- 2026-11-20: **Maps are printed for the table**, on A3 at 1 inch per square (A3 is now the default paper). Secret areas use **reveal pieces**: the player print leaves them blank, and a separate cut-out (`_reveal_print-a3.pdf`) is laid on top when they're found. The VTT image must not be printed for players because it shows the secret rooms.
