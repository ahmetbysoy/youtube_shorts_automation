#!/usr/bin/env python3
"""
Faz 1 - Görev 1 (Adım 3): YouTube Data API v3 Headless OAuth2 Yetkilendirme Betiği
---------------------------------------------------------------------------------
Google, `google-auth-oauthlib >= 1.0` sürümüyle birlikte eski OOB tabanlı
`InstalledAppFlow.run_console()` metodunu güvenlik gerekçesiyle tamamen kaldırdı.

Bu betik, bulut/sunucu (headless) ortamlarında SSH tüneline ihtiyaç duymadan
çalışabilen güncel "Loopback URL Kopyalama + PKCE (code_verifier)" akışını uygular:
  1. Desktop App istemcisi için otomatik izinli `http://localhost:8080/` yönlendirmesiyle
     yetkilendirme URL'si üretir (`access_type="offline"`, `prompt="consent"`).
  2. Kullanıcı kendi tarayıcısında URL'yi açıp onay verir.
  3. Tarayıcı `http://localhost:8080/?state=...&code=...` adresine yönlenir
     ("Bu siteye ulaşılamıyor" uyarısı normaldir; önemli olan adres çubuğundaki URL'dir).
  4. Adres çubuğundaki tam URL (veya sadece `code` parametresi) betiğe verilir;
     kalıcı `refresh_token` içeren `token.json` diske kaydedilir.

Kullanım Modları:
  - İnteraktif Konsol : python youtube_auth.py
  - İki Adımlı Bulut  : python youtube_auth.py --generate-url
                        python youtube_auth.py --exchange "http://localhost:8080/?code=..."
  - Masaüstü Tarayıcı : python youtube_auth.py --local-server
  - Mevcut Token Test : python youtube_auth.py --verify
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# YouTube video yükleme + bağlı kanalı doğrulama (salt-okunur) yetkileri
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

DEFAULT_CLIENT_SECRET = Path("client_secret.json")
DEFAULT_TOKEN_PATH = Path("token.json")
PENDING_STATE_PATH = Path(".oauth_state.json")
REDIRECT_URI = "http://localhost:8080/"


def resolve_client_secret(path: Path) -> Path:
    """`client_secret.json` dosyasını bulur; Google'ın uzun isimli indirmesini otomatik tanır."""
    if path.exists():
        return path

    candidates = sorted(glob.glob("client_secret_*.json"))
    if candidates:
        source = Path(candidates[0])
        shutil.copy2(source, path)
        os.chmod(path, 0o600)
        print(f"[BİLGİ] '{source.name}' bulundu ve '{path.name}' olarak kopyalandı.")
        return path

    print(
        f"\n[HATA] '{path}' dosyası proje dizininde bulunamadı!\n"
        "Lütfen Google Cloud Console -> APIs & Services -> Credentials menüsünden\n"
        "'Desktop app' (Masaüstü uygulaması) türünde OAuth İstemci Kimliği oluşturup\n"
        f"indirdiğiniz JSON dosyasını '{path}' adıyla bu klasöre yükleyin.\n",
        file=sys.stderr,
    )
    sys.exit(1)


def extract_auth_code(raw_input: str) -> str:
    """Kullanıcının yapıştırdığı tam yönlendirme URL'sinden veya ham metinden `code` değerini ayıklar."""
    cleaned = raw_input.strip()
    if not cleaned:
        raise ValueError("Boş giriş yapıldı. Lütfen yönlendirilen URL'yi veya yetki kodunu girin.")

    if cleaned.startswith(("http://", "https://", "localhost:")):
        if cleaned.startswith("localhost:"):
            cleaned = f"http://{cleaned}"
        parsed = urlparse(cleaned)
        params = parse_qs(parsed.query)

        if "error" in params:
            err = params["error"][0]
            raise RuntimeError(
                f"Google OAuth yetkilendirme hatası döndürdü: '{err}'. "
                "OAuth Consent Screen -> Test Users listesine kendi Gmail adresinizi eklediğinizden emin olun."
            )

        if "code" not in params or not params["code"][0]:
            raise ValueError(
                "Yapıştırılan URL içinde 'code=' parametresi bulunamadı. "
                "Lütfen adres çubuğundaki tam URL'yi kopyaladığınızdan emin olun."
            )
        return params["code"][0]

    return cleaned


