#!/usr/bin/env python3
"""Studio otomatik kare adaylari arasindan kapak gorseline en yakinini bulur.

Kullanim:
  pick_matching_still.py <cover.jpg> <still_0> <still_1> ...  (bos arg = atla)
  pick_matching_still.py brightness <resim>
Cikti (son satir, JSON): {"index": i, "distance": d, "matched": bool}
  veya {"mode": "brightness", "mean": float}

Yontem: 24x24 gri kucultme + ortalama mutlak fark (0-255). <40 = guclu eslesme.
ESLESEME BANT MASKESI (2026-11-23, run 44929883887 dersi):
  Kapak (cover.jpg) uzerine baslik seridi (ust), konu basligi (orta-ust) ve
  "ABONE OL" rozeti + sarı cizgi (alt) cizilir; Studio adaylari ise ham video
  karesidir. Bu sabit bantlar karsilastirmaya dahil edilince merkezi konu
  ayni olsa bile fark her zaman 40 esigini geciyor ve "eslesme yok" cikiyordu.
  Bu yuzden yalnizca MERKEZİ KONU BANTI (satir 10-20) karsilastirilir; yazi/rozet
  satirlari maskelenir. Birebir ayni gorsellerde fark hala 0'dir (regresyon korunur).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageStat

SIZE = (24, 24)
# 24 satirlik gridde maskelenen satirlar (yukari/asa yazi ve CTA bantlari).
# Merkez konu blogu: satir 10..20 (gorselin ~%42-%83'i).
MASKED_ROWS = set(range(0, 10)) | set(range(21, 24))


def _is_masked_row(y: int) -> bool:
    return y in MASKED_ROWS


def sig(p: Path) -> list[int]:
    with Image.open(p) as im:
        im = ImageOps.fit(im.convert("L"), SIZE)
        return [im.getpixel((x, y)) for y in range(SIZE[1]) for x in range(SIZE[0])]


def masked_distance(cover: list[int], cand: list[int]) -> float:
    """Yalniz maskelenmemis merkez banttaki piksellerin ortalama mutlak farki."""
    total = 0.0
    count = 0
    for idx, (a, b) in enumerate(zip(cover, cand)):
        y = idx // SIZE[0]
        if _is_masked_row(y):
            continue
        total += abs(a - b)
        count += 1
    return total / count if count else 255.0


def gray_mean(p: Path) -> float:
    """Kucuk gri kopyanin ortalama parlakligi (0-255). Koyu kapak tespiti icin."""
    with Image.open(p) as im:
        small = ImageOps.fit(im.convert("L"), (48, 84))
        return float(ImageStat.Stat(small).mean[0])


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
    if len(sys.argv) < 2:
        print(json.dumps({"error": "args"}))
        return 1
    # Parlaklik modu: `pick_matching_still.py brightness <resim>`
    if sys.argv[1] == "brightness":
        if len(sys.argv) < 3 or not Path(sys.argv[2]).exists():
            print(json.dumps({"error": "missing_image"}))
            return 1
        try:
            print(json.dumps({"mode": "brightness", "mean": round(gray_mean(Path(sys.argv[2])), 1)}))
            return 0
        except Exception as exc:
            print(json.dumps({"error": "brightness_failed", "detail": type(exc).__name__}))
            return 1
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
    cover_path = Path(sys.argv[1])
    if not cover_path.exists():
        print(json.dumps({"error": "cover_missing"}))
        return 1
    cover = sig(cover_path)
    best = None
    for i, arg in enumerate(sys.argv[2:]):
        if not arg or not Path(arg).exists():
            continue
        try:
            cand = sig(Path(arg))
        except Exception:
            continue
        dist = masked_distance(cover, cand)
        if best is None or dist < best[1]:
            best = (i, dist)
    if best is None:
        print(json.dumps({"error": "no candidates", "distance": None}))
        return 1
    distance = round(best[1], 1)
    print(json.dumps({"index": best[0], "distance": distance, "matched": distance < 40}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
