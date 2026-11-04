#!/usr/bin/env python3
"""
Profesyonel YouTube Data API v3 OAuth 2.0 Kimlik Doğrulama ve Servis Çekirdeği
(`src/youtube_upload/oauth_handler.py`)

Mimari İyileştirmeler:
  1. Dizin Bağımsız Loglama: `logs/oauth_handler.log` mutlak yolla (`BASE_DIR / "logs"`)
     ve otomatik klasör oluşturma (`mkdir(parents=True, exist_ok=True)`) ile başlatılır.
  2. Gerçek Sessionless (GitHub Actions) Desteği: Önce `token.json` (veya `YOUTUBE_TOKEN_JSON`
     ortam değişkeni) kontrol edilir ve `refresh_token` ile sessizce yenilenir; `client_secret.json`
     yalnızca sıfırdan yeni OAuth akışı başlatılacağında zorunlu tutulur.
  3. Headless + Desktop Çift Mod: Grafik arayüz (DISPLAY) varsa `run_local_server`,
     bulut/headless sunucuda ise Google'ın kaldırdığı OOB akışı yerine PKCE destekli
     `http://localhost:8080/` Loopback URL kopyalama akışı (`--generate-url` / `--exchange`) çalışır.
  4. Zorunlu Kalıcı Token & Dosya Güvenliği: `access_type="offline"` ve `prompt="consent"` ile
     `refresh_token` garantilenir; `token.json` diske `0600` izniyle kaydedilir.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Proje kökündeki .env dosyasını yükle
load_dotenv(BASE_DIR / ".env")

# Loglama ayarları (hem dosyaya hem konsola)
logger = logging.getLogger("youtube_oauth_handler")
if not logger.handlers:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logger.setLevel(log_level)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(LOG_DIR / "oauth_handler.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


class YouTubeOAuthHandler:
    REDIRECT_URI = "http://localhost:8080/"

    def __init__(
        self,
        client_secret_path: Path | None = None,
        token_path: Path | None = None,
    ) -> None:
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]
        self.base_dir = BASE_DIR
        self.client_secret_path = client_secret_path or (self.base_dir / "client_secret.json")
        self.token_path = token_path or (self.base_dir / "token.json")
        self.pending_state_path = self.base_dir / ".oauth_state.json"
        self.creds: Credentials | None = None
        self.service = None

    def _resolve_client_secret(self) -> bool:
        """`client_secret.json` dosyasını veya indirilen `client_secret_*.json` dosyasını doğrular."""
        if self.client_secret_path.exists():
            return True

        secrets_alt = self.base_dir / "secrets" / "client_secret.json"
        if secrets_alt.exists():
            self.client_secret_path = secrets_alt
            return True

        candidates = sorted(glob.glob(str(self.base_dir / "client_secret_*.json")))
        if candidates:
            src = Path(candidates[0])
            shutil.copy2(src, self.client_secret_path)
            os.chmod(self.client_secret_path, 0o600)
            logger.info(f"'{src.name}' bulundu ve '{self.client_secret_path.name}' olarak kopyalandı.")
            return True

        logger.error(f"CRITICAL: client_secret.json bulunamadı! Yol: {self.client_secret_path}")
        return False

    def _save_token(self) -> None:
        """Token bilgisini `0600` dosya izinleriyle diske yazar."""
        if not self.creds:
            return
        with open(self.token_path, "w", encoding="utf-8") as token_file:
            token_file.write(self.creds.to_json())
        os.chmod(self.token_path, 0o600)
        logger.info(f"OAuth token başarıyla kaydedildi: {self.token_path}")

    @staticmethod
    def _extract_code(raw_input: str) -> str:
        cleaned = raw_input.strip()
        if not cleaned:
            raise ValueError("Boş yetki kodu/URL girildi.")
        if cleaned.startswith(("http://", "https://", "localhost:")):
            if cleaned.startswith("localhost:"):
                cleaned = f"http://{cleaned}"
            parsed = urlparse(cleaned)
            params = parse_qs(parsed.query)
            if "error" in params:
                raise RuntimeError(f"Google OAuth hatası döndürdü: {params['error'][0]}")
            if "code" not in params or not params["code"][0]:
                raise ValueError("URL içinde 'code=' parametresi bulunamadı.")
            return params["code"][0]
        return cleaned

    def generate_headless_auth_url(self) -> str:
        """Headless ortamlar için PKCE destekli onay URL'si üretir ve durumu saklar."""
        if not self._resolve_client_secret():
            raise FileNotFoundError(f"client_secret.json bulunamadı: {self.client_secret_path}")

        flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.scopes)
        flow.redirect_uri = self.REDIRECT_URI
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        state_payload = {
            "state": state,
            "code_verifier": flow.code_verifier,
            "redirect_uri": self.REDIRECT_URI,
            "client_secret_path": str(self.client_secret_path),
        }
        self.pending_state_path.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")
        os.chmod(self.pending_state_path, 0o600)
        logger.info("Headless OAuth 2.0 yetkilendirme URL'si ve PKCE durumu oluşturuldu.")
        return auth_url

    def exchange_headless_code(self, url_or_code: str) -> bool:
        """Tarayıcı adres çubuğundan kopyalanan `http://localhost:8080/?code=...` yanıtını takas eder."""
        try:
            code = self._extract_code(url_or_code)
            state_data = {}
            if self.pending_state_path.exists():
                state_data = json.loads(self.pending_state_path.read_text(encoding="utf-8"))

            secret_path = Path(state_data.get("client_secret_path", str(self.client_secret_path)))
            self.client_secret_path = secret_path
            if not self._resolve_client_secret():
                return False

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.client_secret_path),
                self.scopes,
                state=state_data.get("state"),
            )
            flow.redirect_uri = state_data.get("redirect_uri", self.REDIRECT_URI)
            if state_data.get("code_verifier"):
                flow.code_verifier = state_data["code_verifier"]

            flow.fetch_token(code=code)
            self.creds = flow.credentials
            self._save_token()
            if self.pending_state_path.exists():
                self.pending_state_path.unlink()

            self.service = build("youtube", "v3", credentials=self.creds)
            logger.info("YouTube Data API v3 servisi (headless exchange) başarıyla başlatıldı.")
            return True
        except Exception as exc:
            logger.error(f"Headless kod takası hatası: {exc}")
            return False

    def authenticate(self, force_headless: bool = False) -> bool:
        """
        OAuth 2.0 kimlik doğrulamasını yapar.
        Varsa `token.json` (veya CI/CD için `YOUTUBE_TOKEN_JSON`) kullanır;
        yoksa masaüstü veya headless akışla yeni yetki ister.
        """
        try:
            # 1. Önce mevcut token.json veya ortam değişkenini kontrol et (Sessionless çalışma)
            env_token = os.getenv("YOUTUBE_TOKEN_JSON", "").strip()
            if env_token:
                logger.info("YOUTUBE_TOKEN_JSON ortam değişkeninden kimlik bilgisi yükleniyor...")
                self.creds = Credentials.from_authorized_user_info(json.loads(env_token), self.scopes)
            elif self.token_path.exists():
                logger.info(f"Mevcut token.json okunuyor: {self.token_path}")
                self.creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

            # 2. Geçerli kimlik bilgisi yoksa yenile veya yeni OAuth akışı başlat
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("Token süresi dolmuş, refresh_token ile sessizce yenileniyor...")
                    self.creds.refresh(Request())
                    if not env_token:
                        self._save_token()
                else:
                    if not self._resolve_client_secret():
                        return False

                    has_display = bool(os.environ.get("DISPLAY") or sys.platform in ("win32", "darwin"))
                    if has_display and not force_headless:
                        logger.info("Yeni OAuth akışı başlatılıyor. Lütfen tarayıcıda yetki verin.")
                        flow = InstalledAppFlow.from_client_secrets_file(
                            str(self.client_secret_path), self.scopes
                        )
                        self.creds = flow.run_local_server(
                            port=0,
                            open_browser=True,
                            access_type="offline",
                            prompt="consent",
                        )
                        self._save_token()
                    else:
                        auth_url = self.generate_headless_auth_url()
                        logger.info(
                            "Headless ortam algılandı. Aşağıdaki URL'yi tarayıcıda açıp onaylayın:\n"
                            f"{auth_url}"
                        )
                        if sys.stdin.isatty():
                            raw = input("\nYönlendirilen http://localhost:8080/?code=... adresini yapıştırın: ")
                            return self.exchange_headless_code(raw)
                        logger.warning(
                            "Etkileşimsiz (non-TTY) terminal: Onay sonrası URL'yi şu komutla tamamlayın:\n"
                            'python src/youtube_upload/oauth_handler.py --exchange "http://localhost:8080/?code=..."'
                        )
                        return False

            # 3. YouTube API servisini başlat
            self.service = build("youtube", "v3", credentials=self.creds)
            logger.info("YouTube Data API v3 servisi başarıyla başlatıldı.")
            return True

        except HttpError as exc:
            logger.error(f"Google API HTTP Hatası: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Beklenmeyen OAuth Hatası: {exc}")
            return False

    def get_service(self):
        """Yetkilendirilmiş YouTube API servisini döndürür."""
        if not self.service:
            logger.error("Servis başlatılmadı! Önce authenticate() çağrılmalı.")
            raise RuntimeError("YouTube servisi mevcut değil.")
        return self.service


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube Data API v3 OAuth 2.0 Handler")
    parser.add_argument("--generate-url", action="store_true", help="Headless onay URL'si üretir")
    parser.add_argument("--exchange", type=str, metavar="URL_OR_CODE", help="Yönlendirme URL'sini token.json'a çevirir")
    parser.add_argument("--headless", action="store_true", help="Headless akışı zorlar")
    args = parser.parse_args()

    handler = YouTubeOAuthHandler()

    if args.generate_url:
        try:
            url = handler.generate_headless_auth_url()
            print(f"\n[+] ONAY URL'Sİ:\n{url}\n")
            return 0
        except Exception as exc:
            print(f"\n[-] HATA: {exc}")
            return 1

    authenticated = (
        handler.exchange_headless_code(args.exchange)
        if args.exchange
        else handler.authenticate(force_headless=args.headless)
    )

    if authenticated:
        print("\n[+] BAŞARILI: OAuth kimlik doğrulaması tamamlandı. token.json oluşturuldu.")
        try:
            service = handler.get_service()
            request = service.channels().list(part="snippet,contentDetails,statistics", mine=True)
            response = request.execute()
            items = response.get("items", [])
            if items:
                print(f"[+] Kanal Adı: {items[0]['snippet']['title']}")
                print(f"[+] Abone Sayısı: {items[0]['statistics'].get('subscriberCount', 'Gizli/0')}")
            else:
                print("[-] Bu Google hesabına bağlı aktif bir YouTube kanalı bulunamadı.")
        except Exception as exc:
            print(f"[-] Kanal bilgisi çekilemedi: {exc}")
        return 0

    print("\n[-] HATA: OAuth kimlik doğrulaması başarısız oldu. Logları kontrol et.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
