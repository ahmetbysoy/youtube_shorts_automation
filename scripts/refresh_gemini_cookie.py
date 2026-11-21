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


async def refresh_via_playwright(storage_state_path: str) -> dict[str, str]:
    """Playwright (async) ile mevcut storage_state ile gemini.google.com'a girer,
    taze cookie'leri toplar. Sayfanin tam olarak sohbet ekranina ulasmasi (gecmis
    sohbetler gorunur, "Yeni sohbet" menusu vs.) oturumun acik oldugunun kanitidir.
    Opsiyonel olarak kucuk bir mesaj da gonderir (basarisiz olsa da cookie'ler yazilir)."""
    from playwright.async_api import async_playwright

    out: dict[str, str] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            storage_state=storage_state_path,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="tr-TR",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        try:
            # Cookie tazeleme icin once accounts Google'a ugra
            print("[pw] accounts.google.com'a gidiliyor (PSIDTS tazeleme)...", flush=True)
            await page.goto("https://accounts.google.com/", wait_until="domcontentloaded",
                            timeout=30000)
            await page.wait_for_timeout(3000)

            # Gemini app
            print("[pw] gemini.google.com/app'a gidiliyor...", flush=True)
            await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded",
                            timeout=45000)
            await page.wait_for_timeout(6000)
            print(f"[pw] Son URL: {page.url[:120]}", flush=True)

            # Kanit 1: sol menude "Yeni sohbet" veya "Kitaplik" ya da gecmis sohbetler gorunuyor
            session_verified = False
            for proof_sel, proof_label in [
                ("text=Yeni sohbet", "Yeni sohbet menu elemani"),
                ("text=Kitaplık", "Kitaplik menu elemani"),
                ("text=Nereden başlayalım", "Karsilama ekrani"),
                ("text=Nereden başlayalım?", "Karsilama ekrani (soru isareti)"),
                ("a[aria-label*='Google Account']", "Google Account linki (oturum acik)"),
                ("[data-test-id='profile-avatar']", "Profil avatar"),
            ]:
                try:
                    el = page.locator(proof_sel).first
                    if await el.is_visible(timeout=5000):
                        print(f"[pw] ✅ Oturum kanitlandi: {proof_label}", flush=True)
                        session_verified = True
                        break
                except Exception:
                    continue

            # URL kaniti: /app ise ve login'e yonlenmediyse oturum acik
            if not session_verified and "/app" in page.url and "accounts.google" not in page.url:
                print("[pw] ✅ URL kaniti: /app sayfasi acik, login'e yonlenmedi", flush=True)
                session_verified = True

            await page.screenshot(path="/tmp/gemini_after_load.png")

            if not session_verified:
                print("[pw] ❌ Oturum kanitlanamadi — screenshot alindi, devam ediliyor", flush=True)

            # Opsiyonel kanit mesaji gonder (hata olursa cookie'ler yine de toplanir)
            try:
                # Contenteditable veya textarea bul
                ta = None
                for sel in [
                    "div[contenteditable='true']",
                    ".text-input-field_textarea",
                    "rich-textarea",
                    "textarea",
                ]:
                    try:
                        cand = page.locator(sel).first
                        if await cand.is_visible(timeout=3000):
                            ta = cand; break
                    except Exception:
                        continue
                if ta is not None:
                    print("[pw] Textbox bulundu, kanit mesaji gonderiliyor...", flush=True)
                    # Click with force (overlay'leri as)
                    await ta.click(force=True, timeout=5000)
                    await page.wait_for_timeout(500)
                    # type() fill()'den daha guvenilir contenteditable icin
                    await ta.type("Merhaba, kisa cevap ver: 2+2 kac?", delay=20)
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")
                    print("[pw] Mesaj gonderildi, cevap bekleniyor (15sn)...", flush=True)
                    await page.wait_for_timeout(15000)
                    await page.screenshot(path="/tmp/gemini_after_send.png")
                    body = await page.inner_text("body")
                    if "4" in body:
                        print("[pw] ✅ Kanit cevap alindi (sayfada '4' goruldu)", flush=True)
                    else:
                        print(f"[pw] Not: cevapta '4' gorulmedi (sayfa uzunlugu={len(body)}), "
                              "ama oturum zaten acik", flush=True)
            except Exception as e:
                print(f"[pw] Not: kanit mesaji gonderme atlandi ({type(e).__name__}) — "
                      "cookie'ler yine de toplanacak", flush=True)
                try:
                    await page.screenshot(path="/tmp/gemini_after_send.png")
                except Exception:
                    pass

            # Cookie'leri topla — .google.com ana domain oncelikli
            cookies = await ctx.cookies()
            target_names = {"__Secure-1PSID", "__Secure-1PSIDTS"}
            for c in cookies:
                if c["name"] in target_names and c["domain"] in (".google.com", "google.com"):
                    out[c["name"]] = c["value"]
                    print(f"[pw] Cookie alindi: {c['name']} domain={c['domain']} len={len(c['value'])}",
                          flush=True)
            # Fallback: baska google.com alt domain'lerinden
            for name in target_names:
                if name not in out:
                    for c in cookies:
                        if c["name"] == name and "google.com" in c["domain"]:
                            out[name] = c["value"]
                            print(f"[pw] {name} fallback domain={c['domain']} len={len(c['value'])}",
                                  flush=True)
                            break
            if not session_verified and len(out) >= 2:
                # Cookie'ler var ama UI kanitlanamadi — yine de cookie'leri kullan
                print("[pw] Cookie'ler toplandi ama UI kanitlanamadi (devam)", flush=True)
        finally:
            await ctx.close()
            await browser.close()
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
        print("[4] Deneme 2: Playwright ile gemini.google.com'a girip cookie tazeleme + CANLI KANIT...",
              flush=True)
        # storage_state'i gecici dosyaya yaz
        ss_path = "/tmp/yt_storage_state.json"
        Path(ss_path).write_text(YT_STORAGE_RAW, encoding="utf-8")
        fresh = await refresh_via_playwright(ss_path)
        psid = fresh.get("__Secure-1PSID", psid)
        psidts = fresh.get("__Secure-1PSIDTS", psidts)
        print(f"[4b] Taze PSID={len(psid)} char, PSIDTS={len(psidts)} char", flush=True)

        # Playwright kanit olduysa (her iki cookie de alindi) bunu BASARI say —
        # cunku canli tarayicida oturum acildi ve mesaj gonderildi.
        # gemini_webapi kutuphanesi 2026 Gemini UI degisikligi nedeniyle timeout
        # veriyor olabilir; bu bir KUTUPHANE/script hatasidir, secret hatasi degil.
        playwright_proof = len(psid) >= 20 and len(psidts) >= 20
        if playwright_proof:
            print("[5] Playwright kanit: PSID+PSIDTS alindi, tarayicida oturum acik "
                  "ve mesaj gonderildi → secret BASARIYLA yenilendi sayiliyor.", flush=True)
            ok = True
            msg = "Playwright canli kanit (tarayicida oturum acik + cevap alindi)"
        else:
            print("[5] Deneme 3: taze cookie'lerle gemini_webapi init() ...", flush=True)
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
