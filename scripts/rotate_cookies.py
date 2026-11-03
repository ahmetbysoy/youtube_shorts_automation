#!/usr/bin/env python3
"""
14 Günlük Cookie & Oturum Rotasyon Aracı (Son Protokol - Faz 7/8)
Yerelde yenilenen `.env`, `cookies.json` ve `storage_state.json` dosyalarını
Libsodium (PyNaCl SealedBox) ile şifreleyerek GitHub Repository Secrets üzerindeki
`ENV_FILE_1..10`, `COOKIES_JSON_1..10` ve `STORAGE_STATE_JSON_1..10` alanlarına yazar.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests
from nacl import encoding, public


DEFAULT_REPO = "ahmetbysoy/youtube_shorts_automation"


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    pub_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(pub_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def parse_channels(spec: str) -> list[str]:
    spec = spec.strip()
    if "-" in spec:
        start_s, end_s = spec.split("-", 1)
        return [str(i) for i in range(int(start_s), int(end_s) + 1)]
    return [item.strip() for item in spec.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub Secrets Cookie & StorageState Rotasyon Aracı")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPO", DEFAULT_REPO), help="owner/repo")
    parser.add_argument("--channels", default="1-10", help="Kanal aralığı veya listesi (örn: 1-10 veya 4,5,6)")
    parser.add_argument("--env-file", default=".env", help=".env dosya yolu")
    parser.add_argument("--cookies-file", default="cookies.json", help="cookies.json dosya yolu")
    parser.add_argument("--state-file", default="storage_state.json", help="storage_state.json dosya yolu")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[-] HATA: GITHUB_TOKEN ortam değişkeni tanımlı değil!", file=sys.stderr)
        return 1

    env_path = Path(args.env_file)
    cookies_path = Path(args.cookies_file)
    state_path = Path(args.state_file)

    if not env_path.exists() or not cookies_path.exists():
        print("[-] HATA: .env veya cookies.json bulunamadı!", file=sys.stderr)
        return 1

    cookies_raw = cookies_path.read_text(encoding="utf-8").strip()
    parsed_cookies = json.loads(cookies_raw)
    if not isinstance(parsed_cookies, list) or not parsed_cookies:
        print("[-] HATA: cookies.json boş veya geçersiz JSON listesi!", file=sys.stderr)
        return 1

    env_lines = [
        ln for ln in env_path.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("MATRIX_CHANNEL_ID=")
    ]
    clean_env = "\n".join(env_lines).strip()
    state_raw = state_path.read_text(encoding="utf-8").strip() if state_path.exists() else ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    pk_resp = requests.get(
        f"https://api.github.com/repos/{args.repo}/actions/secrets/public-key",
        headers=headers,
        timeout=20,
    )
    pk_resp.raise_for_status()
    pk_data = pk_resp.json()

    channels = parse_channels(args.channels)
    for cid in channels:
        payloads = {
            f"ENV_FILE_{cid}": f"{clean_env}\nMATRIX_CHANNEL_ID={cid}\n",
            f"COOKIES_JSON_{cid}": cookies_raw,
        }
        if state_raw:
            payloads[f"STORAGE_STATE_JSON_{cid}"] = state_raw

        for secret_name, secret_val in payloads.items():
            enc_val = encrypt_secret(pk_data["key"], secret_val)
            resp = requests.put(
                f"https://api.github.com/repos/{args.repo}/actions/secrets/{secret_name}",
                headers=headers,
                json={"encrypted_value": enc_val, "key_id": pk_data["key_id"]},
                timeout=25,
            )
            resp.raise_for_status()
            print(f"[+] {secret_name} güncellendi (HTTP {resp.status_code})")

    print(f"[OK] Toplam {len(channels)} kanal için oturum rotasyonu tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
