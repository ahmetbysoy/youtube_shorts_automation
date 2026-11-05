#!/usr/bin/env python3
"""
FAZ 6–8: ANA ORKESTRASYON MOTORU (main.py)
Uçtan uca otomasyon: Benzersiz İçerik (15dk Seed) -> Mobil-Optimize Montaj -> YouTube Studio PUBLIC Yayın.
Sıfır hata toleransı, tam loglama, gerçek dünya çalışması.
"""
import argparse
import json
import os
import sys
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Yollar
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# .env yükle
load_dotenv(BASE_DIR / ".env")

# Loglama
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def write_status(status: str, channel_id: str, **extra) -> None:
    """Tek satirlik kosu durumu -> logs/run_status.json (CI ozeti + artifact)."""
    payload = {
        "status": status,
        "channel_id": str(channel_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(extra)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (LOG_DIR / "run_status.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logging.info(f"[*] RUN DURUMU: {status} {payload}")
    except Exception as exc:  # pragma: no cover - dosya yazma hatasi uretimi durdurmaz
        logging.warning(f"[!] run_status.json yazilamadi: {exc}")


def _published_video_info() -> dict:
    """Yayinlanan video bilgisini topla (id + URL + baslik)."""
    info: dict = {}
    vid_file = LOG_DIR / "channel_video_id.txt"
    if vid_file.exists():
        info["video_id"] = vid_file.read_text(encoding="utf-8").strip()
    auth_file = LOG_DIR / "auth_status.json"
    if auth_file.exists():
        try:
            auth = json.loads(auth_file.read_text(encoding="utf-8"))
            info.setdefault("video_id", auth.get("videoId") or auth.get("video_id") or "")
            info.setdefault("url", auth.get("videoUrl") or auth.get("url") or "")
            info.setdefault("title", auth.get("title") or "")
            info.setdefault("visibility", auth.get("visibility") or "PUBLIC")
        except Exception:
            pass
    vid = info.get("video_id")
    if vid and not info.get("url"):
        info["url"] = f"https://youtube.com/shorts/{vid}"
    return {k: v for k, v in info.items() if v}


def run_step(step_name: str, command: list, env_overrides: dict | None = None) -> bool:
    logging.info(f"[*] BAŞLATILIYOR: {step_name}")
    step_env = os.environ.copy()
    if env_overrides:
        step_env.update(env_overrides)
    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            env=step_env,
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"[+] BAŞARILI: {step_name}")
        if result.stdout:
            for line in result.stdout.splitlines():
                show_tokens = (
                    "INFO", "BAŞARILI", "🚀", "unsharp", "eq=", "Başlık", "Link :", "Durum:",
                    # Faz 11: viral metadata + AI kapak kanitlari CI logunda gorunsun
                    "AI ile dikkat", "Kapak resmi", "Kapak görseli", "Etkileşim CTA",
                    "Trend hashtag", "YÜKLEME ATLANDI", "günlük yükleme",
                    # Faz 12: silahlandirilmis kapak + zorunlu basari satiri
                    "SİLAHLANDIRILMIŞ", "KAPAK RESMİ", "Yayınlanan video ID",
                    # Faz 12.6: kapak hata/ fallback mesajlari da gorunur olsun
                    "Kapak üretimi", "Kapak resmi yüklenemedi", "Kapak indirme hatası",
                    "Kapak servisi", "Yerel yedek kapak", "rate limit", "[KAPAK]",
                    # Faz 13: aciklama guvenligi + kaynak satiri kanitlari
                    "Kaynak:", "KAYNAK", "GUVENLIK", "CTA guvenlik",
                    "seçimi doğrulandı", "Studio PUBLIC", "YAYINLAMA İŞLEMİ",
                )
                if any(tok in line for tok in show_tokens):
                    logging.info(f"  -> {line.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        # 42 = YouTube günlük yükleme kotası doldu -> bu bir HATA değil, planlı bir atlama
        if e.returncode == 42:
            logging.warning(f"[⏭️ ATLANDI] {step_name}: YouTube günlük yükleme kotanı doldu.")
            for line in (e.stdout or "").splitlines():
                if any(tok in line for tok in ("Kapak", "CTA", "hashtag", "YÜKLEME", "kota", "günlük")):
                    logging.info(f"  -> {line.strip()}")
            return True
        logging.error(f"[-] KRİTİK HATA: {step_name}")
        logging.error(f"Stdout: {e.stdout}")
        logging.error(f"Stderr: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Otomasyon Ana Orkestratörü")
    parser.add_argument(
        "--channel_id",
        type=str,
        default=os.environ.get("MATRIX_CHANNEL_ID", "1"),
        help="Matrix kanal ID'si",
    )
    args = parser.parse_args()

    os.environ["MATRIX_CHANNEL_ID"] = str(args.channel_id)
    step_env = {"MATRIX_CHANNEL_ID": str(args.channel_id)}

    logging.info("=" * 70)
    logging.info(" 🚀 YOUTUBE SHORTS OTOMASYON ORKESTRATÖRÜ BAŞLATILIYOR 🚀")
    logging.info("=" * 70)
    logging.info(f"[*] KANAL ID: {args.channel_id} için işlem başlatılıyor.")
    write_status("started", args.channel_id)

    # 1. Adım: İçerik Üretimi (15dk Benzersizlik Tohumu ile)
    step1_ok = run_step(
        "FAZ 2: İçerik ve Ses Üretimi",
        [sys.executable, str(BASE_DIR / "content_engine.py"), "--force-fallback", "--channel_id", args.channel_id],
        env_overrides=step_env,
    )
    if not step1_ok:
        logging.error("İçerik üretimi başarısız. Orkestrasyon durduruldu.")
        write_status("error", args.channel_id, stage="content")
        sys.exit(1)

    # 2. Adım: Mobil-Optimize Medya İşleme ve Montaj (unsharp + eq + MarginV=250)
    step2_ok = run_step(
        "FAZ 3: FFmpeg Montaj ve Altyazı",
        [sys.executable, str(BASE_DIR / "src" / "media_processing" / "media_processor.py")],
        env_overrides=step_env,
    )
    if not step2_ok:
        logging.error("Medya işleme başarısız. Orkestrasyon durduruldu.")
        write_status("error", args.channel_id, stage="media")
        sys.exit(1)

    # 3. Adım: YouTube Studio PUBLIC Yükleme
    cookies_path = BASE_DIR / "cookies.json"
    if not cookies_path.exists():
        logging.warning("[!] UYARI: cookies.json bulunamadı! İlk headless çalıştırmada 2FA hatası alabilir.")

    step3_ok = run_step(
        "FAZ 5: Playwright YouTube Studio Yükleme",
        ["node", str(BASE_DIR / "youtube_studio_uploader.js")],
        env_overrides=step_env,
    )
    if not step3_ok:
        logging.error("YouTube yükleme başarısız. Orkestrasyon durduruldu.")
        write_status("error", args.channel_id, stage="upload")
        sys.exit(1)

    published = _published_video_info()
    if published:
        write_status("uploaded", args.channel_id, **published)
    else:
        # exit code 42 = gunkluk yukleme kotasi doldu -> planli atlama
        write_status("quota_skipped", args.channel_id, stage="upload")

    logging.info("=" * 70)
    logging.info(" ✅ TÜM FAZLAR BAŞARIYLA TAMAMLANDI. PARA MAKİNESİ ÇALIŞIYOR. ✅")
    logging.info("=" * 70)

if __name__ == "__main__":
    main()
