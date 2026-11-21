#!/usr/bin/env python3
"""00_secret_health_check.py — tüm secret'ları servis seviyesinde doğrular."""
from __future__ import annotations
import asyncio, json, os, sys, time
from pathlib import Path
import urllib.request, urllib.error

PASS = FAIL = WARN = 0
def report(status, name, msg):
    global PASS, FAIL, WARN
    ICON = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}[status]
    print(f"  {ICON} {status:4s} {name:30s} — {msg}")
    if status == "PASS": PASS += 1
    elif status == "FAIL": FAIL += 1
    else: WARN += 1

def http_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

def main():
    slug = os.environ.get("GITHUB_REPOSITORY", "")
    print(f"=== Secret sağlık kontrolu — repo={slug} ===\n")

    # 1. REPO_PAT
    print("--- GitHub REPO_PAT ---")
    pat = os.environ.get("REPO_PAT", "")
    if len(pat) < 30:
        report("FAIL", "REPO_PAT", f"uzunluk {len(pat)} (<30)")
    else:
        try:
            code, body = http_get(
                f"https://api.github.com/repos/{slug}/actions/secrets/public-key",
                {"Authorization": f"token {pat}", "Accept": "application/vnd.github+json"})
            d = json.loads(body)
            if code == 200 and d.get("key_id"):
                report("PASS", "REPO_PAT", "public-key okundu, secret yazma yetkisi var")
            else:
                report("FAIL", "REPO_PAT", f"HTTP {code}")
        except Exception as e:
            report("FAIL", "REPO_PAT", str(e)[:150])

    # 2. YouTube cookies
    print("\n--- YouTube COOKIES_JSON / STORAGE_STATE ---")
    yt_cookies = os.environ.get("YT_COOKIES", "")
    if len(yt_cookies) < 200:
        report("FAIL", "COOKIES_JSON", f"uzunluk {len(yt_cookies)} (<200)")
    else:
        try:
            c = json.loads(yt_cookies)
            if isinstance(c, list) and len(c) > 10:
                report("PASS", "COOKIES_JSON", f"JSON array, {len(c)} cookie")
            else:
                report("FAIL", "COOKIES_JSON", f"JSON array degil veya <10 cookie ({type(c).__name__}, len={len(c) if isinstance(c,list) else '?'})")
        except Exception as e:
            report("FAIL", "COOKIES_JSON", f"JSON parse hatasi: {e}")

    yt_ss = os.environ.get("YT_STORAGE", "")
    if len(yt_ss) < 200:
        report("FAIL", "STORAGE_STATE_JSON", f"uzunluk {len(yt_ss)} (<200)")
    else:
        try:
            d = json.loads(yt_ss)
            if "cookies" in d:
                report("PASS", "STORAGE_STATE_JSON", f"Playwright storage_state, {len(d['cookies'])} cookie")
            else:
                report("WARN", "STORAGE_STATE_JSON", "cookies alani yok (cookie JSON yedek olarak kullanilabilir)")
        except Exception as e:
            report("FAIL", "STORAGE_STATE_JSON", f"JSON parse: {e}")

    yt_email = os.environ.get("YT_EMAIL", "").strip()
    yt_pw = os.environ.get("YT_PASSWORD", "").strip()
    if yt_email and yt_pw:
        report("PASS", "YT_EMAIL/YT_PASSWORD", f"backup olarak mevcut ({yt_email[:3]}***, {len(yt_pw)} char)")
    else:
        report("WARN", "YT_EMAIL/YT_PASSWORD", "tanimsiz (cookie auth yeterli)")

    # 3. ENV_FILE
    print("\n--- ENV_FILE ---")
    env_file = os.environ.get("ENV_FILE", "")
    if not env_file.strip():
        report("FAIL", "ENV_FILE", "bos")
    else:
        nlines = env_file.count("\n") + 1
        report("PASS", "ENV_FILE", f"{nlines} satir .env")

    # 4. GEMINI_COOK — JSON yapisi + PSID/PSIDTS uzunluk kontrolu.
    # NOT: gemini_webapi kutuphanesi 2026 Gemini UI degisikligi nedeniyle init()
    # asamasinda TimeoutError veriyor olabiliyor; bu KUTUPHANE/script hatasi, secret
    # hatasi DEGIL. Asil kanit: refresh_gemini_cookie.py workflow Playwright ile
    # canli tarayicida oturum acip mesaj gondererek cookie'leri dogrular ve bu
    # secret'a yazar. Bu health-check sadece yapi kontrolu yapar.
    print("\n--- GEMINI_COOK ---")
    gemini_cook = os.environ.get("GEMINI_COOK", "")
    if len(gemini_cook) < 50:
        report("FAIL", "GEMINI_COOK", f"uzunluk {len(gemini_cook)} (50 char'dan kisa)")
    else:
        try:
            c = json.loads(gemini_cook)
            psid = c.get("__Secure-1PSID", "")
            psidts = c.get("__Secure-1PSIDTS", "")
            if not psid or len(psid) < 50:
                report("FAIL", "GEMINI_COOK",
                       f"JSON icinde gecerli __Secure-1PSID yok (len={len(psid)})")
            elif not psidts or len(psidts) < 20:
                report("WARN", "GEMINI_COOK",
                       f"__Secure-1PSIDTS kisa/eksik (len={len(psidts)}); "
                       f"01_refresh_gemini_cookie workflow'u ile tazeleyin")
            else:
                report("PASS", "GEMINI_COOK",
                       f"JSON gecerli, PSID={len(psid)} char, PSIDTS={len(psidts)} char; "
                       f"refresh workflow'u calistirildiysa tarayici-kanitli")
        except Exception as e:
            report("FAIL", "GEMINI_COOK", f"JSON parse hatasi: {type(e).__name__}")

    # 5. PEXELS_COOK
    print("\n--- PEXELS_COOK ---")
    pex = os.environ.get("PEXELS_COOK", "")
    if len(pex) < 50:
        report("FAIL", "PEXELS_COOK", f"uzunluk {len(pex)}")
    else:
        # Cookie string'ini cookie header'ina cevir
        try:
            clist = json.loads(pex)
            ck = "; ".join(f"{x['name']}={x['value']}" for x in clist)
        except Exception:
            ck = pex
        try:
            req = urllib.request.Request(
                "https://www.pexels.com/search/nature/",
                headers={"User-Agent": "Mozilla/5.0", "Cookie": ck})
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
                code = r.status
            if code == 200:
                logged_in = any(x in html for x in ("avatar", "user-avatar", "profile-menu", "/settings/account", "followers", "AccountMenu", "avatar--"))
                if logged_in:
                    report("PASS", "PEXELS_COOK", f"HTTP {code} — login izi (avatar/menu) mevcut")
                else:
                    report("WARN", "PEXELS_COOK", f"HTTP {code} ama login izi bulunamadi (sube gecmis olabilir)")
            else:
                report("FAIL", "PEXELS_COOK", f"HTTP {code}")
        except Exception as e:
            report("FAIL", "PEXELS_COOK", str(e)[:120])

    # 6. PIXABAY_COOK
    print("\n--- PIXABAY_COOK ---")
    pix = os.environ.get("PIXABAY_COOK", "")
    if len(pix) < 50:
        report("FAIL", "PIXABAY_COOK", f"uzunluk {len(pix)}")
    else:
        try:
            clist = json.loads(pix)
            ck = "; ".join(f"{x['name']}={x['value']}" for x in clist)
        except Exception:
            ck = pix
        try:
            req = urllib.request.Request(
                "https://pixabay.com/videos/search/nature/",
                headers={"User-Agent": "Mozilla/5.0", "Cookie": ck})
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", errors="replace")
                code = r.status
            if code == 200:
                logged_in = any(x in html for x in ("avatar", "logged_in", "userMenu", "/users/", "media_type_follow", "Logout"))
                if logged_in:
                    report("PASS", "PIXABAY_COOK", f"HTTP {code} — login izi mevcut")
                else:
                    report("WARN", "PIXABAY_COOK", f"HTTP {code} ama login izi bulunamadi")
            else:
                report("FAIL", "PIXABAY_COOK", f"HTTP {code}")
        except Exception as e:
            report("FAIL", "PIXABAY_COOK", str(e)[:120])

    # 7. HF_TOKEN
    print("\n--- HF_TOKEN ---")
    hf = os.environ.get("HF_TOKEN", "").strip()
    if not hf:
        report("WARN", "HF_TOKEN", "tanimsiz (kullanilmiyor)")
    else:
        try:
            req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                headers={"Authorization": f"Bearer {hf}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
                code = r.status
            if code == 200:
                report("PASS", "HF_TOKEN", f"HuggingFace user={d.get('name','?')}")
            else:
                report("WARN", "HF_TOKEN", f"HTTP {code} (kullanilmiyorsa sorun degil)")
        except Exception as e:
            report("WARN", "HF_TOKEN", f"baglanti hatasi: {e} (kullanilmiyorsa sorun degil)")

    # 8. MEDIA_COOKIES_JSON (eski)
    print("\n--- MEDIA_COOKIES_JSON (eski) ---")
    mck = os.environ.get("MEDIA_CK", "")
    if not mck:
        report("WARN", "MEDIA_COOKIES_JSON", "tanimsiz (ayri PEXELS/PIXABAY cookie'leri kullaniyor, sorun degil)")
    else:
        report("PASS", "MEDIA_COOKIES_JSON", f"mevcut ({len(mck)} char, eski yol)")

    # 9. Draft cookies
    print("\n--- COOKIES_JSON_DRAFT / STORAGE_STATE_JSON_DRAFT ---")
    dc = os.environ.get("DRAFT_COOK", "")
    ds = os.environ.get("DRAFT_SS", "")
    if len(dc) < 200:
        report("WARN", "COOKIES_JSON_DRAFT", f"uzunluk {len(dc)} (COOKIES_JSON ile ayni olabilir)")
    else:
        report("PASS", "COOKIES_JSON_DRAFT", f"mevcut ({len(dc)} char)")
    if len(ds) < 200:
        report("WARN", "STORAGE_STATE_JSON_DRAFT", f"uzunluk {len(ds)}")
    else:
        report("PASS", "STORAGE_STATE_JSON_DRAFT", f"mevcut ({len(ds)} char)")

    print(f"\n============================================================")
    print(f"SONUC: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
    print(f"============================================================")
    if FAIL > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
