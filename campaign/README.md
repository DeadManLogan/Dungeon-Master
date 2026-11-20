# Campaign

One folder per book: `campaign/<book>/`, named in lowercase-kebab. The same name is
used for that book's maps in `maps/<book>/`.

Each book folder holds:
- the PDF (git-ignored; one per folder)
- `extracted/`: text and images, made by `python tools/pdf_extract.py ingest` (git-ignored)
- `index.md`: chapters, locations and maps with page numbers (committed)

## Books

| Book | Index | Maps |
|---|---|---|
| The Delian Tomb | [index](the-delian-tomb/index.md) | [maps/the-delian-tomb](../maps/the-delian-tomb/) |
