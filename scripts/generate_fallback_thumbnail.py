#!/usr/bin/env python3
"""Yerel yedek kapak (thumbnail) ureteci - AI servisi calismazsa devreye girer.

NEDEN:
  image.pollinations.ai ardisik isteklerde HTTP 402 (rate limit) donuyor; run #52'de
  AI kapak uretilemedigi icin "[+] KAPAK RESMI BASARIYLA YUKLENDI VE KAYDEDILDI!"
  satiri CI logunda gorunmedi ve video YouTube'un otomatik secim karesiyle yayinlandi.
  Bu uretecler: AI basarisiz oldugunda yerelde AGRESIF, yuksek kontrastli,
  telefonda okunabilir bir kapak uretir (beyaz/sari kalin yazi, siyah zemin,
  kirmizi vurgu rozeti, sari ok) - kanal banneri ile ayni gorsel dil.

Kullanim:
  python scripts/generate_fallback_thumbnail.py --title "Baslik" --out /tmp/thumb.jpg
Cikti: 0 (basarili) / 1 (hata)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:  # pragma: no cover
    print(f"[!] Pillow yuklenemedi: {exc}", file=sys.stderr)
    raise SystemExit(1)

W, H = 1080, 1920
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def pick_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start: int, min_size: int = 54):
    size = start
    while size > min_size:
        font = pick_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
        size -= 6
    return pick_font(min_size)


def wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:6]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Zemin: siyah -> koyu kirmizi dikey gradyan (kapak banneri ile ayni dil)
    img = Image.new("RGB", (W, H), (8, 8, 12))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        ratio = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=(
                int(10 + 70 * ratio),
                int(6 + 8 * ratio),
                int(12 + 14 * ratio),
            ),
        )

    # Ustte kirmizi "SON" bandi -> dikkat cekici kontrast
    draw.rectangle([0, 120, W, 300], fill=(196, 22, 32))
    band_font = fit_font(draw, "SON BULMA", W - 120, 150)
    bbox = draw.textbbox((0, 0), "SON BULMA", font=band_font)
    draw.text(
        ((W - (bbox[2] - bbox[0])) / 2, 210 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
        "SON BULMA",
        font=band_font,
        fill=(255, 255, 255),
    )

    title = (args.title or "BILIM").strip()
    if "#Shorts" in title:
        title = title.replace("#Shorts", "").strip()

    title_font = fit_font(draw, title, W - 140, 132)
    lines = wrap(draw, title, title_font, W - 140)
    y = 420
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (W - (bbox[2] - bbox[0])) / 2
        # Siyah dis kontur + sari yazi (telefonda okunabilirlik)
        for dx, dy in ((-6, 0), (6, 0), (0, -6), (0, 6), (-5, -5), (5, 5), (-5, 5), (5, -5)):
            draw.text((x + dx, y + dy), line, font=title_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=title_font, fill=(255, 214, 10))
        y += int(bbox[3] - bbox[1]) + 26

    # Alt tarafta kirmizi "ABONE OL" butonu
    btn_y = H - 430
    draw.rounded_rectangle([140, btn_y, W - 140, btn_y + 190], radius=44, fill=(214, 18, 28))
    btn_font = fit_font(draw, "ABONE OL", W - 380, 116, 60)
    bbox = draw.textbbox((0, 0), "ABONE OL", font=btn_font)
    draw.text(
        ((W - (bbox[2] - bbox[0])) / 2, btn_y + 95 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
        "ABONE OL",
        font=btn_font,
        fill=(255, 255, 255),
    )

    # Sari asagi ok (banner ile ayni gorsel dil)
    arrow = [(W // 2 - 110, btn_y - 230), (W // 2 + 110, btn_y - 230), (W // 2, btn_y - 60)]
    draw.polygon(arrow, fill=(255, 214, 10))

    img.save(out, "JPEG", quality=92)
    size_kb = round(out.stat().st_size / 1024)
    print(f"[*] Yerel yedek kapak uretildi: {out} ({size_kb} KB, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
