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


def run_step(
    step_name: str,
    command: list,
    env_overrides: dict | None = None,
    timeout_seconds: int = 900,
) -> bool:
    """Alt süreci canlı loglarla çalıştır; her faz için kesin timeout uygula."""
    logging.info(f"[*] BAŞLATILIYOR: {step_name}")
    logging.info(f"[*] KOMUT: {' '.join(map(str, command))}")
    step_env = os.environ.copy()
    if env_overrides:
        step_env.update(env_overrides)
    try:
        # stdout/stderr doğrudan Actions konsoluna akar; capture_output tamponu yok.
        subprocess.run(
            command,
            cwd=BASE_DIR,
            env=step_env,
            check=True,
            stdout=sys.stdout,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout_seconds,
        )
        logging.info(f"[+] BAŞARILI: {step_name}")
        return True
    except subprocess.TimeoutExpired:
        logging.error(
            f"[-] TIMEOUT: {step_name} {timeout_seconds} saniyede tamamlanmadı; "
            "alt süreç sonlandırıldı."
        )
        return False
    except subprocess.CalledProcessError as e:
        # 42 = YouTube günlük yükleme kotası doldu -> planlı atlama.
        if e.returncode == 42:
            logging.warning(f"[⏭️ ATLANDI] {step_name}: YouTube günlük yükleme kotanı doldu.")
            return True
        # 43 = Google kimlik dogrulama modali -> telefon onayi beklenmedi, video TASLAK kaldi
        # (draft_publisher.yml 20 dk icinde yayinlar). Planli durum, kosu kirmizi olmaz.
        if e.returncode == 43:
            logging.warning(f"[📝 TASLAK] {step_name}: kimlik modali cikti, video taslak olarak birakildi.")
            return True
        logging.error(f"[-] KRİTİK HATA: {step_name} (exit={e.returncode})")
        return False
    except OSError as e:
        logging.exception(f"[-] Alt süreç başlatılamadı: {step_name}: {e}")
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
        timeout_seconds=600,
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
        timeout_seconds=1200,
    )
    if not step2_ok:
        logging.error("Medya işleme başarısız. Orkestrasyon durduruldu.")
        write_status("error", args.channel_id, stage="media")
        sys.exit(1)

    # 2.5 Adım: Kapak karesini videoya göm (kalıcı kapak çözümü; ayrı kapak yüklemesi yok).
    # Başarısız olsa bile yayın durmaz: script video'yu dokunmadan bırakır ve 0 döner.
    run_step(
        "FAZ 3.5: Kapak Karesi Gömme (ilk 0.6 sn)",
        [sys.executable, str(BASE_DIR / "scripts" / "embed_cover_frame.py")],
        env_overrides=step_env,
        timeout_seconds=600,
    )

    # 3. Adım: YouTube Studio PUBLIC Yükleme
    cookies_path = BASE_DIR / "cookies.json"
    if not cookies_path.exists():
        logging.warning("[!] UYARI: cookies.json bulunamadı! İlk headless çalıştırmada 2FA hatası alabilir.")

    step3_ok = run_step(
        "FAZ 5: Playwright YouTube Studio Yükleme",
        ["node", str(BASE_DIR / "youtube_studio_uploader.js")],
        env_overrides=step_env,
        timeout_seconds=1200,
    )
    if not step3_ok:
        logging.error("YouTube yükleme başarısız. Orkestrasyon durduruldu.")
        write_status("error", args.channel_id, stage="upload")
        sys.exit(1)

    published = _published_video_info()
    auth_state = ""
    try:
        auth_state = json.loads((LOG_DIR / "auth_status.json").read_text(encoding="utf-8")).get("state", "")
    except Exception:
        pass
    if auth_state == "draft_left":
        write_status("draft_left", args.channel_id, stage="upload", **{k: v for k, v in published.items() if k != "visibility"})
    elif published:
        write_status("uploaded", args.channel_id, **published)
    else:
        # exit code 42 = gunkluk yukleme kotasi doldu -> planli atlama
        write_status("quota_skipped", args.channel_id, stage="upload")

    logging.info("=" * 70)
    logging.info(" ✅ TÜM FAZLAR BAŞARIYLA TAMAMLANDI. PARA MAKİNESİ ÇALIŞIYOR. ✅")
    logging.info("=" * 70)

if __name__ == "__main__":
    main()
