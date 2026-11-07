#!/usr/bin/env python3
"""FAZ 3.5 - Kapak karesini videonun ICINE gomer (kalici kapak cozumu).

NEDEN (2026-11-07, kullanici karari):
  Studio'ya ayri kapak dosyasi yuklemek gunluk "ozel kucuk resim" kotasina
  carpiyor ve her yuklemede ekstra deneme/is yuku uretiyordu. Kapak tasarimi
  videonun ilk karelerine gomulunce YouTube'un kendi kare secimi (otomatik
  adaylar / "kare sec") o goruntuyu kullanabilir; ayri yukleme gerekmez.

AKIS:
  1) Kapak gorseli:
       a) ucretsiz, anahtarsiz image.pollinations.ai (script.json -> thumbnail_prompt)
          -> konuyla ilgili dramatik/eglenceli gorsel (402/429 olursa kisa tekrar),
       b) servis cevap vermezse videonun en kontrastli karesi.
     Ikisi de scripts/generate_fallback_thumbnail.py ile baslik + rozet alir
     -> output/cover.jpg (1080x1920).
  2) FFmpeg: kapak, videonun ilk COVER_SECONDS saniyesine bindirilir (overlay).
     Ses ve altyazi akisi degismez; sure uzamaz; sonunda kisa alpha-fade.
  3) Her hata guvenli: video dokunulmadan kalir, cikis kodu 0 (yayin durmaz),
     log satirlari [KAPAK] ile baslar.

Kullanim:
  python scripts/embed_cover_frame.py --video output/final_short.mp4 --script script.json
  Ortam: COVER_SECONDS (vars. 0.6), COVER_AI=0 -> AI servisini atla (test/offline)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
GEN_SCRIPT = BASE_DIR / "scripts" / "generate_fallback_thumbnail.py"

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


def _trim_edges(img_path: Path, ratio: float = 0.04) -> None:
    """Kenarlardan kucuk bir pay kirpar (servis filigrani sag altta kaliyor)."""
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            w, h = im.size
            dx, dy = int(w * ratio), int(h * ratio)
            im.convert("RGB").crop((dx, dy, w - dx, h - dy)).save(img_path, "JPEG", quality=94)
    except Exception as exc:
        log(f"kenar kirpma atlandi: {exc}")


def fetch_ai_image(prompt: str, out_path: Path, attempts: int = 3, timeout: int = 90) -> bool:
    """Ucretsiz pollinations.ai'den gorsel indirir. Basarisizsa False (loglu)."""
    if not prompt:
        return False
    encoded = urllib.parse.quote(f"{prompt}, {STYLE_SUFFIX}")
    for i in range(attempts):
        seed = random.randint(1, 10**9)
        url = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width=1080&height=1920&nologo=true&model=flux&seed={seed}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "")
            if len(data) < 20_000 or "image" not in ctype:
                log(f"AI gorsel yaniti gecersiz (deneme {i + 1}: {len(data)} B, {ctype or '?'}).")
            else:
                out_path.write_bytes(data)
                _trim_edges(out_path)
                log(f"AI gorsel indirildi ({len(data) // 1024} KB, deneme {i + 1}).")
                return True
        except Exception as exc:  # HTTP 402/429/timeout vb.
            log(f"AI gorsel servisi basarisiz (deneme {i + 1}/{attempts}): {str(exc)[:120]}")
        if i < attempts - 1:
            time.sleep(8 * (i + 1))
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
    fade = min(0.2, seconds / 3)
    fade_start = max(0.0, seconds - fade)
    filter_complex = (
        f"[1:v]scale=1080:1920,setsar=1,format=yuva420p,"
        f"fade=t=out:st={fade_start:.3f}:d={fade:.3f}:alpha=1[cv];"
        f"[0:v][cv]overlay=0:0:eof_action=pass[v]"
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
    ap.add_argument("--seconds", type=float, default=float(os.environ.get("COVER_SECONDS", "0.6")))
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
    prompt = str(data.get("thumbnail_prompt") or "").strip()
    use_ai = not args.no_ai and os.environ.get("COVER_AI", "1") != "0"

    cover_out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cover_") as tmp_s:
        tmp = Path(tmp_s)
        ai_img = tmp / "ai.jpg"
        got_ai = fetch_ai_image(prompt, ai_img) if use_ai else False
        if not got_ai:
            log("AI gorsel yok -> videonun en kontrastli karesi kapak tabani olacak.")
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
        f"({'AI gorsel' if got_ai else 'video karesi'} + baslik) -> {video.name}; kapak: {cover_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
