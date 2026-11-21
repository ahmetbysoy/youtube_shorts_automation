#!/usr/bin/env python3
"""
PEXELS_COOK refresh v2: calisan YouTube STORAGE_STATE_JSON ile Google SSO uzerinden
Pexels'a giris yapar, taze cookie'leri toplar, ve GitHub secret'ina yazar.

Gelistirmeler:
- Cloudflare Turnstile checkbox'ini iframe icinde bulup otomatik tiklar
- navigator.webdriver maskeleme, gercekci UA ve viewport
- CF gecene kadar uzun bekleme dongusu
- /login sayfasinda kaliyorsa BASARISIZ say (cookie'leri de yazma)
- Gercek oturum acildiginda ana sayfaya gidip avatar/Upload kaniti arar
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
    out = []
    seen: set[tuple[str, str]] = set()
    for c in all_cookies:
        d = str(c.get("domain", "")).lower()
        n = c.get("name", "")
        if d in PEXELS_DOMAINS and n and (d, n) not in seen:
            out.append({k: c.get(k) for k in COOKIE_FIELDS if k in c})
            seen.add((d, n))
    return out


async def pass_cloudflare(page, screenshot_prefix: str = "/tmp/pexels_cf") -> bool:
    """Cloudflare "Verify you are human" checkbox'ini iframe icinde bulup tiklamayi dener.
    Asil bekleme CF otomatik gecer (turnstile invisible) — checkbox sadece manuel tetikleme."""
    print("[cf] Cloudflare kontrolu basladi...", flush=True)
    for attempt in range(8):
        # Anasayfa check
        body_text = ""
        try:
            body_text = (await page.inner_text("body", timeout=2000))[:500]
        except Exception:
            pass
        if "Performing security verification" not in body_text and "Just a moment" not in body_text \
                and "Verify you are human" not in body_text:
            print(f"[cf] CF gorgulendi (deneme {attempt+1})", flush=True)
            return True

        # iframe ile checkbox bulmaya calis
        try:
            frames = page.frames
            for frame in frames:
                try:
                    cb = frame.locator("input[type='checkbox'], label:has-text('Verify')").first
                    if await cb.is_visible(timeout=1000):
                        print(f"[cf] Checkbox/label bulundu, tiklaniyor (deneme {attempt+1})",
                              flush=True)
                        await cb.click(force=True, timeout=3000)
                        await page.wait_for_timeout(5000)
                        break
                except Exception:
                    continue
        except Exception:
            pass

        await page.wait_for_timeout(5000)
        try:
            await page.screenshot(path=f"{screenshot_prefix}_{attempt}.png")
        except Exception:
            pass

    # Son bir kontrol
    try:
        body_text = (await page.inner_text("body", timeout=2000))[:500]
        if "Verify you are human" in body_text or "Performing security" in body_text:
            print("[cf] CF asamadi (hala verify sayfasi)", flush=True)
            return False
    except Exception:
        pass
    print("[cf] CF beklenen surecte gecti", flush=True)
    return True


async def wait_for_google_account_picker(page, max_wait: int = 30) -> bool:
    """Google hesap secici sayfasinda bir hesaba tiklar."""
    for _ in range(max_wait // 3):
        cur = page.url
        if "accounts.google.com" not in cur and "oauthchoice" not in cur:
            return True
        # Hesap kartlarindan birini bul
        for sel in [
            "[data-identifier]",
            "div[role='link'][data-email]",
            "li:has([data-email])",
            "div[role='link']",
        ]:
            try:
                els = page.locator(sel)
                cnt = await els.count()
                for i in range(cnt):
                    try:
                        el = els.nth(i)
                        if await el.is_visible(timeout=500):
                            t = await el.inner_text(timeout=1000)
                            if "@" in t or "mentan" in t.lower() or i == 0:
                                print(f"[google] Hesap seciliyor: {t[:50]!r}", flush=True)
                                await el.click(timeout=5000)
                                await page.wait_for_timeout(6000)
                                return True
                    except Exception:
                        continue
            except Exception:
                continue
        await page.wait_for_timeout(3000)
    return False


async def wait_for_oauth_approval(page, max_wait: int = 20) -> bool:
    """Google OAuth onay ekrani (Allow/Continue)."""
    for _ in range(max_wait // 3):
        cur = page.url
        if "accounts.google.com" not in cur and "oauth" not in cur.lower() and "consent" not in cur:
            return True
        if "accounts.google.com" in cur:
            for sel in [
                "button[jsname='LgbsSe']",  # Allow/Continue/Seç
                "#submit_approve_access",
                "button:has-text('Allow')",
                "button:has-text('Continue')",
                "button:has-text('I agree')",
                "button:has-text('Devam')",
                "button:has-text('İzin ver')",
                "span:has-text('Allow')",
                "span:has-text('Continue')",
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible(timeout=1500):
                        print(f"[oauth] Onay butonu bulundu: {sel}", flush=True)
                        await btn.click(timeout=5000)
                        await page.wait_for_timeout(5000)
                        return True
                except Exception:
                    continue
        await page.wait_for_timeout(3000)
    return False


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

    # Headed mode (xvfb-run ile CI'da pencere acarak) — CF tespitini azaltir
    headless_mode = not bool(os.environ.get("DISPLAY"))
    print(f"[0] Chromium baslatiliyor — headless={headless_mode} "
          f"(DISPLAY={os.environ.get('DISPLAY','')})", flush=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--lang=en-US,en;q=0.9",
                "--start-maximized",
            ],
        )
        ctx = await browser.new_context(
            storage_state=ss_path,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1366, "height": 768},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
                "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            },
        )
        # navigator.webdriver maskeleme
        await ctx.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en','tr'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            window.chrome = { runtime: {} };
        """)
        page = await ctx.new_page()
        try:
            # Adim 1: Login sayfasina git
            print("[2] pexels.com/login/ sayfasina gidiliyor...", flush=True)
            await page.goto("https://www.pexels.com/login/", wait_until="domcontentloaded",
                            timeout=60000)
            await page.wait_for_timeout(3000)
            print(f"[2b] Ilk URL: {page.url[:120]}", flush=True)
            await page.screenshot(path="/tmp/pexels_01_initial.png")

            # Adim 2: Cloudflare'i gec (8 deneme x 5sn = 40sn)
            cf_passed = await pass_cloudflare(page, "/tmp/pexels_cf")
            if not cf_passed:
                print("[cf] Sonrasinda da CF gecemedim, Google SSO butonunu yine de arayacagim",
                      flush=True)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/pexels_02_after_cf.png")

            # Adim 3: Once zaten giris yapmis miyiz? (avatar/upload)
            for already_sel in [
                "a[href*='/settings']", "a[href*='/account']",
                "button:has-text('Upload')",
                "a:has-text('Log out')",
                "[data-testid*='avatar']",
                "img[alt*='avatar']", "img[class*='Avatar']",
            ]:
                try:
                    if await page.locator(already_sel).first.is_visible(timeout=2000):
                        print(f"[3] Zaten girisli gorunuyor (sel={already_sel})", flush=True)
                        login_verified = True
                        break
                except Exception:
                    continue

            # Adim 4: "Continue with Google" butonunu bul
            if not login_verified:
                print("[4] Google SSO butonu araniyor...", flush=True)
                google_btn = None
                # Sayfada tum textleri tarayarak google kelimesini iceren tiklanabilir eleman bul
                for sel in [
                    "button:has-text('Continue with Google')",
                    "a:has-text('Continue with Google')",
                    "button:has-text('Sign up with Google')",
                    "button:has-text('Sign in with Google')",
                    "button:has-text('Google')",
                    "[data-testid*='google']",
                    "button[aria-label*='Google']",
                    "[class*='Google']",
                    "[class*='social-google']",
                    "button:has(img[alt*='Google'])",
                    "a[href*='accounts.google']",
                    "a[href*='oauth/google']",
                    "a[href*='auth/google']",
                ]:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=2000):
                            google_btn = el
                            print(f"[4] SSO butonu: {sel}", flush=True)
                            break
                    except Exception:
                        continue

                # Son care: sayfa kaynaginda google auth URL'si ara
                if google_btn is None:
                    href = await page.evaluate("""() => {
                        const links = [...document.querySelectorAll('a, button')];
                        for (const el of links) {
                            const t = (el.textContent||'').toLowerCase();
                            const h = el.href||'';
                            if ((t.includes('google') || h.includes('google') || h.includes('oauth'))
                                && el.offsetParent !== null) {
                                return h || el.getAttribute('data-href') || el.getAttribute('href');
                            }
                        }
                        return null;
                    }""")
                    if href:
                        print(f"[4] Sayfa kaynagindan Google SSO href'i: {href[:120]}", flush=True)
                        if href.startswith("/"):
                            href = "https://www.pexels.com" + href
                        await page.goto(href, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(5000)
                    else:
                        print("[4] HATA: Google SSO butonu bulunamadi", flush=True)
                        await page.screenshot(path="/tmp/pexels_03_no_sso.png")
                        # URL hala login sayfasindaysa ve buton yoksa CF'de kaldiysak don
                        body = await page.inner_text("body")
                        if "Verify you are human" in body or "Performing security" in body:
                            print("[4] Neden: CF checkbox'i manuel gerektiriyor.", flush=True)
                            return 10
                        return 4
                else:
                    await google_btn.click(force=True, timeout=10000)
                    await page.wait_for_timeout(6000)

                await page.screenshot(path="/tmp/pexels_04_after_sso_click.png")
                print(f"[4b] SGO sonrasi URL: {page.url[:120]}", flush=True)

                # Adim 5: Google hesap secici + OAuth onay
                await wait_for_google_account_picker(page, max_wait=20)
                await page.screenshot(path="/tmp/pexels_05_after_picker.png")
                print(f"[5] Hesap secimi sonrasi URL: {page.url[:120]}", flush=True)

                await wait_for_oauth_approval(page, max_wait=20)
                await page.screenshot(path="/tmp/pexels_06_after_oauth.png")
                print(f"[5b] OAuth sonrasi URL: {page.url[:120]}", flush=True)

                # Pexels donusunu bekle
                for _ in range(25):
                    await page.wait_for_timeout(3000)
                    cur = page.url
                    if "pexels.com" in cur and "accounts.google" not in cur \
                            and "consent" not in cur:
                        print(f"[6] Pexels'e donuldu: {cur[:120]}", flush=True)
                        break

                # CF bu noktada tekrar cikip gecebilir
                await pass_cloudflare(page, "/tmp/pexels_cf2")
                await page.wait_for_timeout(4000)
                await page.screenshot(path="/tmp/pexels_07_after_redirect.png")

            # Adim 7: Ana sayfaya gecip login kanitlarini ara
            print("[7] Ana sayfa / login kanit araniyor...", flush=True)
            for check_url in ["https://www.pexels.com/", "https://www.pexels.com/search/nature/"]:
                try:
                    await page.goto(check_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(4000)
                    await pass_cloudflare(page, "/tmp/pexels_cf_home")
                    await page.wait_for_timeout(2000)
                    cur = page.url
                    print(f"[7b] URL={cur[:120]}", flush=True)
                    if "/login" in cur:
                        print("[7] HALA LOGIN SAYFASINDA — giris BASARISIZ", flush=True)
                        continue
                    break
                except Exception:
                    continue

            await page.screenshot(path="/tmp/pexels_08_home.png")

            # Login kanit
            proof_selectors = [
                ("a[href*='/settings']", "Settings link"),
                ("a[href*='/account']", "Account link"),
                ("button:has-text('Upload')", "Upload button"),
                ("a:has-text('Log out')", "Log out link"),
                ("button:has-text('Log out')", "Log out button"),
                ("[data-testid*='avatar']", "avatar data-testid"),
                ("img[src*='avatars']", "avatar img"),
                ("button[aria-label*='avatar' i]", "avatar aria-label"),
                ("a[href*='@']", "user profile @ link"),
                ("div:has-text('Following')", "Following section"),
                ("a[href='/me/']", "/me/ link"),
                ("a:has-text('For you')", "For you (girisli feed)"),
            ]
            for sel, label in proof_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        print(f"[8] ✅ Login kanitlandi: {label}", flush=True)
                        login_verified = True
                        break
                except Exception:
                    continue

            if not login_verified:
                body = await page.inner_text("body", timeout=5000)
                for kw in ["Log out", "Upload ", "Following", "Collections", "Your profile",
                           "Profile", "For You"]:
                    if kw in body:
                        print(f"[8] ✅ Dolayli kanit (body metninde '{kw}' bulundu)", flush=True)
                        login_verified = True
                        break

            # Adim 8: Cookie'leri topla
            all_cookies = await ctx.cookies()
            collected = pick_cookies(all_cookies)
            print(f"[9] Pexels cookie'leri: {len(collected)} adet", flush=True)
            for c in collected:
                print(f"    {c.get('domain',''):20} {c.get('name','')[:35]:35} len={len(str(c.get('value','')))}",
                      flush=True)

            # Session cookie tanisi
            names = {c["name"] for c in collected}
            session_hints = {"sessionid", "csrftoken", "_pexels_session", "pexels_session",
                             "session", "pexels_auth", "pexels_user", "pexels_sid",
                             "pexels_anon", "pexels_at", "auth_token"}
            found_hints = names & session_hints
            print(f"[9b] session cookie adaylari: {found_hints}", flush=True)

        finally:
            await ctx.close()
            await browser.close()

    # --- Degerlendirme ---
    if not collected:
        print("\nSONUC: BASARISIZ — hic Pexels cookie toplanamadi", file=sys.stderr)
        return 2

    # KRITIK: login_verified False ise BASARISIZ say
    if not login_verified:
        print("\nSONUC: BASARISIZ — login kanitlanamadi (muhtemelen CF veya SSO hatasi)",
              file=sys.stderr)
        return 3

    payload = json.dumps(collected)
    print(f"\n[gh] PEXELS_COOK JSON boyutu: {len(payload)} byte ({len(collected)} cookie)", flush=True)
    put_secret("PEXELS_COOK", payload)
    print("\nSONUC: BASAIRI — PEXELS_COOK yenilendi ve kanitlandi.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
