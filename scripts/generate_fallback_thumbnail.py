#!/usr/bin/env python3
"""Yerel yedek kapak (thumbnail) ureteci - AI servisi calismazsa devreye girer.

NEDEN (FAZ 12.6 / Islah 10):
  image.pollinations.ai ardisik isteklerde HTTP 402 (rate limit) donuyor; run #52'de
  AI kapak uretilemedigi icin "KAPAK RESMI BASARIYLA YUKLENDI" satiri CI logunda
  gorunmedi ve video YouTube'un otomatik secim karesiyle yayinlandi.

NEDEN (FAZ 13.3 - denetim):
  Kanal denetimi, onceki metin-kartı yedek kapagin "konu nesnesi yok" oldugunu ve
  en zayif ornek oldugunu belirtti. Bu yuzden yedek kapak artık:
    1) VIDEONUN KONU KARESI (ffmpeg ile kare alinir, en kontrastli kare secilir),
    2) uzerine siyah dis konturlu sari baslik,
    3) kirmizi "ABONE OL" rozeti + konuya isaret eden sari ok
    olarak uretilir. Video yoksa (eski davranis) metin kartina dusulur.

Kullanim:
  python scripts/generate_fallback_thumbnail.py --title "Baslik" --out /tmp/thumb.jpg \
      --video output/final_short.mp4 --topic "Bilim"
Cikti: 0 (basarili) / 1 (hata)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageStat
except Exception as exc:  # pragma: no cover
    print(f"[!] Pillow yuklenemedi: {exc}", file=sys.stderr)
    raise SystemExit(1)

W, H = 1080, 1920
YELLOW = (255, 214, 10)
RED = (214, 18, 28)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf",
    "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
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


# --------------------------------------------------------------------------- video
def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def probe_duration(video: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    proc = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(video)])
    try:
        value = float(proc.stdout.strip())
        return value if value > 1 else None
    except Exception:
        return None


def extract_candidate_frames(video: Path, workdir: Path) -> list[Path]:
    """Videodan birkok aday kare alir (konu net, metin/son karti olmayan)."""
    if not shutil.which("ffmpeg"):
        return []
    duration = probe_duration(video)
    if duration:
        ratios = [0.22, 0.36, 0.5, 0.64, 0.78]
        timestamps = [round(duration * r, 2) for r in ratios]
    else:
        timestamps = [2.0, 5.0, 8.0]
    frames: list[Path] = []
    for idx, ts in enumerate(timestamps):
        target = workdir / f"frame_{idx}.jpg"
        proc = _run([
            "ffmpeg", "-y", "-ss", str(ts), "-i", str(video),
            "-frames:v", "1", "-q:v", "3", str(target),
        ])
        # Duz renkli test videolari cok kucuk JPEG uretebilir; esik dusuk tutulur
        # (gecerlilik PIL ile pick_best_frame icinde zaten dogrulanir).
        if proc.returncode == 0 and target.exists() and target.stat().st_size > 500:
            frames.append(target)
    return frames


def pick_best_frame(frames: list[Path]) -> Path | None:
    """En kontrastli (en 'bilgi dolu') kareyi secer."""
    best: tuple[float, Path] | None = None
    for frame in frames:
        try:
            with Image.open(frame) as img:
                small = img.convert("L").resize((64, 114))
                std = ImageStat.Stat(small).stddev[0]
        except Exception:
            continue
        if best is None or std > best[0]:
            best = (std, frame)
    return best[1] if best else None


def cover_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Gorseli 1080x1920'e kirpar (en-boy oranini koruyarak)."""
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = int(height * src_ratio)
    else:
        new_w = width
        new_h = int(width / src_ratio)
    img = img.resize((max(new_w, 1), max(new_h, 1)), Image.LANCZOS)
    left = (img.width - width) // 2
    top = (img.height - height) // 2
    return img.crop((left, top, left + width, top + height))


