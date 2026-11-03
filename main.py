#!/usr/bin/env python3
"""
FAZ 6: ANA ORKESTRASYON MOTORU (main.py)
Uçtan uca otomasyon: İçerik -> Montaj -> YouTube Backdoor Yükleme.
Sıfır hata toleransı, tam loglama, gerçek dünya çalışması.
"""
import os
import sys
import logging
import subprocess
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

def run_step(step_name: str, command: list) -> bool:
    logging.info(f"[*] BAŞLATILIYOR: {step_name}")
    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True
        )
        logging.info(f"[+] BAŞARILI: {step_name}")
        if result.stdout:
            for line in result.stdout.splitlines():
                if "INFO" in line or "BAŞARILI" in line or "🚀" in line:
                    logging.info(f"  -> {line.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"[-] KRİTİK HATA: {step_name}")
        logging.error(f"Stdout: {e.stdout}")
        logging.error(f"Stderr: {e.stderr}")
        return False

def main():
    logging.info("="*70)
    logging.info(" 🚀 YOUTUBE SHORTS OTOMASYON ORKESTRATÖRÜ BAŞLATILIYOR 🚀")
    logging.info("="*70)

    # 1. Adım: İçerik Üretimi
    step1_ok = run_step(
        "FAZ 2: İçerik ve Ses Üretimi",
        [sys.executable, str(BASE_DIR / "content_engine.py"), "--force-fallback"]
    )
    if not step1_ok:
        logging.error("İçerik üretimi başarısız. Orkestrasyon durduruldu.")
        sys.exit(1)

    # 2. Adım: Medya İşleme ve Montaj
    step2_ok = run_step(
        "FAZ 3: FFmpeg Montaj ve Altyazı",
        [sys.executable, str(BASE_DIR / "src" / "media_processing" / "media_processor.py")]
    )
    if not step2_ok:
        logging.error("Medya işleme başarısız. Orkestrasyon durduruldu.")
        sys.exit(1)

    # 3. Adım: YouTube Backdoor Yükleme
    cookies_path = BASE_DIR / "cookies.json"
    if not cookies_path.exists():
        logging.warning("[!] UYARI: cookies.json bulunamadı! İlk headless çalıştırmada 2FA hatası alabilir.")
    
    step3_ok = run_step(
        "FAZ 5: Playwright YouTube Studio Yükleme",
        ["node", str(BASE_DIR / "youtube_studio_uploader.js")]
    )
    if not step3_ok:
        logging.error("YouTube yükleme başarısız. Orkestrasyon durduruldu.")
        sys.exit(1)

    logging.info("="*70)
    logging.info(" ✅ TÜM FAZLAR BAŞARIYLA TAMAMLANDI. PARA MAKİNESİ ÇALIŞIYOR. ✅")
    logging.info("="*70)

if __name__ == "__main__":
    main()
