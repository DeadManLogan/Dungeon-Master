# Dungeon-Master — DM prep workspace

This repo holds a DM's preparation for running a published campaign: maps now, and
later items, NPCs and session notes. Claude does the prep work through the skills in
`.claude/skills/` and the Python tools in `tools/`.

## Layout

```
campaign/
  README.md      list of books
  <book>/        one folder per book, lowercase-kebab, e.g. the-delian-tomb/
    <file>.pdf     the book (git-ignored, copyrighted); one PDF per folder
    extracted/     text/images pulled from the PDF (git-ignored, regenerable)
    index.md       chapters, locations, maps → pages; the lookup table for that book
maps/
  README.md      list of maps by book, and their status
  <book>/        same <book> name as under campaign/
    <map>/         one folder per map, e.g. tomb/, hilltop-ruin/
      map.yaml       SOURCE OF TRUTH; edit this, never the images
      <map>_dm.png / _player.png / _vtt.png / .dd2vtt / _print-*.pdf   generated
      <map>_key.md   generated DM key (committed)
      _work/         previews and scratch (git-ignored)
  _examples/     reference maps showing the spec features (not a book)
items/  npcs/  sessions/      future work
tools/
  mapgen/        YAML → map renderer  (python -m tools.mapgen --help)
  pdf_extract.py PDF ingest / page render / search
  imgtool.py     grid detect / grid overlay / crop / compare for tracing
.claude/skills/  campaign-ingest, map-create
```

## Conventions

- **Keep the notes current.** `README.md` › "How this repo works" is the user's guide to
  the folders and workflow. Whenever a change alters the layout, the workflow or a
  decision, update it (and its changelog) in the same change. The user asked for this.

- Run tools from the repo root: `python -m tools.mapgen …`, `python tools/pdf_extract.py …`.
- Python 3.12. Dependencies are in `requirements.txt` (pymupdf, shapely, pyyaml,
  pillow, numpy).
- **Everything is grouped by book.** A book's name is a lowercase-kebab folder name
  (`the-delian-tomb`), used in both `campaign/<book>/` and `maps/<book>/`. Map
  folder names are lowercase-kebab place names inside the book; multi-level sites
  get `-level-N`. Original maps for a book's locations go in that book's folder too.
- Always **look at** a rendered preview (Read tool) before calling a map done, and
  resolve every `WARN`.
- Never put secrets on the player map. Use `secret` doors, `hidden: true` areas and
  DM-only traps/markers.
- Never paste long read-aloud text from the book into the repo. Short DM summaries
  and page references only.
- Generated images and PDFs are git-ignored (rebuild with
  `python -m tools.mapgen all`). Commit `map.yaml` and `_key.md`.

## Table preferences

<!-- Fill in once the DM answers; skills read this. -->
- VTT / table: VTT (DM accepted the defaults on 2026-11-20). Which VTT is not stated yet, so ship `_vtt.png` + `.dd2vtt`.
- Pixels per square: 100
- Print PDFs by default: no (only on request)
- Paper: letter
- Git: generated images/PDFs stay ignored (accepted)
