#!/usr/bin/env python3
"""FAZ 3.5 - Kapak karesini videonun ICINE gomer (kalici kapak cozumu).

NEDEN (2026-11-07, kullanici karari):
  Studio'ya ayri kapak dosyasi yuklemek gunluk "ozel kucuk resim" kotasina
  carpiyor ve her yuklemede ekstra deneme/is yuku uretiyordu. Kapak tasarimi
  videonun ilk karelerine gomulunce YouTube'un kendi kare secimi (otomatik
  adaylar / "kare sec") o goruntuyu kullanabilir; ayri yukleme gerekmez.

AKIS (2026-11-16 duzeltme: pollinations SOKULDU, Gemini kapaga donuldu):
  1) Kapak gorseli:
       a) Gemini web API (gemini_cover.py, GEMINI_COOK cookies ile) — konuyla ilgili
          dramatik/eglenceli gorsel uretir (scripts/gemini_cover.py ile prompt gonderilir).
       b) Gemini basarisiz olursa videonun en iyi (parlak+kontrastli) karesi fallback.
     Ikisi de scripts/generate_fallback_thumbnail.py ile baslik + rozet alir
     -> output/cover.jpg (1080x1920).
  2) FFmpeg: kapak, videonun ilk COVER_SECONDS saniyesine bindirilir (overlay).
     Ses ve altyazi akisi degismez; sure uzamaz; ilk 1.0 saniye tam opak kapak gosterilir.
  3) Her hata guvenli: video dokunulmadan kalir, cikis kodu 0 (yayin durmaz),
     log satirlari [KAPAK] ile baslar.

Kullanim:
  python scripts/embed_cover_frame.py --video output/final_short.mp4 --script script.json
  Ortam: COVER_SECONDS (vars. 1.0), COVER_AI=0 -> AI servisini atla (test/offline)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GEN_SCRIPT = BASE_DIR / "scripts" / "generate_fallback_thumbnail.py"
GEMINI_COVER_SCRIPT = BASE_DIR / "scripts" / "gemini_cover.py"

# Uploader'daki (FAZ 12) stil son eki ile ayni dil: tek net ozne, yazi yok.
STYLE_SUFFIX = ", ".join([
    "YouTube Shorts thumbnail", "vertical 9:16", "single clear subject filling the frame",
    "subject large and centered, instantly recognizable",
    "bright well-lit subject, high contrast against the background",
    "no text, no letters, no logo, no end card, no split screen",
    "hyper-dramatic lighting", "vibrant colors", "glowing elements", "fun and surprising mood",
    "shocked expression", "mysterious or shocking focal point", "8k resolution", "cinematic",
    "highly detailed", "dramatic shadows",
])


def log(msg: str) -> None:
    print(f"[KAPAK] {msg}", flush=True)


def build_title_driven_prompt(title: str, topic: str) -> str:
    """Her video icin kullanicinin belirledigi baslik-odakli dikey kapak promptu."""
    clean_title = (title or "YouTube Shorts").replace("#Shorts", "").strip()
    clean_topic = (topic or "").strip()
    return (
        f'Video title: "{clean_title}". '
        f'Kullanici talimati: "{clean_title}" + "Bu Short videonun izlenme ve etkilesim performansini artiracak; '
        'kapagi goren birinin tiklamamak icin kendini zor tutacagi kadar etkileyici, dikey formatta bir kapak fotografi yap." '
        "Create an exceptionally compelling YouTube Shorts cover image in a vertical 9:16 composition. "
        "The visual must accurately and immediately communicate the exact subject of this title; "
        "use one unmistakable main subject, a surprising or emotionally powerful moment, "
        "an extreme but believable close-up, strong visual storytelling, vivid colors, "
        "dramatic cinematic lighting, crisp details, and very high contrast. "
        "Create a powerful curiosity gap: at a glance, the viewer should feel an irresistible urge to tap "
        "because the image makes them need to know what happens or why this is true. "
        "Make the subject large, instantly readable on a phone screen, and safely inside the central frame. "
        "Do not invent facts or depict an unrelated object. "
        "Do not render text, letters, numbers, logos, watermarks, borders, collages, or split screens. "
        + (f"Topic context: {clean_topic}. " if clean_topic else "")
        + "Photorealistic, polished, premium viral Shorts thumbnail artwork."
        + f" {STYLE_SUFFIX}"
    )


def fetch_gemini_image(prompt: str, out_path: Path, timeout: int = 120) -> bool:
    """Gemini web API (gemini_cover.py) ile gorsel uretir. Basarisizsa False (loglu)."""
    if not prompt:
        return False
    if not GEMINI_COVER_SCRIPT.exists():
        log(f"gemini_cover.py bulunamadi: {GEMINI_COVER_SCRIPT}")
        return False
    cmd = [sys.executable, str(GEMINI_COVER_SCRIPT), str(out_path), "cover", "--prompt", prompt]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0 and out_path.exists() and out_path.stat().st_size > 20_000:
            log(f"Gemini kapak gorseli uretildi ({out_path.stat().st_size // 1024} KB).")
            return True
        err = (res.stderr or res.stdout or "").strip().replace("\n", " ")[:300]
        log(f"Gemini kapak basarisiz (cikis {res.returncode}): {err}")
        return False
    except subprocess.TimeoutExpired:
        log(f"Gemini kapak zamana asimi ({timeout}s).")
        return False
    except Exception as exc:
        log(f"Gemini kapak cagri hatasi: {str(exc)[:150]}")
        return False


def build_cover(title: str, topic: str, video: Path, base_image: Path | None, out: Path) -> bool:
    cmd = [sys.executable, str(GEN_SCRIPT), "--title", title, "--topic", topic, "--out", str(out)]
    if base_image and base_image.exists():
        cmd += ["--base-image", str(base_image)]
    else:
        cmd += ["--video", str(video)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    for line in (res.stdout or "").splitlines():
        if line.strip():
            log(line.strip())
    if res.returncode != 0:
        log(f"kapak uretici hata verdi: {(res.stderr or '').strip()[:200]}")
        return False
    return out.exists() and out.stat().st_size > 5_000


def probe(path: Path) -> dict:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames,duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60)
    st = json.loads(res.stdout or "{}").get("streams") or [{}]
    return st[0]


def overlay_cover(video: Path, cover: Path, seconds: float, out: Path) -> None:
    # Kapak ilk kareden itibaren tam opak kalir; fade uygulanmaz.
    # Boylece YouTube Studio'nun ilk kare adayi kapagin kendisidir.
    filter_complex = (
        "[1:v]scale=1080:1920,setsar=1,format=yuva420p[cv];"
        "[0:v][cv]overlay=0:0:eof_action=pass[v]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(video),
        "-loop", "1", "-framerate", "30", "-t", f"{seconds:.3f}", "-i", str(cover),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "copy", "-movflags", "+faststart", str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(BASE_DIR / "output" / "final_short.mp4"))
    ap.add_argument("--script", default=str(BASE_DIR / "script.json"))
    ap.add_argument("--cover-out", default=str(BASE_DIR / "output" / "cover.jpg"))
    ap.add_argument("--seconds", type=float, default=float(os.environ.get("COVER_SECONDS", "1.0")))
    ap.add_argument("--no-ai", action="store_true", help="AI servisini atla (COVER_AI=0 ile ayni)")
    args = ap.parse_args()

    video = Path(args.video)
    cover_out = Path(args.cover_out)
    if not video.exists():
        log(f"video yok, gomme atlandi: {video}")
        return 0
    try:
        data = json.loads(Path(args.script).read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"script.json okunamadi ({exc}); baslik bos kullanilacak.")
        data = {}
    title = str(data.get("title") or "").replace("#Shorts", "").strip()
    topic = str(data.get("topic") or "").strip()
    # Varsayilan prompt, icerik motorunun eski thumbnail_prompt alanini degil
    # kullanicinin istedigi baslik + CTR odakli sabit talimati kullanir.
    prompt = build_title_driven_prompt(title, topic)
    log(f"Baslik-odakli varsayilan kapak promptu hazir: {title[:100]}")
    use_ai = not args.no_ai and os.environ.get("COVER_AI", "1") != "0"

    cover_out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cover_") as tmp_s:
        tmp = Path(tmp_s)
        ai_img = tmp / "ai.jpg"
        got_ai = fetch_gemini_image(prompt, ai_img) if use_ai else False
        if not got_ai:
            log("Gemini AI gorsel yok -> videonun en iyi (parlak+kontrastli) karesi kapak tabani olacak.")
        if not build_cover(title, topic, video, ai_img if got_ai else None, cover_out):
            log("kapak uretilemedi; video degistirilmedi (YouTube kendi karesini secer).")
            return 0

        before = probe(video)
        tmp_out = tmp / "with_cover.mp4"
        try:
            overlay_cover(video, cover_out, args.seconds, tmp_out)
        except subprocess.CalledProcessError as exc:
            log(f"ffmpeg overlay basarisiz; video degistirilmedi. {(exc.stderr or '')[-300:]}")
            return 0
        except Exception as exc:
            log(f"overlay hatasi; video degistirilmedi: {exc}")
            return 0
        after = probe(tmp_out)
        d0, d1 = float(before.get("duration") or 0), float(after.get("duration") or 0)
        if not tmp_out.exists() or tmp_out.stat().st_size < 10_000 or abs(d0 - d1) > 0.2:
            log(f"dogrulama basarisiz (sure {d0:.2f}->{d1:.2f}); video degistirilmedi.")
            return 0
        shutil.move(str(tmp_out), str(video))
    log(f"kapak videonun ilk {args.seconds:.1f} sn'sine gomuldu "
        f"({'Gemini AI gorsel' if got_ai else 'video karesi'} + baslik) -> {video.name}; kapak: {cover_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