def save_credentials(creds: Credentials, token_path: Path) -> None:
    """Kimlik bilgilerini güvenli dosya izinleriyle (`0600`) kaydeder ve `refresh_token` varlığını denetler."""
    if not creds.refresh_token:
        print(
            "\n[UYARI] Dönen yanıtta 'refresh_token' bulunamadı! "
            "Google hesabınızdan https://myaccount.google.com/permissions adresine gidip "
            "uygulama iznini kaldırarak tekrar deneyin.",
            file=sys.stderr,
        )

    token_path.write_text(creds.to_json(), encoding="utf-8")
    os.chmod(token_path, 0o600)
    print(f"\n[BAŞARILI] Yetkilendirme tamamlandı! Token kaydedildi -> {token_path.resolve()}")
    print(f"[KONTROL] Kalıcı refresh_token mevcut mu? {'EVET' if bool(creds.refresh_token) else 'HAYIR'}")


def verify_connected_channel(creds: Credentials) -> None:
    """Alınan token ile bağlı YouTube kanalını doğrular (Maliyet: 1 kota birimi)."""
    try:
        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(part="snippet", mine=True).execute()
        items = response.get("items", [])
        if not items:
            print(
                "\n[UYARI] Google hesabı doğrulandı ancak bu hesaba bağlı aktif bir YouTube kanalı bulunamadı!\n"
                "Video yüklemeden önce https://www.youtube.com adresine gidip 'Kanal Oluştur' adımını tamamlayın."
            )
            return

        channel = items[0]
        title = channel["snippet"].get("title", "Bilinmiyor")
        channel_id = channel.get("id", "Bilinmiyor")
        custom_url = channel["snippet"].get("customUrl", "")
        handle_info = f" ({custom_url})" if custom_url else ""
        print(f"[KANAL DOĞRULANDI] Bağlı Kanal: {title}{handle_info} | Kanal ID: {channel_id}")
    except HttpError as exc:
        if "youtubeSignupRequired" in str(exc):
            print(
                "\n[UYARI] Bu Google hesabında henüz YouTube kanalı açılmamış (`youtubeSignupRequired`).\n"
                "Lütfen https://www.youtube.com üzerinden 1 tıklamayla kanalınızı oluşturun."
            )
        else:
            print(f"[BİLGİ] Kanal bilgisi sorgulanamadı (yükleme yetkisi yine de geçerli olabilir): {exc}")


def generate_headless_url(client_secret_path: Path, save_state: bool = True) -> tuple[InstalledAppFlow, str]:
    """PKCE destekli OAuth2 yetkilendirme URL'sini oluşturur."""
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes=SCOPES)
    flow.redirect_uri = REDIRECT_URI

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    if save_state:
        state_payload = {
            "state": state,
            "code_verifier": flow.code_verifier,
            "redirect_uri": REDIRECT_URI,
            "client_secret_path": str(client_secret_path),
        }
        PENDING_STATE_PATH.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")
        os.chmod(PENDING_STATE_PATH, 0o600)

    return flow, auth_url


def print_headless_instructions(auth_url: str, two_step_hint: bool = False) -> None:
    print("\n" + "=" * 78)
    print(" YOUTUBE DATA API v3 - HEADLESS OAUTH2 YETKİLENDİRME ADIMLARI")
    print("=" * 78)
    print("\n1) Aşağıdaki URL'yi kendi tarayıcınızda açın ve Google hesabınızla onay verin:\n")
    print(f"   {auth_url}\n")
    print("2) Onay sonrası tarayıcınız `http://localhost:8080/?state=...&code=...` adresine")
    print("   yönlenecektir. Sayfada 'Bu siteye ulaşılamıyor / ERR_CONNECTION_REFUSED'")
    print("   yazması TAMAMEN NORMALDİR.")
    print("3) Tarayıcınızın adres çubuğundaki o URL'nin TAMAMINI kopyalayın.")
    if two_step_hint:
        print("\n4) Kopyaladığınız URL'yi aşağıdaki komutla çalıştırın (veya sohbete yapıştırın):")
        print('   python youtube_auth.py --exchange "YAPIŞTIRILAN_TAM_URL"')
    print("=" * 78 + "\n")


