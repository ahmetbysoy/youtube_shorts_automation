#!/usr/bin/env python3
"""
FAZ 12.5 - Kanal Banner Ureticisi
================================
YouTube kanal banneri (2560x1440) uretir: siyah arka plan, kalin sarı/beyaz yazi,
tiklanabilir "ABONE OL" cagrisi. Tum cihazlarda gorunecek "guvenli alan"
(1546x423 px) merkezde tutulur.

Kullanim:
    python scripts/generate_banner.py                 # assets/banner.png
    python scripts/generate_banner.py --out x.png --text "..."
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2560, 1440
SAFE_W, SAFE_H = 1546, 423

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

BG = (8, 8, 10)
YELLOW = (255, 214, 0)
WHITE = (245, 245, 248)
RED = (255, 45, 45)


def find_font() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def load_font(path: str | None, size: int):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_path: str | None, max_size: int,
             max_width: int):
    """Yaziyi guvenli alana (max_width) sigdiracak sekilde otomatik kucult."""
    size = max_size
    while size > 24:
        font = load_font(font_path, size)
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(text) * size
        if w <= max_width:
            return font
        size -= 4
    return load_font(font_path, 24)


def centered(draw: ImageDraw.ImageDraw, text: str, font, y: int, fill) -> None:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
    except Exception:
        w = len(text) * 20
    draw.text(((WIDTH - w) / 2, y), text, font=font, fill=fill)


def draw_arrow(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, fill) -> None:
    """Emoji yerine vektor ok (PIL emoji fontu yok)."""
    draw.polygon(
        [(cx, cy + size), (cx - size, cy - size), (cx - size * 0.45, cy - size),
         (cx - size * 0.45, cy - size * 1.6), (cx + size * 0.45, cy - size * 1.6),
         (cx + size * 0.45, cy - size), (cx + size, cy - size)],
        fill=fill,
    )


def build_banner(text_top: str, text_bottom: str, out_path: Path) -> Path:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    font_path = find_font()
    # Tum yazilar "guvenli alan" (SAFE_W) icinde kalmali - mobilde kirpilmasin.
    f_top = fit_font(draw, text_top, font_path, 150, SAFE_W - 80)
    f_bottom = fit_font(draw, text_bottom, font_path, 120, SAFE_W - 80)

    # Arka planda hafif kirmizi isik halesi (CTR icin dikkat cekici)
    for i in range(26):
        alpha = int(70 - i * 2.6)
        if alpha <= 0:
            break
        r = 520 - i * 20
        draw.ellipse(
            [WIDTH // 2 - r, HEIGHT // 2 - r + 120, WIDTH // 2 + r, HEIGHT // 2 + r + 120],
            outline=(alpha, 10, 12),
            width=6,
        )

    centered(draw, text_top, f_top, 560, WHITE)
    centered(draw, text_bottom, f_bottom, 760, YELLOW)

    # Kirmizi "ABONE OL" butonu
    btn_w, btn_h = 640, 140
    bx, by = (WIDTH - btn_w) // 2, 940
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=28, fill=RED)
    f_btn = fit_font(draw, "ABONE OL", font_path, 92, btn_w - 80)
    centered(draw, "ABONE OL", f_btn, by + 20, WHITE)

    # Guvenli alan sinirlari (tum cihazlarda gorunur)
    draw.rectangle(
        [(WIDTH - SAFE_W) // 2, (HEIGHT - SAFE_H) // 2, (WIDTH + SAFE_W) // 2, (HEIGHT + SAFE_H) // 2],
        outline=(38, 38, 42),
        width=3,
    )
    draw_arrow(draw, WIDTH // 2, 500, 40, YELLOW)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube kanal banneri uretir")
    parser.add_argument("--out", default="assets/banner.png", help="cikti dosyasi")
    parser.add_argument("--text-top", default="HER GÜN YENİ BİR ŞOK BİLGİ!")
    parser.add_argument("--text-bottom", default="HAYALETİ HİKAYELER BURADA!")
    args = parser.parse_args()

    out = Path(args.out)
    if not out.is_absolute():
        out = Path(__file__).resolve().parent.parent / out
    path = build_banner(args.text_top, args.text_bottom, out)
    size_kb = round(path.stat().st_size / 1024)
    print(f"[+] Banner uretildi: {path} ({size_kb} KB, {WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
