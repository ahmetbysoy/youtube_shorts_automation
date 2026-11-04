#!/usr/bin/env python3
"""
Faz 4 - Görev 4: YouTube Data API v3 Private Yükleme ve Onay Mekanizması
Gerçek API'ler, chunked upload, quota yönetimi, sıfır basitleştirme.
"""

import os
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# Yol tanımlamaları
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CLIENT_SECRET_PATH = BASE_DIR / "client_secret.json"
TOKEN_PATH = BASE_DIR / "token.json"
VIDEO_PATH = BASE_DIR / "output" / "final_short.mp4"
SCRIPT_JSON_PATH = BASE_DIR / "script.json"
PENDING_APPROVAL_PATH = BASE_DIR / "pending_approval.json"
LOG_FILE = BASE_DIR / "logs" / "youtube_uploader.log"

# Loglama ayarları
LOG_FILE.parent.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

class YouTubeUploader:
    def __init__(self):
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl"
        ]
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        if not CLIENT_SECRET_PATH.exists():
            logging.error("KRİTİK HATA: client_secret.json bulunamadı! Lütfen dosyayı proje kök dizinine koy.")
            sys.exit(1)
        
        if not TOKEN_PATH.exists():
            logging.error("KRİTİK HATA: token.json bulunamadı! Lütfen önce oauth_handler.py ile yetkilendirme yapın.")
            sys.exit(1)

        try:
            self.creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), self.scopes)
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logging.info("Token süresi dolmuş, refresh_token ile yenileniyor...")
                    from google.auth.transport.requests import Request
                    self.creds.refresh(Request())
                    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                        f.write(self.creds.to_json())
                else:
                    logging.error("Geçersiz token. Lütfen oauth_handler.py ile yeniden yetkilendirin.")
                    sys.exit(1)
            
            self.service = build("youtube", "v3", credentials=self.creds)
            logging.info("YouTube Data API v3 servisi başarıyla başlatıldı.")
        except Exception as e:
            logging.error(f"Kimlik doğrulama hatası: {e}")
            sys.exit(1)

    def upload_video_private(self, video_path: Path, title: str, description: str, tags: list, category_id: str = "22") -> str | None:
        """
        Videoyu YouTube'a 'private' olarak yükler.
        Chunked upload kullanarak büyük dosyaları güvenli şekilde aktarır.
        """
        if not video_path.exists():
            logging.error(f"Video dosyası bulunamadı: {video_path}")
            return None

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": category_id,
                "defaultLanguage": "tr",
                "defaultAudioLanguage": "tr"
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False
            }
        }

        # 5MB chunk size ile güvenilir yükleme
        media = MediaFileUpload(
            str(video_path.resolve()),
            mimetype="video/mp4",
            chunksize=5 * 1024 * 1024,
            resumable=True
        )

        try:
            logging.info(f"Video yükleniyor (Private): {video_path.name} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
            request = self.service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    logging.info(f"Yükleme ilerlemesi: {int(status.progress() * 100)}%")
            
            video_id = response.get("id")
            logging.info(f"BAŞARILI: Video yüklendi! Video ID: {video_id}")
            return video_id

        except HttpError as e:
            error_details = json.loads(e.content.decode("utf-8")) if e.content else {}
            if "quotaExceeded" in str(e):
                logging.error("YOUTUBE API KOTASI AŞILDI! (Günlük 10.000 birim limit). Sistem kuyruğa alacak.")
            else:
                logging.error(f"YouTube API HTTP Hatası: {error_details.get('error', {}).get('message', str(e))}")
            return None
        except Exception as e:
            logging.error(f"Beklenmeyen yükleme hatası: {e}")
            return None

    def make_video_public(self, video_id: str) -> bool:
        """
        Private olarak yüklenen videoyu 'public' yapar.
        """
        try:
            logging.info(f"Video public yapılıyor: {video_id}")
            request = self.service.videos().update(
                part="status",
                body={
                    "id": video_id,
                    "status": {
                        "privacyStatus": "public"
                    }
                }
            )
            response = request.execute()
            logging.info(f"BAŞARILI: Video artık PUBLIC! URL: https://www.youtube.com/watch?v={video_id}")
            return True
        except HttpError as e:
            logging.error(f"Public yapma hatası: {e}")
            return False


def save_pending_approval(video_id: str, title: str):
    """Onay bekleyen videoları JSON dosyasına kaydeder."""
    pending_data = {}
    if PENDING_APPROVAL_PATH.exists():
        with open(PENDING_APPROVAL_PATH, "r", encoding="utf-8") as f:
            try:
                pending_data = json.load(f)
            except json.JSONDecodeError:
                pending_data = {}
    
    pending_data[video_id] = {
        "title": title,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_approval"
    }
    
    with open(PENDING_APPROVAL_PATH, "w", encoding="utf-8") as f:
        json.dump(pending_data, f, indent=2, ensure_ascii=False)
    logging.info(f"Video onay kuyruğuna eklendi: {PENDING_APPROVAL_PATH}")


def run_upload_pipeline():
    if not SCRIPT_JSON_PATH.exists():
        logging.error("script.json bulunamadı! Faz 2 çalıştırılmalı.")
        sys.exit(1)

    with open(SCRIPT_JSON_PATH, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    title = script_data.get("title", "İlginç Bilgi #Shorts")
    description = script_data.get("description", "")
    tags = ["shorts", "ilginçbilgiler", "tarih", "bilim", "yapayzeka"]
    
    uploader = YouTubeUploader()
    video_id = uploader.upload_video_private(VIDEO_PATH, title, description, tags, category_id="27") # 27: Education
    
    if video_id:
        save_pending_approval(video_id, title)
        print("\n" + "="*60)
        print(" 🚀 YÜKLEME TAMAMLANDI - ONAY BEKLİYOR 🚀")
        print("="*60)
        print(f" Video ID       : {video_id}")
        print(f" Başlık         : {title}")
        print(f" Durum          : PRIVATE (Gizli)")
        print(f" Onay Komutu    : python src/youtube_upload/youtube_uploader.py --approve {video_id}")
        print("="*60 + "\n")
    else:
        logging.error("Yükleme başarısız oldu. Logları kontrol edin.")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Shorts Otomatik Yükleyici")
    parser.add_argument("--approve", type=str, help="Video ID'sini public yapmak için girin")
    args = parser.parse_args()

    if args.approve:
        uploader = YouTubeUploader()
        uploader.make_video_public(args.approve)
        
        # JSON'dan kaldır
        if PENDING_APPROVAL_PATH.exists():
            with open(PENDING_APPROVAL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if args.approve in data:
                del data[args.approve]
            with open(PENDING_APPROVAL_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        run_upload_pipeline()