def exchange_with_saved_state(raw_url_or_code: str, client_secret_path: Path, token_path: Path) -> None:
    """Kaydedilmiş PKCE durumu ile yetki kodunu kalıcı `token.json` dosyasına dönüştürür."""
    code = extract_auth_code(raw_url_or_code)

    state_data = {}
    if PENDING_STATE_PATH.exists():
        state_data = json.loads(PENDING_STATE_PATH.read_text(encoding="utf-8"))

    secret_file = Path(state_data.get("client_secret_path", str(client_secret_path)))
    secret_file = resolve_client_secret(secret_file)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(secret_file),
        scopes=SCOPES,
        state=state_data.get("state"),
    )
    flow.redirect_uri = state_data.get("redirect_uri", REDIRECT_URI)
    if state_data.get("code_verifier"):
        flow.code_verifier = state_data["code_verifier"]

    flow.fetch_token(code=code)
    creds = flow.credentials
    save_credentials(creds, token_path)

    if PENDING_STATE_PATH.exists():
        PENDING_STATE_PATH.unlink()

    verify_connected_channel(creds)


def verify_existing_token(token_path: Path) -> None:
    """Mevcut `token.json` dosyasını okur, süresi dolmuşsa yeniler ve kanalı doğrular."""
    if not token_path.exists():
        print(f"[HATA] '{token_path}' bulunamadı. Önce yetkilendirme işlemini tamamlayın.", file=sys.stderr)
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        print("[BİLGİ] Access token süresi dolmuş, refresh_token ile otomatik yenileniyor...")
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(token_path, 0o600)
        print("[BAŞARILI] Access token başarıyla yenilendi.")

    print(f"[DURUM] Token geçerli mi? {'EVET' if creds.valid else 'HAYIR'}")
    print(f"[DURUM] Kalıcı refresh_token mevcut mu? {'EVET' if bool(creds.refresh_token) else 'HAYIR'}")
    verify_connected_channel(creds)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Data API v3 Headless OAuth2 Yetkilendirme Aracı")
    parser.add_argument(
        "--client-secret",
        type=Path,
        default=DEFAULT_CLIENT_SECRET,
        help="OAuth2 istemci kimlik dosyası (varsayılan: client_secret.json)",
    )
    parser.add_argument(
        "--token-path",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help="Üretilecek token dosyası (varsayılan: token.json)",
    )
    parser.add_argument(
        "--generate-url",
        action="store_true",
        help="Headless ortam için yetkilendirme URL'sini üretir ve PKCE durumunu kaydeder.",
    )
    parser.add_argument(
        "--exchange",
        type=str,
        metavar="URL_VEYA_KOD",
        help="Tarayıcıdan kopyalanan yönlendirme URL'sini veya yetki kodunu token.json'a dönüştürür.",
    )
    parser.add_argument(
        "--local-server",
        action="store_true",
        help="Masaüstü ortamda yerel HTTP sunucusu üzerinden otomatik tarayıcı doğrulaması başlatır.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Mevcut token.json dosyasını ve bağlı YouTube kanalını test eder.",
    )
    args = parser.parse_args()

    if args.verify:
        verify_existing_token(args.token_path)
        return

    if args.exchange:
        exchange_with_saved_state(args.exchange, args.client_secret, args.token_path)
        return

    client_secret_path = resolve_client_secret(args.client_secret)

    if args.local_server:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes=SCOPES)
        creds = flow.run_local_server(port=8080, access_type="offline", prompt="consent")
        save_credentials(creds, args.token_path)
        verify_connected_channel(creds)
        return

    # İki adımlı bulut modu veya etkileşimsiz (non-TTY) terminal algılaması
    if args.generate_url or not sys.stdin.isatty():
        _, auth_url = generate_headless_url(client_secret_path, save_state=True)
        print_headless_instructions(auth_url, two_step_hint=True)
        return

    # İnteraktif konsol modu (tek adımda URL üret -> kullanıcıdan URL/kod al -> kaydet)
    flow, auth_url = generate_headless_url(client_secret_path, save_state=True)
    print_headless_instructions(auth_url, two_step_hint=False)
    user_input = input("Yönlendirilen tam URL'yi (veya 'code' değerini) buraya yapıştırın: ")
    code = extract_auth_code(user_input)
    flow.fetch_token(code=code)
    creds = flow.credentials
    save_credentials(creds, args.token_path)
    if PENDING_STATE_PATH.exists():
        PENDING_STATE_PATH.unlink()
    verify_connected_channel(creds)


if __name__ == "__main__":
    main()
