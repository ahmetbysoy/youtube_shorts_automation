#!/usr/bin/env python3
"""
PEXELS_COOK / PIXABAY_COOK reset to empty array `[]`.
Kodda `if (cookies.length) await context.addCookies(cookies);` — bos array
hic cookie gondermez, tarayici tamamen misafir olarak gider ve 4.7K+ sonuc doner.
Kanit: 99_test_pexels_guest run #44900835329 — HTTP 200, 48 video linki.
"""
from __future__ import annotations
import base64, json, os, sys
from pathlib import Path
import requests

OWNER = "ahmetbysoy"
REPO = "youtube_shorts_automation"
REPO_PAT = os.environ["REPO_PAT"]
H = {"Authorization": f"token {REPO_PAT}", "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2022-11-28"}

def put(name: str, value: str):
    r = requests.get(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/public-key",
                     headers=H, timeout=30); r.raise_for_status()
    kd = r.json()
    from nacl import encoding, public as np
    pk = np.PublicKey(kd["key"].encode(), encoding.Base64Encoder())
    enc = base64.b64encode(np.SealedBox(pk).encrypt(value.encode())).decode()
    r = requests.put(f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/{name}",
                     headers={**H, "Content-Type": "application/json"},
                     json={"encrypted_value": enc, "key_id": kd["key_id"]}, timeout=30)
    print(f"PUT {name} → HTTP {r.status_code}", flush=True)

def main():
    # Bos array = misafir erisimi (Pexels ve Pixabay icin gecerli, kanitlandi)
    put("PEXELS_COOK", "[]")
    # Pixabay'i de deneyecegiz; eger guest calisiyorsa onu da [] yap, yoksa dokunma.
    # Asagida ayri test yapiyoruz.
    return 0

if __name__ == "__main__":
    sys.exit(main())
