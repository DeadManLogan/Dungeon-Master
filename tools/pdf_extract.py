"""Campaign PDF helper.

Books live one per folder: campaign/<book>/<file>.pdf. Everything extracted goes
next to the PDF in campaign/<book>/extracted/. <book> below means that folder name
(e.g. the-delian-tomb), or a path to the PDF.

  python tools/pdf_extract.py ingest campaign/<book>/<file>.pdf
      -> campaign/<book>/extracted/
           info.json          page count, metadata, whether OCR seems needed
           outline.md         the PDF bookmarks (chapter / section -> page)
           full.md            all text with "<!-- page N -->" markers (grep-friendly)
           pages/p0001.txt    text per page
           images/            embedded images >= 300 px, named p0012_x345.png
           images.json        image manifest (page, size, repeats, likely_map)
           contact_*.png      thumbnail sheets of large images, for a quick look

  python tools/pdf_extract.py render <book> --pages 12,14-16 [--dpi 150] [--clip x0,y0,x1,y1]
      -> campaign/<book>/extracted/renders/p0012.png   (full page raster; clip in 0..1 page fractions)

  python tools/pdf_extract.py search <book> "term" [--context 80]
      -> pages and snippets where the term appears (case-insensitive)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "campaign"


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def book_pdf(folder: Path) -> Path:
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"No PDF in {folder}")
    if len(pdfs) > 1:
        sys.exit(f"{folder} holds {len(pdfs)} PDFs; keep one book per folder: {[p.name for p in pdfs]}")
    return pdfs[0]


def resolve(book: str) -> tuple[Path, Path]:
    """Return (pdf path, extracted dir) from a book folder name, a book folder, or a PDF path."""
    p = Path(book)
    if p.suffix.lower() == ".pdf":
        if not p.exists():
            sys.exit(f"No such file: {p}")
        p = p.resolve()
        if p.parent.parent != CAMPAIGN.resolve():
            sys.exit(f"Put the PDF in its own book folder first: campaign/<book>/{p.name} "
                     f"(<book> = lowercase-kebab name, e.g. {slugify(p.stem)})")
        return p, p.parent / "extracted"
    folder = p if p.is_dir() else CAMPAIGN / book
    if not folder.is_dir():
        books = sorted(d.name for d in CAMPAIGN.iterdir() if d.is_dir())
        sys.exit(f"No book '{book}'. Books in campaign/: {books}")
    return book_pdf(folder), folder / "extracted"


def parse_pages(spec: str, n: int) -> list[int]:
    out = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def _font(px):
    for n in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            pass
    return ImageFont.load_default(px)


def contact_sheets(items, out_dir: Path, per_sheet=20, thumb=360):
    sheets = []
    for k in range(0, len(items), per_sheet):
        chunk = items[k:k + per_sheet]
        cols = 5
        rows = -(-len(chunk) // cols)
        sheet = Image.new("RGB", (cols * thumb, rows * (thumb + 30)), "white")
        d = ImageDraw.Draw(sheet)
        f = _font(16)
        for i, it in enumerate(chunk):
            im = Image.open(out_dir / "images" / it["file"]).convert("RGB")
            im.thumbnail((thumb - 10, thumb - 10))
            x, y = (i % cols) * thumb, (i // cols) * (thumb + 30)
            sheet.paste(im, (x + 5, y + 5))
            d.text((x + 5, y + thumb), f"{it['file']}  {it['width']}x{it['height']}", font=f, fill="black")
        p = out_dir / f"contact_{k // per_sheet + 1:02d}.png"
        sheet.save(p)
        sheets.append(p.name)
    return sheets


def cmd_ingest(a):
    pdf, out = resolve(a.pdf)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    (out / "images").mkdir(exist_ok=True)
    doc = pymupdf.open(pdf)

    # text
    full = []
    chars = []
    for i, page in enumerate(doc, 1):
        t = page.get_text("text", sort=True)
        chars.append(len(t.strip()))
        (out / "pages" / f"p{i:04d}.txt").write_text(t, encoding="utf-8")
        full.append(f"\n<!-- page {i} -->\n{t}")
    (out / "full.md").write_text(f"# {pdf.name}\n" + "".join(full), encoding="utf-8")

    # outline
    toc = doc.get_toc(simple=True)
    lines = [f"# Outline of {pdf.name}", ""]
    if toc:
        for lvl, title, page in toc:
            lines.append(f"{'  ' * (lvl - 1)}- {title} — p.{page}")
    else:
        lines.append("_No bookmarks in this PDF; build the index from headings in full.md._")
    (out / "outline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # images
    seen: dict[int, dict] = {}
    for pno, page in enumerate(doc, 1):
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen:
                seen[xref]["pages"].append(pno)
                continue
            w, h = img[2], img[3]
            rec = {"xref": xref, "pages": [pno], "width": w, "height": h, "file": None}
            seen[xref] = rec
            if min(w, h) < a.min_size:
                continue
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                smask = img[1]
                if smask:
                    try:
                        mask = pymupdf.Pixmap(doc, smask)
                        if (mask.width, mask.height) == (pix.width, pix.height):
                            pix = pymupdf.Pixmap(pix, mask)
                    except Exception:
                        pass
                name = f"p{pno:04d}_x{xref}.png"
                pix.save(out / "images" / name)
                rec["file"] = name
            except Exception as e:  # odd colourspaces etc.
                rec["error"] = str(e)
    manifest = []
    for rec in seen.values():
        if not rec["file"]:
            continue
        rec["repeats"] = len(rec["pages"]) > 2
        rec["likely_map"] = (not rec["repeats"]) and min(rec["width"], rec["height"]) >= 700
        manifest.append(rec)
    manifest.sort(key=lambda r: r["pages"][0])
    (out / "images.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    big = [r for r in manifest if not r["repeats"]]
    sheets = contact_sheets(big, out) if big else []

    low_text = sum(1 for c in chars if c < 100)
    info = {
        "pdf": pdf.relative_to(ROOT.resolve()).as_posix(), "pages": len(doc), "metadata": doc.metadata,
        "pages_with_little_text": low_text,
        "ocr_needed": low_text > 0.5 * len(doc),
        "images_saved": len(manifest), "likely_maps": [r["file"] for r in manifest if r["likely_map"]],
        "contact_sheets": sheets,
    }
    (out / "info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in info.items() if k != "metadata"}, indent=1))
    print(f"\nExtracted to {out.relative_to(ROOT)}")
    if info["ocr_needed"]:
        print("WARNING: most pages have no text layer — this looks like a scanned PDF. Install Tesseract for OCR.")


def cmd_render(a):
    pdf, out = resolve(a.pdf)
    doc = pymupdf.open(pdf)
    rdir = out / "renders"
    rdir.mkdir(parents=True, exist_ok=True)
    clip = None
    for p in parse_pages(a.pages, len(doc)):
        page = doc[p - 1]
        if a.clip:
            x0, y0, x1, y1 = (float(v) for v in a.clip.split(","))
            r = page.rect
            clip = pymupdf.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)
        pix = page.get_pixmap(dpi=a.dpi, clip=clip)
        suffix = "_clip" if clip else ""
        f = rdir / f"p{p:04d}{suffix}.png"
        pix.save(f)
        print("wrote", f.relative_to(ROOT), f"{pix.width}x{pix.height}")


def cmd_search(a):
    pdf, out = resolve(a.pdf)
    pages_dir = out / "pages"
    rx = re.compile(re.escape(a.term), re.I)
    if pages_dir.exists():
        files = sorted(pages_dir.glob("p*.txt"))
        texts = [(int(f.stem[1:]), f.read_text(encoding="utf-8")) for f in files]
    else:
        doc = pymupdf.open(pdf)
        texts = [(i, p.get_text()) for i, p in enumerate(doc, 1)]
    hits = 0
    for pno, t in texts:
        flat = re.sub(r"\s+", " ", t)
        for m in rx.finditer(flat):
            s, e = max(0, m.start() - a.context), min(len(flat), m.end() + a.context)
            print(f"p.{pno}: …{flat[s:e]}…")
            hits += 1
    print(f"{hits} hit(s)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("ingest"); i.add_argument("pdf", help="campaign/<book>/<file>.pdf or <book>"); i.add_argument("--min-size", type=int, default=300)
    i.set_defaults(fn=cmd_ingest)
    r = sub.add_parser("render"); r.add_argument("pdf", metavar="book"); r.add_argument("--pages", required=True)
    r.add_argument("--dpi", type=int, default=150); r.add_argument("--clip"); r.set_defaults(fn=cmd_render)
    s = sub.add_parser("search"); s.add_argument("pdf", metavar="book"); s.add_argument("term"); s.add_argument("--context", type=int, default=80)
    s.set_defaults(fn=cmd_search)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
