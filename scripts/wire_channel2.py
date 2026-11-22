#!/usr/bin/env python3
"""
KANAL-2 TEL CEKME: DRAFT oturumunun GERCEK kanal kimligi ana hesaptan
farkli ise COOKIES_JSON_2 / STORAGE_STATE_JSON_2 / ENV_FILE_2 slotlarina
DRAFT cookie'lerini yazar (server-side sealed-box PUT; degerler loglanmaz).

Karar mantigi (fail-closed):
  - ana kimligi cozulemediyse  -> WIRE YOK (exit 2)
  - draft kimligi cozulemediyse -> WIRE YOK (exit 2)
  - ayni UC... ise             -> WIRE YOK, kota korunur (exit 0)
  - farkli UC... ise           -> 3 secret PUT, WIRE_OK (exit 0)

Kullanim:
  python3 scripts/wire_channel2.py \
      --ids-ana  /tmp/identity/ids_ana.json \
      --ids-draft /tmp/identity/ids_draft.json \
      --cookies-draft /tmp/identity/cookies_draft.json \
      --storage-draft /tmp/identity/storage_draft.json \
      --env-file1 /tmp/identity/env_file_1.txt
"""
import argparse
import base64
import json
import os
import sys

import requests

OWNER = "ahmetbysoy"
REPO = "youtube_shorts_automation"


def api_headers():
    pat = os.environ.get("REPO_PAT", "")
    if len(pat) < 20:
        print("REPO_PAT env eksik -> secret yazilamaz")
        sys.exit(2)
    return {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def put_secret(name: str, value: str) -> None:
    from nacl import encoding
    from nacl import public as np

    r = requests.get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/public-key",
        headers=api_headers(), timeout=30)
    r.raise_for_status()
    kd = r.json()
    pk = np.PublicKey(kd["key"].encode(), encoding.Base64Encoder())
    enc = base64.b64encode(np.SealedBox(pk).encrypt(value.encode())).decode()
    r = requests.put(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/{name}",
        headers={**api_headers(), "Content-Type": "application/json"},
        json={"encrypted_value": enc, "key_id": kd["key_id"]}, timeout=30)
    print(f"PUT {name} ({len(value)} char) -> HTTP {r.status_code}")
    if r.status_code not in (201, 204):
        raise RuntimeError(f"Secret PUT basarisiz: {r.text[:200]}")


def read_id(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # noqa: BLE001
        print(f"kimlik dosyasi okunamadi ({path}): {exc}")
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids-ana", required=True)
    ap.add_argument("--ids-draft", required=True)
    ap.add_argument("--cookies-draft", required=True)
    ap.add_argument("--storage-draft", required=True)
    ap.add_argument("--env-file1", required=True)
    args = ap.parse_args()

    ana = read_id(args.ids_ana)
    draft = read_id(args.ids_draft)
    ana_id = ana.get("channel_id", "")
    draft_id = draft.get("channel_id", "")

    print(f"ana   kanal: {ana_id or 'COZULEMEDI'} (yontem: {ana.get('method', '-')})")
    print(f"draft kanal: {draft_id or 'COZULEMEDI'} (yontem: {draft.get('method', '-')})")

    if not ana_id or not draft_id:
        print("WIRE_YOK: kimlik tam cozulemedi -> fail-closed (secret'lara dokunulmadi).")
        return 2

    if ana_id == draft_id:
        print(f"WIRE_YOK: AYNI HESAP ({ana_id}) — DRAFT oturumu ana kanalin baska oturumu.")
        print("  Ikinci kanal icin KULLANICIYENI Google hesabi cookie'si gerekir.")
        return 0

    print(f"WIRE_BASLIYOR: ayri hesaplar (ana={ana_id}, draft={draft_id})")
    for path, name in ((args.cookies_draft, "COOKIES_JSON_2"),
                       (args.storage_draft, "STORAGE_STATE_JSON_2")):
        with open(path, "r", encoding="utf-8") as fh:
            put_secret(name, fh.read())
    if os.path.getsize(args.env_file1) > 50:
        with open(args.env_file1, "r", encoding="utf-8") as fh:
            put_secret("ENV_FILE_2", fh.read())
    else:
        print("ENV_FILE_1 icerigi cok kucuk -> ENV_FILE_2 atlandi")

    print("WIRE_OK: Kanal-2 slotu DRAFT oturumu ile dolduruldu.")
    print("  Dogrulama: daily_shorts.yml dispatch target_channel=2")
    return 0


if __name__ == "__main__":
    sys.exit(main())
