---
name: campaign-ingest
description: Ingest a campaign/adventure PDF so later tasks (maps, items, NPCs, session prep) can find things in it. Extracts text per page, bookmarks, embedded images (finds the maps) and builds campaign/<book>/index.md. Use when the user provides or mentions a campaign PDF, adds a new sourcebook, or a book's index.md is missing.
---

# Campaign ingest

## 1. Put the PDF in place

**One folder per book:** `campaign/<book>/<file>.pdf`, where `<book>` is the
book's name in lowercase-kebab, e.g. `the-delian-tomb`, `lost-mine-of-phandelver`.
The same `<book>` name is used for the book's maps (`maps/<book>/`), so pick it once
and keep it. One PDF per book folder. If the user gave a path elsewhere (or a folder
with spaces or underscores), move or rename it into place. All PDFs under
`campaign/` are git-ignored; the books are copyrighted. Check with
`git check-ignore -v <pdf>`.

## 2. Extract

```
python tools/pdf_extract.py ingest "campaign/<book>/<file>.pdf"
```

This writes `campaign/<book>/extracted/`. After that, the other commands take just
the book name (`render <book>`, `search <book>`):

| file | what it is |
|---|---|
| `info.json` | page count, whether OCR is needed, `likely_maps` |
| `outline.md` | PDF bookmarks → page numbers. Best skeleton for the index |
| `full.md` | all text with `<!-- page N -->` markers. Grep it |
| `pages/pNNNN.txt` | one page of text |
| `images/` + `images.json` | embedded images ≥300 px, which page each is on, `likely_map` flag |
| `contact_NN.png` | thumbnail sheets of non-repeating images. **Look at these** to spot the maps fast |

If `ocr_needed` is true, the PDF is a scan with no text layer. Tell the user
Tesseract is needed (see README › Optional tools) before continuing with text-based
work. Image extraction still works.

## 3. Find the maps

1. Read each `contact_NN.png`, and note which images are maps (dungeon or battle
   maps, region maps, town maps).
2. Read the page text around each one to get its name.
3. Some maps are vector drawings and won't be in `images/`. Look for headings like
   "Map", "Cartographer", or area keys ("1. ", "Area 1"). Render those pages with
   `python tools/pdf_extract.py render <book> --pages N --dpi 80` to check.

## 4. Build `campaign/<book>/index.md`

Use this structure. Keep it compact; it's a lookup table, not a summary of the book.

```markdown
# Campaign index — <Book title>
Source: <file>.pdf (this folder) · extracted: extracted/ · <N> pages

## Chapters
| # | Chapter | Pages | Notes |
|---|---|---|---|

## Locations
| Location | Chapter | Pages | Keyed areas | Book map? |
|---|---|---|---|---|
| Cragmaw Hideout | 1 | 6–10 | 1–12 | yes — p.7 image p0007_x123.png |

## Maps
| Map | Book page / image | Grid | Our map (maps/<book>/<map>) | Status |
|---|---|---|---|---|
| Cragmaw Hideout | p.7, p0007_x123.png | 5 ft squares | — | todo |

## Other assets spotted (for later)
- Magic items (pages), NPC roster (pages), handouts, random tables…
```

Grid column: note the scale if the map shows one ("1 square = 5 ft", "10 ft",
"no grid — scale bar 50 ft").

## 5. Register the book

- Add a row to the Books table in `campaign/README.md`.
- Add a `## <Book title>` heading to `maps/README.md`; that book's maps get listed under it.
  The maps themselves will live in `maps/<book>/`, created by `mapgen new <book>/<map>`.

## 6. Report

Tell the user:
- how many pages and maps were found
- anything odd (scanned pages, maps split across pages, maps that exist only as
  vector art)
- the table of maps, so they can choose what to make first
