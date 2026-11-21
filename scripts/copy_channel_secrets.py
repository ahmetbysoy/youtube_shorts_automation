#!/usr/bin/env python3
"""
_1 suffix'li channel secret'larini yoksa, ana secret'tan (suffix'siz) kopyalayarak olusturur.
Channel 1 pipeline'in bekledigi secret'lar:
  COOKIES_JSON_1   <- COOKIES_JSON
  STORAGE_STATE_JSON_1 <- STORAGE_STATE_JSON
  ENV_FILE_1       <- ENV_FILE
  (YT_EMAIL, YT_PASSWORD, GEMINI_COOK, PEXELS_COOK, PIXABAY_COOK, HF_TOKEN
   channel-spesifik degil, ortak)
"""
import base64, json, os, sys
from pathlib import Path
import requests

OWNER = "ahmetbysoy"; REPO = "youtube_shorts_automation"
GH = os.environ["REPO_PAT"]
H = {"Authorization": f"token {GH}", "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28"}

def list_secrets():
    r = requests.get(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets?per_page=100",
                     headers=H, timeout=30); r.raise_for_status()
    return {s["name"] for s in r.json()["secrets"]}

def get_pubkey():
    r = requests.get(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/public-key",
                     headers=H, timeout=30); r.raise_for_status()
    return r.json()

def put_secret(name, value):
    from nacl import encoding, public as np
    kd = get_pubkey()
    pk = np.PublicKey(kd["key"].encode(), encoding.Base64Encoder())
    enc = base64.b64encode(np.SealedBox(pk).encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/{name}",
                     headers={**H, "Content-Type": "application/json"},
                     json={"encrypted_value": enc, "key_id": kd["key_id"]}, timeout=30)
    print(f"PUT {name}({len(value)} chars) → HTTP {r.status_code}")
    if r.status_code not in (201, 204):
        raise RuntimeError(f"Secret PUT failed: {r.text[:300]}")

# Ana secret'lari env'den al (workflow bunlari enjekte etmis olacak)
mappings = [
    ("COOKIES_JSON_1", "COOKIES_JSON"),
    ("STORAGE_STATE_JSON_1", "STORAGE_STATE_JSON"),
    ("ENV_FILE_1", "ENV_FILE"),
]

existing = list_secrets()
print(f"Mevcut secret sayisi: {len(existing)}")

copied = 0
for target, source in mappings:
    source_val = os.environ.get(source, "")
    if target in existing:
        print(f"[zaten var] {target}")
        continue
    if not source_val:
        print(f"[ATLA] {target} icin kaynak {source} bos")
        continue
    put_secret(target, source_val)
    copied += 1

print(f"\nSONUC: {copied} yeni secret olusturuldu.")
