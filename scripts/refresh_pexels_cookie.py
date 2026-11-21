#!/usr/bin/env python3
"""
PEXELS_COOK refresh: calisan YouTube STORAGE_STATE_JSON ile acik Google oturumundan
Pexels'a Google SSO ile giris yapar, taze cookie'leri toplar, ve GitHub secret'ina yazar.

Strateji:
  1) Calisan YT storage_state'i ile Playwright tarayici ac (Google oturumu .google.com'da hazir)
  2) https://www.pexels.com/login/ sayfasina git (CF challenge varsa bekle)
  3) "Continue with Google" butonunu bul, tikla
  4) Google hesap secici acilirsa tek olan hesaba tikla
  5) OAuth onay ekrani varsa "Allow"/"Continue" de
  6) Pexels ana sayfaya dondugunde avatar / "Log out" / indirme gibi login izi gor
  7) .pexels.com / www.pexels.com domain'li tum cookie'leri topla
  8) GitHub Secrets API ile PEXELS_COOK'u guncelle
  9) Kanit: /search/nature/ sayfasina gidip login sonucu gelebilecek sonuclari dogrula
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import requests

OWNER = "ahmetbysoy"
REPO = "youtube_shorts_automation"
REPO_PAT = os.environ.get("REPO_PAT", "")
YT_STORAGE_RAW = os.environ.get("STORAGE_STATE_JSON") or os.environ.get("STORAGE_STATE_JSON_1", "")

GH_HEADERS = {
    "Authorization": f"token {REPO_PAT}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

PEXELS_DOMAINS = {".pexels.com", "www.pexels.com", "pexels.com"}
COOKIE_FIELDS = ("name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite")


def encrypt_secret(public_key: str, value: str) -> str:
    from nacl import encoding, public as nacl_public
    pkey = nacl_public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed = nacl_public.SealedBox(pkey).encrypt(value.encode("utf-8"))
    return base64.b64encode(sealed).decode("utf-8")


def put_secret(name: str, value: str) -> None:
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


def pick_cookies(all_cookies: list[dict]) -> list[dict]:
    """Sadece Pexels domain'li cookie'leri filtrele ve gerekli alanlari sakla."""
    out = []
    seen: set[tuple[str, str]] = set()
    for c in all_cookies:
        d = str(c.get("domain", "")).lower()
        n = c.get("name", "")
        if d in PEXELS_DOMAINS and n and (d, n) not in seen:
            out.append({k: c.get(k) for k in COOKIE_FIELDS if k in c})
            # domain normalize: .pexels.com ile www.pexels.com'u ikisini de tut
            seen.add((d, n))
    return out


async def main() -> int:
    if not REPO_PAT:
        print("HATA: REPO_PAT yok", file=sys.stderr); return 1
    if not YT_STORAGE_RAW:
        print("HATA: STORAGE_STATE_JSON yok", file=sys.stderr); return 1

    print(f"[1] YT storage_state boyut={len(YT_STORAGE_RAW)} byte", flush=True)

    from playwright.async_api import async_playwright

    ss_path = "/tmp/yt_storage_state.json"
    Path(ss_path).write_text(YT_STORAGE_RAW, encoding="utf-8")

    collected: list[dict] = []
    login_verified = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            storage_state=ss_path,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        try:
            # Adim 1: Login sayfasina git (CF challenge dahil)
            print("[pw] pexels.com/login/ sayfasina gidiliyor...", flush=True)
            await page.goto("https://www.pexels.com/login/", wait_until="domcontentloaded",
                            timeout=60000)
            await page.wait_for_timeout(8000)
            print(f"[pw] URL: {page.url[:120]}", flush=True)
            await page.screenshot(path="/tmp/pexels_01_login.png")

            # Adim 2: Once zaten giris yapmis miyiz? Avatar / account menu varsa direkt topla
            for already_sel in [
                "button[aria-label*='Avatar']", "button[aria-label*='account']",
                "a[href*='/settings']", "a[href*='/account']", "button.avatar",
                "[data-testid='avatar-button']", "[class*='Avatar']",
                "button:has-text('Log out')",
                "img.AvatarImage",
            ]:
                try:
                    if await page.locator(already_sel).first.is_visible(timeout=2000):
                        print(f"[pw] Zaten giris yapilmis gorunuyor (sel={already_sel})", flush=True)
                        login_verified = True
                        break
                except Exception:
                    continue

            if not login_verified:
                # Adim 3: "Continue with Google" butonunu bul
                google_btn = None
                for sel, label in [
                    ("button:has-text('Continue with Google')", "button 'Continue with Google'"),
                    ("a:has-text('Continue with Google')", "a 'Continue with Google'"),
                    ("button:has-text('Sign up with Google')", "Sign up with Google"),
                    ("button:has-text('Google')", "button Google"),
                    ("[data-testid*='google']", "data-testid google"),
                    ("button[aria-label*='Google']", "aria-label Google"),
                    ("[class*='social-google']", "class social-google"),
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=3000):
                            google_btn = el
                            print(f"[pw] Google SSO butonu bulundu: {label}", flush=True)
                            break
                    except Exception:
                        continue

                if google_btn is not None:
                    await google_btn.click(timeout=10000)
                    await page.wait_for_timeout(5000)
                    print(f"[pw] Google SGO'ya yonlendirildikten sonra URL: {page.url[:120]}", flush=True)
                    await page.screenshot(path="/tmp/pexels_02_google.png")
                else:
                    print("[pw] UYARI: Google SSO butonu bulunamadi — "
                          "sayfa zaten girisli ya da CF engelledi olabilir.", flush=True)

                # Adim 4: Google hesap secici (hesap listesi)
                for _ in range(3):
                    cur = page.url
                    if "accounts.google.com" in cur:
                        print("[pw] Google hesap secici sayfasi bekleniyor...", flush=True)
                        # Hesap secici — data-identifier veya email ile ilk secilebilir hesap
                        for sel in [
                            "[data-identifier*='gmail.com']",
                            "li:has([data-email])",
                            "div[role='link']:has-text('@gmail.com')",
                            "div:has-text('mentan')",
                            "div[role='link']",  # herhangi bir hesap linki
                        ]:
                            try:
                                acc = page.locator(sel).first
                                if await acc.is_visible(timeout=5000):
                                    txt = await acc.inner_text(timeout=2000)
                                    print(f"[pw] Hesap bulundu, tiklaniyor: {txt[:60]!r}", flush=True)
                                    await acc.click(timeout=5000)
                                    await page.wait_for_timeout(6000)
                                    break
                            except Exception:
                                continue
                        await page.wait_for_timeout(3000)
                    else:
                        break
                print(f"[pw] Hesap seciminden sonra URL: {page.url[:120]}", flush=True)
                await page.screenshot(path="/tmp/pexels_03_after_acc.png")

                # Adim 5: OAuth onay ekrani "Continue" / "Allow"
                if "accounts.google.com" in page.url or "oauth" in page.url.lower():
                    for approval_sel in [
                        "button:has-text('Continue')",
                        "button:has-text('Allow')",
                        "button:has-text('I agree')",
                        "#submit_approve_access",
                        "button[jsname='LgbsSe']",
                        "span:has-text('Allow')",
                    ]:
                        try:
                            btn = page.locator(approval_sel).first
                            if await btn.is_visible(timeout=3000):
                                print(f"[pw] OAuth onay butonu: {approval_sel}", flush=True)
                                await btn.click(timeout=5000)
                                await page.wait_for_timeout(6000)
                                break
                        except Exception:
                            continue
                print(f"[pw] OAuth sonrasi URL: {page.url[:120]}", flush=True)
                await page.screenshot(path="/tmp/pexels_04_after_oauth.png")

                # Pexels'e geri donmesini bekle
                for _ in range(20):
                    await page.wait_for_timeout(3000)
                    cur = page.url
                    if "pexels.com" in cur and "accounts.google" not in cur:
                        print(f"[pw] Pexels'e geri donuldu: {cur[:120]}", flush=True)
                        break

            await page.wait_for_timeout(5000)

            # Adim 6: Giris kanit — avatar, logout, upload vb.
            for proof_sel, proof_label in [
                ("button[aria-label*='Avatar']", "Avatar button"),
                ("a[href*='/settings']", "Settings link"),
                ("a[href*='/account']", "Account link"),
                ("button:has-text('Upload')", "Upload button (girisli)"),
                ("a:has-text('Log out')", "Log out link"),
                ("button:has-text('Log out')", "Log out button"),
                ("[class*='avatar']", "avatar class"),
                ("[data-testid*='avatar']", "data-testid avatar"),
                ("img.AvatarImage", "AvatarImage img"),
            ]:
                try:
                    el = page.locator(proof_sel).first
                    if await el.is_visible(timeout=3000):
                        print(f"[pw] ✅ Giris kanitlandi: {proof_label}", flush=True)
                        login_verified = True
                        break
                except Exception:
                    continue

            # URL / login-page disi ise dolayli kanit
            if not login_verified and "/login" not in page.url and "accounts.google" not in page.url \
                    and "pexels.com" in page.url:
                # Gövde metninde "Log out" geciyor mu?
                body = await page.inner_text("body")
                if "Log out" in body or "Upload" in body or "Your profile" in body or "Me" in body[:200]:
                    print("[pw] ✅ Dolayli giris kanit: body metninde login izi bulundu", flush=True)
                    login_verified = True

            await page.screenshot(path="/tmp/pexels_05_home.png")

            # Adim 7: Cookie'leri topla
            all_cookies = await ctx.cookies()
            collected = pick_cookies(all_cookies)
            print(f"[pw] Pexels cookie'leri toplandi: {len(collected)} adet", flush=True)
            for c in collected[:8]:
                print(f"[pw]   {c.get('domain',''):20} {c.get('name','')[:30]:30} len={len(str(c.get('value','')))}",
                      flush=True)
            if len(collected) > 8:
                print(f"[pw]   ... ve {len(collected) - 8} diger", flush=True)

            # Adim 8 (opsiyonel kanit): arama sayfasina gidip sonuc geliyor mu
            try:
                await page.goto("https://www.pexels.com/search/nature/",
                                wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                await page.screenshot(path="/tmp/pexels_06_search.png")
                title = await page.title()
                print(f"[pw] Arama sayfasi title: {title[:80]}", flush=True)
                # Search result count veya photo card var mi?
                cards = await page.locator("article, a[href*='/photo/'], a[href*='/video/']").count()
                print(f"[pw] Arama sonucu elemanlari: ~{cards}", flush=True)
            except Exception as e:
                print(f"[pw] Arama kaniti atlandi: {type(e).__name__}", flush=True)

        finally:
            await ctx.close()
            await browser.close()

    # Degerlendirme
    if not collected:
        print("\nSONUC: BASARISIZ — hic Pexels cookie toplanamadi", file=sys.stderr)
        return 2

    # En azindan bir session-ish cookie var mi?
    cookie_names = {c["name"] for c in collected}
    session_hints = {"sessionid", "csrftoken", "cf_clearance", "_pexels_session",
                     "pexels_session", "session", "auth"}
    found_hints = cookie_names & session_hints

    print(f"\n[sonuc] login_verified={login_verified}, session_hints={found_hints}, "
          f"cookie_count={len(collected)}", flush=True)

    # Cookie'leri JSON'a yaz
    payload = json.dumps(collected)
    print(f"[gh] PEXELS_COOK JSON boyutu: {len(payload)} byte", flush=True)

    if not login_verified and not found_hints:
        print("SONUC: BASARISIZ — ne giris kanitlandi ne session cookie bulundu", file=sys.stderr)
        return 3

    # Secret'a yaz
    put_secret("PEXELS_COOK", payload)
    print("\nSONUC: BASAIRI — PEXELS_COOK yenilendi ve kanitlandi.", flush=True)
    if not login_verified:
        print("  (not: avatar/profil gorunmedi ama session cookie'ler var; "
              "health-check ile HTTP testi yapilacak)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