def draw_gradient_overlay(img: Image.Image) -> Image.Image:
    """Ust koyulastirma + alt siyah band -> yazi okunur, konu hala gorunur."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(0, 520):
        alpha = int(165 * (1 - y / 520))
        odraw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    for y in range(H - 760, H):
        alpha = int(235 * ((y - (H - 760)) / 760))
        odraw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--video", default="", help="output/final_short.mp4 (konu karesi icin)")
    parser.add_argument("--topic", default="", help="kisa konu rozeti (Bilim/Tarih/Uzay)")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    title = (args.title or "BILIM").strip()
    if "#Shorts" in title:
        title = title.replace("#Shorts", "").strip()

    # --- 1) Konu karesi: videodan en kontrastli kare -----------------------------
    base_img: Image.Image | None = None
    video_path = Path(args.video) if args.video else None
    # Esik dusuk tutulur: kucuk/duz renkli test videolari da gecerli birer mp4'tur
    # (gecerlilik ffmpeg kare alma adiminda dogrulanir).
    if video_path and video_path.exists() and video_path.stat().st_size > 1000:
        with tempfile.TemporaryDirectory() as tmp:
            frames = extract_candidate_frames(video_path, Path(tmp))
            best = pick_best_frame(frames)
            if best:
                with Image.open(best) as raw:
                    base_img = cover_crop(raw.convert("RGB"), W, H)
        if base_img is not None:
            base_img = ImageEnhance.Color(base_img).enhance(1.12)
            base_img = ImageEnhance.Contrast(base_img).enhance(1.08)
            print(f"[*] Konu karesi videodan alindi ({video_path.name}).")

    if base_img is None:
        # --- Eski davranis: saf metin karti (konu karesi bulunamadi) ------------
        img = Image.new("RGB", (W, H), (8, 8, 12))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            ratio = y / H
            draw.line([(0, y), (W, y)],
                      fill=(int(10 + 70 * ratio), int(6 + 8 * ratio), int(12 + 14 * ratio)))
        draw.rectangle([0, 120, W, 300], fill=(196, 22, 32))
        band_font = fit_font(draw, "SON BULMA", W - 120, 150)
        bbox = draw.textbbox((0, 0), "SON BULMA", font=band_font)
        draw.text(((W - (bbox[2] - bbox[0])) / 2, 210 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
                  "SON BULMA", font=band_font, fill=(255, 255, 255))
    else:
        img = draw_gradient_overlay(base_img)
        draw = ImageDraw.Draw(img)

    # --- 2) Konu rozeti (kirmizi etiket) -> ustte, baslik onun altinda ---------
    topic = (args.topic or "").strip().upper()[:18]
    title_top = 420
    if topic:
        chip_font = fit_font(draw, topic, 640, 74, 44)
        bbox = draw.textbbox((0, 0), topic, font=chip_font)
        chip_w = bbox[2] - bbox[0] + 70
        chip_h = bbox[3] - bbox[1] + 44
        cx, cy = (W - chip_w) / 2, 40
        draw.rounded_rectangle([cx, cy, cx + chip_w, cy + chip_h], radius=18, fill=(196, 22, 32))
        draw.text((cx + 35, cy + 18), topic, font=chip_font, fill=(255, 255, 255))
        title_top = 210

    # --- 3) Baslik (siyah dis konturlu sari) -----------------------------------
    title_font = fit_font(draw, title, W - 140, 132)
    lines = wrap(draw, title, title_font, W - 140)
    y = title_top
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (W - (bbox[2] - bbox[0])) / 2
        for dx, dy in ((-6, 0), (6, 0), (0, -6), (0, 6), (-5, -5), (5, 5), (-5, 5), (5, -5)):
            draw.text((x + dx, y + dy), line, font=title_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=title_font, fill=YELLOW)
        y += int(bbox[3] - bbox[1]) + 26


    # --- 4) Kirmizi "ABONE OL" butonu + sari ok (konuya isaret) -----------------
    btn_y = H - 430
    draw.rounded_rectangle([140, btn_y, W - 140, btn_y + 190], radius=44, fill=RED)
    btn_font = fit_font(draw, "ABONE OL", W - 380, 116, 60)
    bbox = draw.textbbox((0, 0), "ABONE OL", font=btn_font)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, btn_y + 95 - (bbox[3] - bbox[1]) / 2 - bbox[1]),
              "ABONE OL", font=btn_font, fill=(255, 255, 255))

    # Ok KONU CERCEVESINE (yukari) isaret eder: denetim "konu nesnesi net olsun" diyor.
    arrow_top = btn_y - 250
    arrow = [
        (W // 2 - 110, arrow_top + 170),
        (W // 2 + 110, arrow_top + 170),
        (W // 2, arrow_top),
    ]
    draw.polygon(arrow, fill=YELLOW)
    draw.rectangle([W // 2 - 26, arrow_top + 150, W // 2 + 26, arrow_top + 210], fill=YELLOW)

    img.save(out, "JPEG", quality=92)
    size_kb = round(out.stat().st_size / 1024)
    mode = "konu kareli" if base_img is not None else "metin karti"
    print(f"[*] Yerel yedek kapak uretildi ({mode}): {out} ({size_kb} KB, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
