"""Image helpers for tracing maps out of a campaign PDF.

  python tools/imgtool.py detect  <img>                       estimate grid pitch + offset (px)
  python tools/imgtool.py grid    <img> --cell 52.3 [--offset 12 8] [--out f.png]
                                  overlay a numbered grid so squares can be read off as coordinates
  python tools/imgtool.py crop    <img> x0 y0 x1 y1 [--scale 2] [--out f.png]    zoom into a region (px)
  python tools/imgtool.py compare <a> <b> [--out f.png]       side by side, same height
  python tools/imgtool.py info    <img>

Outputs default to the `_work/` folder next to the input, or to --out.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _font(px):
    for n in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            pass
    return ImageFont.load_default(px)


def _out(a, src: Path, suffix: str) -> Path:
    if a.out:
        return Path(a.out)
    d = src.parent / "_work"
    d.mkdir(exist_ok=True)
    return d / f"{src.stem}_{suffix}.png"


def _autocorr(signal: np.ndarray):
    s = signal - signal.mean()
    # high-pass: remove room-sized structure so only repeating grid lines remain
    k = 31
    s = s - np.convolve(s, np.ones(k) / k, mode="same")
    ac = np.correlate(s, s, mode="full")[len(s) - 1:]
    return s, ac / (ac[0] + 1e-9)


def _peaks(ac, lo, hi):
    return [i for i in range(max(lo, 1), min(hi, len(ac) - 1)) if ac[i] > 0 and ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]]


def _at(ac, x):
    i = int(x)
    if i + 1 >= len(ac):
        return 0.0
    return float(ac[i] + (ac[i + 1] - ac[i]) * (x - i))


def _refine(ac, lag):
    lag = int(round(lag))
    best = max(range(max(1, lag - 3), min(len(ac) - 1, lag + 4)), key=lambda i: ac[i])
    y0, y1, y2 = ac[best - 1], ac[best], ac[best + 1]
    d = y0 - 2 * y1 + y2
    return best + (0.5 * (y0 - y2) / d if d else 0)


def _phase(s, lag):
    n = int(len(s) // lag * lag)
    k = np.arange(n)
    ang = np.angle(np.sum(s[:n] * np.exp(-2j * np.pi * k / lag)))
    off = (-ang / (2 * np.pi) * lag) % lag
    return off - lag if off > lag / 2 else off


def cmd_detect(a):
    im = Image.open(a.img).convert("L")
    g = np.asarray(im).astype(np.float32)
    sx, acx = _autocorr(np.abs(np.diff(g, axis=1)).sum(axis=0))
    sy, acy = _autocorr(np.abs(np.diff(g, axis=0)).sum(axis=1))
    lo, hi = a.min, min(a.max, len(acx) // 3, len(acy) // 3)
    # A real grid repeats on BOTH axes and at 2x/3x its pitch; texture noise doesn't.
    cands = set(_peaks(acx, lo, hi)) | set(_peaks(acy, lo, hi))
    def score(L):
        return sum(_at(ac, L) + 0.6 * _at(ac, 2 * L) + 0.4 * _at(ac, 3 * L) for ac in (acx, acy))
    ranked = sorted(cands, key=score, reverse=True)
    print(f"image {im.width}x{im.height}")
    if not ranked:
        print("no repeating grid found — measure a scale bar / wall with `crop` instead")
        return
    # prefer the smallest candidate whose score is close to the best (avoid 2x pitch)
    top = score(ranked[0])
    L = min((c for c in ranked[:6] if score(c) > 0.8 * top), default=ranked[0])
    px, py = _refine(acx, L), _refine(acy, L)
    cell = (px + py) / 2
    ox, oy = _phase(sx, cell), _phase(sy, cell)
    conf = (_at(acx, cell) + _at(acy, cell)) / 2
    print(f"pitch x {px:.2f}px, y {py:.2f}px  (confidence {conf:.2f})")
    print(f"suggest: --cell {cell:.2f} --offset {ox:.1f} {oy:.1f}  ->  ~{im.width / cell:.1f} x {im.height / cell:.1f} squares")
    others = [f"{c}px" for c in ranked[:4] if abs(c - L) > 3]
    if others:
        print("other candidates:", ", ".join(others))
    if conf < 0.15 or abs(px - py) / cell > 0.03:
        print("low confidence: verify with `grid` before trusting it")


def cmd_grid(a):
    src = Path(a.img)
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im, "RGBA")
    c = a.cell
    ox, oy = a.offset
    f = _font(max(10, int(c * 0.32)))
    n_x = int((im.width - ox) / c + 0.1)
    n_y = int((im.height - oy) / c + 0.1)
    for i in range(n_x + 1):
        x = ox + i * c
        d.line([(x, 0), (x, im.height)], fill=(255, 0, 0, 200 if i % 5 == 0 else 110), width=2 if i % 5 == 0 else 1)
    for j in range(n_y + 1):
        y = oy + j * c
        d.line([(0, y), (im.width, y)], fill=(255, 0, 0, 200 if j % 5 == 0 else 110), width=2 if j % 5 == 0 else 1)
    step = 1 if c >= 30 else 2 if c >= 15 else 5
    for i in range(0, n_x, step):
        d.text((ox + (i + 0.5) * c, oy + 0.5 * c), str(i), font=f, fill=(255, 255, 0, 255), anchor="mm", stroke_width=2, stroke_fill="black")
    for j in range(0, n_y, step):
        d.text((ox + 0.5 * c, oy + (j + 0.5) * c), str(j), font=f, fill=(0, 255, 255, 255), anchor="mm", stroke_width=2, stroke_fill="black")
    p = _out(a, src, "grid")
    im.save(p)
    print("wrote", p, f"({n_x} x {n_y} squares; yellow = column, cyan = row)")


def cmd_crop(a):
    src = Path(a.img)
    im = Image.open(src)
    c = im.crop((a.x0, a.y0, a.x1, a.y1))
    if a.scale != 1:
        c = c.resize((int(c.width * a.scale), int(c.height * a.scale)), Image.Resampling.LANCZOS)
    p = _out(a, src, f"crop_{a.x0}_{a.y0}")
    c.save(p)
    print("wrote", p)


def cmd_compare(a):
    A, B = Image.open(a.a).convert("RGB"), Image.open(a.b).convert("RGB")
    h = min(A.height, B.height, 1400)
    A = A.resize((int(A.width * h / A.height), h))
    B = B.resize((int(B.width * h / B.height), h))
    out = Image.new("RGB", (A.width + B.width + 20, h), "white")
    out.paste(A, (0, 0))
    out.paste(B, (A.width + 20, 0))
    p = _out(a, Path(a.b), "compare")
    out.save(p)
    print("wrote", p)


def cmd_info(a):
    im = Image.open(a.img)
    print(a.img, im.size, im.mode, im.info.get("dpi"))


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("detect"); s.add_argument("img")
    s.add_argument("--min", type=int, default=16, help="smallest pitch to consider (px)")
    s.add_argument("--max", type=int, default=400, help="largest pitch to consider (px)"); s.set_defaults(fn=cmd_detect)
    s = sub.add_parser("grid"); s.add_argument("img"); s.add_argument("--cell", type=float, required=True)
    s.add_argument("--offset", type=float, nargs=2, default=[0, 0]); s.add_argument("--out"); s.set_defaults(fn=cmd_grid)
    s = sub.add_parser("crop"); s.add_argument("img")
    for k in ("x0", "y0", "x1", "y1"):
        s.add_argument(k, type=int)
    s.add_argument("--scale", type=float, default=1); s.add_argument("--out"); s.set_defaults(fn=cmd_crop)
    s = sub.add_parser("compare"); s.add_argument("a"); s.add_argument("b"); s.add_argument("--out"); s.set_defaults(fn=cmd_compare)
    s = sub.add_parser("info"); s.add_argument("img"); s.set_defaults(fn=cmd_info)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
