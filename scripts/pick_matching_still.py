#!/usr/bin/env python3
"""Studio otomatik kare adaylari arasindan kapak gorseline en yakinini bulur.

Kullanim: pick_matching_still.py <cover.jpg> <still_0> <still_1> ...  (bos arg = atla)
Cikti (son satir, JSON): {"index": i, "distance": d, "matched": bool}
Yontem: 24x24 gri kucultme + ortalama mutlak fark (0-255). <40 = guclu eslesme.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

SIZE = (24, 24)


def sig(p: Path) -> list[int]:
    with Image.open(p) as im:
        im = ImageOps.fit(im.convert("L"), SIZE)
        return [im.getpixel((x, y)) for y in range(SIZE[1]) for x in range(SIZE[0])]


def quality(p: Path) -> float:
    """Kapak yokken: kontrast (std) + doygunluk; ucuk/siyah/beyaz kareler dusuk puan alir."""
    from PIL import ImageStat
    with Image.open(p) as im:
        im = ImageOps.fit(im.convert("RGB"), (96, 96))
        gray = im.convert("L")
        st = ImageStat.Stat(gray)
        mean, std = st.mean[0], st.stddev[0]
        hsv = im.convert("HSV")
        sat = ImageStat.Stat(hsv).mean[1]
        penalty = abs(mean - 128) / 128.0  # cok karanlik / cok acik
        return std * 1.0 + sat * 0.6 - penalty * 40


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"error": "args"}))
        return 1
    if sys.argv[1] == "-":
        best = None
        for i, arg in enumerate(sys.argv[2:]):
            if not arg or not Path(arg).exists():
                continue
            try:
                q = quality(Path(arg))
            except Exception:
                continue
            if best is None or q > best[1]:
                best = (i, q)
        if best is None:
            print(json.dumps({"error": "no candidates"}))
            return 1
        print(json.dumps({"index": best[0], "score": round(best[1], 1), "mode": "quality"}))
        return 0
    cover = sig(Path(sys.argv[1]))
    best = None
    for i, arg in enumerate(sys.argv[2:]):
        if not arg or not Path(arg).exists():
            continue
        try:
            cand = sig(Path(arg))
        except Exception:
            continue
        dist = sum(abs(a - b) for a, b in zip(cover, cand)) / len(cover)
        if best is None or dist < best[1]:
            best = (i, dist)
    if best is None:
        print(json.dumps({"error": "no candidates"}))
        return 1
    print(json.dumps({"index": best[0], "distance": round(best[1], 1), "matched": best[1] < 40}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
