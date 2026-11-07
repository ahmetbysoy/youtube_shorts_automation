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
    return lines


def layout_title(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int):
    """Fit every line including its stroke; fail closed rather than crop a long word."""
    for size in range(126, 7, -2):
        font = pick_font(size)
        lines = wrap(draw, text, font, max_width - 10)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=5) for line in lines]
        widths = [box[2] - box[0] for box in boxes]
        height = sum(box[3] - box[1] + 22 for box in boxes)
        if lines and len(lines) <= 5 and max(widths) <= max_width and height <= max_height:
            return font, lines
    raise ValueError("Kapak başlığı taşmadan yerleştirilemedi")


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
    parser.add_argument("--strict-subject", action="store_true", help="konu eslesmesi dogrulanmazsa rastgele kare yerine metin karti")
    parser.add_argument("--base-image", default="", help="hazir (orn. ucretsiz AI) gorsel; verilirse video karesi yerine bu kullanilir")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    title = (args.title or "BILIM").strip()
    if "#Shorts" in title:
        title = title.replace("#Shorts", "").strip()

    # --- 1) Konu karesi: videodan en kontrastli kare -----------------------------
    base_img: Image.Image | None = None
    base_image_path = Path(args.base_image) if args.base_image else None
    if base_image_path and base_image_path.exists() and base_image_path.stat().st_size > 1000:
        try:
            with Image.open(base_image_path) as raw:
                base_img = cover_crop(raw.convert("RGB"), W, H)
            print(f"[*] Hazir gorsel kapak tabani olarak kullanildi: {base_image_path.name}")
        except Exception as exc:  # bozuk indirme -> video karesine dus
            print(f"[!] Hazir gorsel acilamadi ({exc}); video karesine dusuluyor.")
            base_img = None
    video_path = Path(args.video) if (args.video and base_img is None) else None
    # Esik dusuk tutulur: kucuk/duz renkli test videolari da gecerli birer mp4'tur
    # (gecerlilik ffmpeg kare alma adiminda dogrulanir).
    if video_path and video_path.exists() and video_path.stat().st_size > 1000:
        with tempfile.TemporaryDirectory() as tmp:
            frames = extract_candidate_frames(video_path, Path(tmp))
            best = None
            if args.strict_subject and frames:
                from gemini_frame_selector import select_subject_frame
                selected = select_subject_frame(title, frames)
                if selected is not None:
                    best = frames[selected]
            elif not args.strict_subject:
                # Backward-compatible explicit non-strict mode: contrast is not semantic matching.
                best = pick_best_frame(frames)
            if best:
                with Image.open(best) as raw:
                    base_img = cover_crop(raw.convert("RGB"), W, H)
        if base_img is not None:
            base_img = ImageEnhance.Color(base_img).enhance(1.12)
            base_img = ImageEnhance.Contrast(base_img).enhance(1.08)
            print(f"[*] Secilen video karesi alindi ({video_path.name}); model karari insan dogrulamasi degildir.")

    if base_img is None:
        # Neutral, honest artwork; never imply a contrast-selected frame depicts the subject.
        img = Image.new("RGB", (W, H), (8, 12, 25))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            ratio = y / H
            draw.line([(0, y), (W, y)], fill=(int(8 + 18 * ratio), int(12 + 16 * ratio), int(25 + 22 * ratio)))
        # Decorative scene is explicitly illustrative; do not represent an actual photo.
        subject = (title + " " + args.topic).lower()
        cx, cy = W // 2, 1110
        if "muz" in subject:
            # Decorative banana silhouette, not a scientific illustration.
            draw.ellipse([145, 740, 935, 1530], fill=(34, 35, 45), outline=(65, 71, 80), width=5)
            draw.arc([250, 825, 820, 1375], 25, 155, fill=(245, 205, 73), width=105)
            draw.line([(285, 1180), (245, 1135)], fill=(245, 205, 73), width=50)
            draw.line([(790, 1175), (830, 1130)], fill=(245, 205, 73), width=50)
        elif "emu" in subject:
            # A stylized long-necked bird, not a depiction of a specific animal or event.
            draw.ellipse([145, 740, 935, 1530], fill=(34, 35, 45), outline=(65, 71, 80), width=5)
            draw.ellipse([310, 1000, 710, 1250], fill=(221, 185, 87))
            draw.line([(630, 1100), (675, 920), (720, 840)], fill=(221, 185, 87), width=65)
            draw.ellipse([685, 795, 780, 880], fill=(221, 185, 87))
            draw.polygon([(770, 815), (835, 850), (770, 865)], fill=(242, 208, 117))
            draw.line([(425, 1220), (400, 1410)], fill=(221, 185, 87), width=20)
            draw.line([(570, 1220), (595, 1410)], fill=(221, 185, 87), width=20)
        elif any(word in subject for word in ("zanzibar", "savaş", "savas", "savaşı")):
            # Simplified ship and sea, not a claimed reconstruction of a historical vessel.
            draw.ellipse([145, 740, 935, 1530], fill=(22, 35, 52), outline=(49, 65, 80), width=5)
            draw.line([(250, 1240), (830, 1240)], fill=(237, 191, 60), width=12)
            draw.polygon([(275, 1170), (800, 1170), (720, 1290), (345, 1290)], fill=(239, 197, 70))
            draw.rectangle([385, 1055, 680, 1170], fill=(200, 159, 54))
            draw.rectangle([490, 925, 515, 1055], fill=(238, 197, 78))
            draw.polygon([(515, 930), (515, 1040), (690, 1040)], fill=(247, 215, 123))
            for y in (1330, 1375, 1420):
                draw.arc([255, y-35, 825, y+45], 0, 180, fill=(72, 119, 143), width=8)
        elif any(word in subject for word in ("volkan", "yanardağ", "yanardag", "krakatoa", "pompeii", "vezüv")):
            draw.ellipse([145, 740, 935, 1530], fill=(34, 30, 42), outline=(65, 52, 58), width=5)
            draw.polygon([(235, 1380), (445, 1020), (565, 1020), (850, 1380)], fill=(94, 91, 95))
            draw.polygon([(445, 1020), (565, 1020), (520, 1080), (465, 1060)], fill=(244, 111, 46))
            draw.line([(500, 1020), (465, 895), (390, 825)], fill=(245, 161, 59), width=22)
            draw.line([(510, 1010), (565, 890), (640, 830)], fill=(238, 105, 46), width=18)
            draw.ellipse([380, 780, 420, 820], fill=(249, 187, 64))
            draw.ellipse([640, 775, 672, 807], fill=(247, 151, 52))
        elif any(word in subject for word in ("uzay", "güneş", "gunes", "yıldız", "yildiz", "gezegen", "venüs", "venüs", "uranüs", "neptün", "voyager")):
            draw.ellipse([230, 805, 850, 1425], fill=(32, 57, 91), outline=(232, 187, 62), width=12)
            draw.ellipse([345, 890, 430, 975], fill=(75, 109, 149))
            draw.ellipse([590, 1120, 755, 1285], fill=(60, 89, 131))
            draw.arc([145, 950, 935, 1270], 10, 175, fill=(237, 194, 76), width=15)
            for x,y,r in [(180,820,8),(850,780,10),(850,1410,7),(220,1430,10),(735,715,6)]:draw.ellipse([x-r,y-r,x+r,y+r],fill=(245,220,135))
        elif any(word in subject for word in ("okyanus", "deniz", "mariana", "ahtapot")):
            draw.ellipse([145, 740, 935, 1530], fill=(16, 44, 61), outline=(49, 81, 94), width=5)
            for y in (920, 1000, 1080, 1160, 1240, 1320):
                draw.arc([205,y-55,875,y+55], 0, 180, fill=(72, 155, 174), width=14)
            draw.ellipse([455, 1110, 625, 1280], fill=(238, 197, 78))
        else:
            draw.ellipse([205, 775, 875, 1445], outline=(58, 73, 92), width=7)
            draw.ellipse([265, 835, 815, 1385], outline=(100, 88, 62), width=4)
            draw.polygon([(540, 905), (605, 1090), (800, 1110), (645, 1225), (695, 1400), (540, 1300), (385, 1400), (435, 1225), (280, 1110), (475, 1090)], fill=(232, 187, 63))
        art_font = pick_font(32)
        draw.text((70, 1510), "TEMSİLİ GÖRSEL", font=art_font, fill=(167, 177, 188))
    else:
        img = draw_gradient_overlay(base_img)
        draw = ImageDraw.Draw(img)

    # Header and title occupy a bounded area; long titles wrap rather than overlap.
    turkish_upper = lambda text: text.replace("i", "İ").replace("ı", "I").upper()
    topic = turkish_upper((args.topic or "KISA BİLGİ").strip())[:20]
    chip_font = fit_font(draw, topic, 700, 52, 36)
    box = draw.textbbox((0, 0), topic, font=chip_font)
    chip_w = box[2] - box[0] + 70
    draw.rounded_rectangle([60, 65, 60 + chip_w, 150], radius=16, fill=YELLOW)
    draw.text((95, 79 - box[1]), topic, font=chip_font, fill=(12, 16, 26))
    title_text = turkish_upper(title.strip())
    title_font, lines = layout_title(draw, title_text, W - 120, 520)
    y = 225
    for line in lines:
        box = draw.textbbox((0, 0), line, font=title_font, stroke_width=4)
        x = 60
        draw.text((x, y), line, font=title_font, fill=(255,255,255), stroke_width=5, stroke_fill=(0,0,0))
        y += box[3] - box[1] + 22
    draw.rounded_rectangle([60, 1690, 450, 1785], radius=18, fill=RED)
    btn_font = pick_font(52)
    draw.text((92, 1704), "ABONE OL", font=btn_font, fill=(255,255,255))
    draw.line([(60, 1830), (W - 60, 1830)], fill=YELLOW, width=7)

    img.save(out, "JPEG", quality=92)
    size_kb = round(out.stat().st_size / 1024)
    mode = "hazir gorselli" if (base_img is not None and base_image_path and video_path is None) else ("konu kareli" if base_img is not None else "metin karti")
    print(f"[*] Yerel yedek kapak uretildi ({mode}): {out} ({size_kb} KB, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
