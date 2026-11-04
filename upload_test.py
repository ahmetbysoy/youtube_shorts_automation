#!/usr/bin/env python3
"""
Faz 1 - Görev 1 (Adım 4): YouTube Data API v3 İlk "Private" Video Yükleme Betiği
---------------------------------------------------------------------------------
Prensip : "Önce gizli (private) yükle, onayla, yayınla"
Kota    : Her `videos.insert` çağrısı günlük 10.000 birimlik ücretsiz kotadan
          yaklaşık 1.600 birim harcar (günde maksimum ~6 video yükleme).

Özellikler:
  - `token.json` (veya CI/CD ortamında `YOUTUBE_TOKEN_JSON` ortam değişkeni) ile bağlanır.
  - Süresi dolmuş `access_token` değerini `refresh_token` kullanarak otomatik yeniler.
  - Güvenlik kilidi: `privacyStatus` kesinlikle `"private"` olarak zorlanır.
  - Kesintiye dayanıklı (resumable) yükleme ve üstel geri çekilmeli (exponential backoff)
    yeniden deneme mekanizması içerir.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

UPLOAD_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
FORCED_PRIVACY_STATUS = "private"
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_RETRIES = 5


def load_credentials(token_path: Path) -> Credentials:
    """`token.json` dosyasından veya `YOUTUBE_TOKEN_JSON` ortam değişkeninden kimlik bilgisi yükler."""
    env_token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()
    if env_token_json:
        info = json.loads(env_token_json)
        creds = Credentials.from_authorized_user_info(info, UPLOAD_SCOPES)
    elif token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), UPLOAD_SCOPES)
    else:
        print(
            f"\n[HATA] '{token_path}' bulunamadı ve 'YOUTUBE_TOKEN_JSON' tanımlı değil!\n"
            "Önce `python youtube_auth.py` komutuyla OAuth2 yetkilendirmesini tamamlayın.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("[BİLGİ] Access token süresi dolmuş; refresh_token ile otomatik yenileniyor...")
            creds.refresh(Request())
            if token_path.exists() and not env_token_json:
                token_path.write_text(creds.to_json(), encoding="utf-8")
                os.chmod(token_path, 0o600)
            print("[BAŞARILI] Access token yenilendi.")
        else:
            print(
                "[HATA] Token geçersiz ve yenilenemiyor (refresh_token eksik veya iptal edilmiş).",
                file=sys.stderr,
            )
            sys.exit(1)

    return creds


def build_video_Metadata(title: str, description: str, category_id: str, tags: list[str]) -> dict:
    """YouTube Data API v3 `videos.insert` gövdesini oluşturur ve `private` kilidini doğrular."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": FORCED_PRIVACY_STATUS,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Kesin güvenlik kilidi: Asla public veya unlisted yüklemeye izin verme
    if body["status"]["privacyStatus"] != "private":
        raise RuntimeError("Güvenlik ihlali: privacyStatus kesinlikle 'private' olmalıdır!")

    return body


def resumable_upload(request) -> dict:
    """Üstel geri çekilmeli (exponential backoff) kesintiye dayanıklı yükleme döngüsü."""
    response = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"[YÜKLENİYOR] İlerleme: %{progress}")
        except HttpError as exc:
            if exc.resp.status in RETRIABLE_STATUS_CODES and retry < MAX_RETRIES:
                retry += 1
                wait_seconds = (2**retry) + random.uniform(0, 1)
                print(
                    f"[UYARI] Geçici sunucu hatası (HTTP {exc.resp.status}). "
                    f"{wait_seconds:.1f} sn sonra yeniden deneniyor ({retry}/{MAX_RETRIES})..."
                )
                time.sleep(wait_seconds)
            else:
                raise

    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Data API v3 Private Test Yükleme Aracı")
    parser.add_argument(
        "--video",
        type=Path,
        default=Path("test.mp4"),
        help="Yüklenecek video dosyası (varsayılan: test.mp4)",
    )
    parser.add_argument(
        "--token-path",
        type=Path,
        default=Path("token.json"),
        help="OAuth2 token dosyası (varsayılan: token.json)",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Test Video 01",
        help='Video başlığı (varsayılan: "Test Video 01")',
    )
    parser.add_argument(
        "--description",
        type=str,
        default="AI Shorts Factory - Faz 1 Otomatik Private Yükleme Testi #Shorts",
        help="Video açıklaması",
    )
    parser.add_argument(
        "--category-id",
        type=str,
        default="27",  # 27 = Education (İlginç Bilgiler / Bilim / Tarih konseptine uygun)
        help="YouTube kategori kimliği (varsayılan: 27 - Eğitim)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API çağrısı yapmadan video dosyasını ve yükleme paketini doğrular (0 kota harcar).",
    )
    args = parser.parse_args()

    if not args.video.exists():
        print(f"[HATA] Yüklenecek video dosyası bulunamadı: {args.video.resolve()}", file=sys.stderr)
        sys.exit(1)

    file_size_kb = args.video.stat().st_size / 1024
    body = build_video_Metadata(
        title=args.title,
        description=args.description,
        category_id=args.category_id,
        tags=["shorts", "bilim", "ilgincbilgiler", "test"],
    )

    print("=" * 72)
    print(" YOUTUBE DATA API v3 - PRIVATE YÜKLEME TESTİ")
    print("=" * 72)
    print(f" Dosya          : {args.video.resolve()} ({file_size_kb:.1f} KB)")
    print(f" Başlık         : {body['snippet']['title']}")
    print(f" Gizlilik Kilidi: {body['status']['privacyStatus']} (Zorunlu)")
    print(" Tahmini Kota   : ~1.600 / 10.000 günlük birim")
    print("=" * 72)

    if args.dry_run:
        print("\n[DRY-RUN] API çağrısı atlandı. Gönderilecek JSON gövdesi:")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        print("[DRY-RUN BAŞARILI] Medya dosyası ve yükleme paketi üretime hazır.")
        return

    creds = load_credentials(args.token_path)
    youtube = build("youtube", "v3", credentials=creds)

    media = MediaFileUpload(
        str(args.video),
        mimetype="video/mp4",
        chunksize=1024 * 1024,  # 1 MB parça boyutu
        resumable=True,
    )

    insert_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print("\n[BAŞLATILDI] Video YouTube sunucularına yükleniyor...")
    try:
        response = resumable_upload(insert_request)
    except HttpError as exc:
        print(f"\n[API HATASI] Yükleme başarısız oldu (HTTP {exc.resp.status}):\n{exc}", file=sys.stderr)
        sys.exit(1)

    video_id = response.get("id")
    returned_privacy = response.get("status", {}).get("privacyStatus", "bilinmiyor")

    print("\n" + "=" * 72)
    print(" [BAŞARILI] VİDEO YÜKLEME TAMAMLANDI!")
    print("=" * 72)
    print(f" Video ID          : {video_id}")
    print(f" Gizlilik Durumu   : {returned_privacy}")
    print(f" Standart Bağlantı : https://www.youtube.com/watch?v={video_id}")
    print(f" Shorts Bağlantısı : https://www.youtube.com/shorts/{video_id}")
    print(f" Studio Onay Ekranı: https://studio.youtube.com/video/{video_id}/edit")
    print("=" * 72)


if __name__ == "__main__":
    main()
