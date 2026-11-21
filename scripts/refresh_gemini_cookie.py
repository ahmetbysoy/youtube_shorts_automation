#!/usr/bin/env python3
"""
GEMINI_COOK refresh: calisan YouTube STORAGE_STATE_JSON ile oturum acik Google hesabindan
__Secure-1PSID / __Secure-1PSIDTS cookie'lerini alir, GeminiClient.init() ile dogrular,
ve GitHub secret'ina yazar.

Calisma sekli:
  1) STORAGE_STATE_JSON'daki .google.com cookie'lerinden PSID/PSIDTS'i cek
  2) Async olarak GeminiClient(cookie).init() ile test et — BASARILIYSA dogrudan adim 5'e atla
  3) Basarisiz olursa Playwright ile mevcut storage_state ile gemini.google.com'a git,
     SSO ile oturum ac, cookie'leri tazele
  4) Taze cookie'lerle tekrar init() testi yap
  5) REPO_PAT ile GitHub Secrets API uzerinden GEMINI_COOK'u guncelle
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests

# --- Konfiguration ---
OWNER = "ahmetbysoy"
REPO = "youtube_shorts_automation"
REPO_PAT = os.environ.get("REPO_PAT", "")
YT_STORAGE_RAW = os.environ.get("STORAGE_STATE_JSON") or os.environ.get("STORAGE_STATE_JSON_1", "")
GEMINI_COOK_CURRENT = os.environ.get("GEMINI_COOK", "")

GH_HEADERS = {
    "Authorization": f"token {REPO_PAT}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def extract_psid_cookies(storage_state_json: str) -> dict[str, str]:
    """Playwright storage_state JSON'indan .google.com PSID/PSIDTS cookie'lerini cikar."""
    try:
        state = json.loads(storage_state_json)
    except json.JSONDecodeError:
        return {}
    cookies = state.get("cookies", []) if isinstance(state, dict) else []
    out: dict[str, str] = {}
    target_names = {"__Secure-1PSID", "__Secure-1PSIDTS"}
    for c in cookies:
        if c.get("name") in target_names:
            domain = c.get("domain", "")
            # .google.com (root) veya accounts.google.com — ikisi de gec erisimli olur
            if "google.com" in domain:
                out[c["name"]] = c.get("value", "")
    return out


async def test_gemini_cookies(psid: str, psidts: str) -> tuple[bool, str]:
    """Verilen PSID/PSIDTS ile GeminiClient.init() dener. (bool, msg) doner."""
    if not psid or len(psid) < 20:
        return False, f"PSID bos veya cok kisa ({len(psid)})"
    try:
        from gemini_webapi import GeminiClient
        client = GeminiClient(psid, psidts)
        await asyncio.wait_for(client.init(timeout=20, auto_refresh=False), timeout=25)
        try:
            await asyncio.wait_for(client.close(), timeout=5)
        except Exception:
            pass
        return True, "GeminiClient.init() BASARILI"
    except asyncio.TimeoutError:
        return False, "GeminiClient.init() TIMEOUT (25s)"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def refresh_via_playwright(storage_state_path: str) -> dict[str, str]:
    """Playwright ile mevcut storage_state ile gemini.google.com'a girer, SSO akisini tetikler,
    taze cookie'leri toplar."""
    from playwright.sync_api import sync_playwright

    out: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=storage_state_path,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="tr-TR",
        )
        page = ctx.new_page()
        try:
            print("[pw] gemini.google.com'a gidiliyor...", flush=True)
            page.goto("https://gemini.google.com/", wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            # "Sign in" / "Oturum aç" butonu var mi?
            for sel, label in [
                ("text=Sign in", "Sign in"),
                ("text=Oturum aç", "Oturum aç"),
                ("a:has-text('Sign in')", "Sign in link"),
                ("button:has-text('Sign in')", "Sign in button"),
                ("[data-test-id='sign-in-button']", "Sign in test-id"),
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        print(f"[pw] {label} butonu bulundu, tiklaniyor...", flush=True)
                        btn.click(timeout=5000)
                        page.wait_for_timeout(6000)
                        break
                except Exception:
                    continue

            # Wait for Gemini chat UI — birkaç olasi gosterge
            loaded = False
            for indicator in [
                "rich-textarea",                  # Gemini textarea class
                "[data-placeholder*='message']",
                "textarea",
                "[role='textbox']",
                "g-snackbar + div",
                "button[aria-label*='Send']",
                "button:has-text('Send')",
                ".text-input-field-textarea",
                ".input-area",
            ]:
                try:
                    page.wait_for_selector(indicator, timeout=10000)
                    print(f"[pw] Gemini UI yuklendi (indicator: {indicator})", flush=True)
                    loaded = True
                    break
                except Exception:
                    continue

            if not loaded:
                # Son care: URL'de "app" veya "chat" var mi
                cur = page.url
                if "gemini.google.com" in cur:
                    print(f"[pw] UI indicator secici bulunamadi ama sayfa {cur} acik", flush=True)
                else:
                    print(f"[pw] UYARI: beklenen sayfa acilmadi — su an: {cur}", flush=True)

            page.screenshot(path="/tmp/gemini_after_load.png")
            page.wait_for_timeout(3000)

            # Cookie'leri topla (.google.com ve gemini.google.com)
            cookies = ctx.cookies()
            target_names = {"__Secure-1PSID", "__Secure-1PSIDTS"}
            for c in cookies:
                if c["name"] in target_names and "google.com" in c["domain"]:
                    out[c["name"]] = c["value"]
                    print(f"[pw] Cookie alindi: {c['name'][:20]}... domain={c['domain']} len={len(c['value'])}",
                          flush=True)
        finally:
            ctx.close()
            browser.close()
    return out


def encrypt_secret(public_key: str, value: str) -> str:
    """Sodium sealed box ile secret'i GitHub public key ile sifrele."""
    from nacl import encoding, public as nacl_public
    pkey = nacl_public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed = nacl_public.SealedBox(pkey).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def put_secret(name: str, value: str) -> None:
    """GitHub Actions secret'ini guncelle."""
    # public key al
    r = requests.get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/public-key",
        headers=GH_HEADERS, timeout=30,
    )
    r.raise_for_status()
    key_data = r.json()
    enc = encrypt_secret(key_data["key"], value)
    r = requests.put(
        f"https://api.github.com/repos/{OWNER}/{REPO}/actions/secrets/{name}",
        headers={**GH_HEADERS, "Content-Type": "application/json"},
        json={"encrypted_value": enc, "key_id": key_data["key_id"]},
        timeout=30,
    )
    if r.status_code not in (201, 204):
        raise RuntimeError(f"Secret write failed HTTP {r.status_code}: {r.text[:300]}")
    print(f"[gh] Secret {name} PUT → HTTP {r.status_code}", flush=True)


async def main() -> int:
    if not REPO_PAT:
        print("HATA: REPO_PAT yok", file=sys.stderr); return 1
    if not YT_STORAGE_RAW:
        print("HATA: STORAGE_STATE_JSON yok", file=sys.stderr); return 1

    print(f"[1] YT storage_state boyut={len(YT_STORAGE_RAW)} byte", flush=True)
    cookies = extract_psid_cookies(YT_STORAGE_RAW)
    print(f"[2] Storage state'den PSID/PSIDTS cikarildi: PSID={len(cookies.get('__Secure-1PSID',''))} char, "
          f"PSIDTS={len(cookies.get('__Secure-1PSIDTS',''))} char", flush=True)

    psid = cookies.get("__Secure-1PSID", "")
    psidts = cookies.get("__Secure-1PSIDTS", "")

    # 1. Deneme: direkt YT cookie'leri ile init
    print("[3] Deneme 1: YT storage_state cookie'leri ile GeminiClient.init() ...", flush=True)
    ok, msg = await test_gemini_cookies(psid, psidts)
    print(f"    sonuc: {ok} — {msg}", flush=True)

    if not ok:
        print("[4] Deneme 2: Playwright ile gemini.google.com'a girip cookie tazeleme ...", flush=True)
        # storage_state'i gecici dosyaya yaz
        ss_path = "/tmp/yt_storage_state.json"
        Path(ss_path).write_text(YT_STORAGE_RAW, encoding="utf-8")
        fresh = refresh_via_playwright(ss_path)
        psid = fresh.get("__Secure-1PSID", psid)
        psidts = fresh.get("__Secure-1PSIDTS", psidts)
        print(f"[4b] Taze PSID={len(psid)} char, PSIDTS={len(psidts)} char", flush=True)

        print("[5] Deneme 3: taze cookie'lerle init() ...", flush=True)
        ok, msg = await test_gemini_cookies(psid, psidts)
        print(f"    sonuc: {ok} — {msg}", flush=True)

    if not ok:
        print(f"\nSONUC: BASARISIZ — Gemini baglantisi kurulamadi. ({msg})", file=sys.stderr)
        return 1

    # GEMINI_COOK formatında JSON obje olustur ve yaz
    payload = json.dumps({"__Secure-1PSID": psid, "__Secure-1PSIDTS": psidts})
    print(f"\n[6] GEMINI_COOK secret guncelleniyor ({len(payload)} byte JSON) ...", flush=True)
    put_secret("GEMINI_COOK", payload)
    print("\nSONUC: BASAIRI — GEMINI_COOK yenilendi ve dogrulandi.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
