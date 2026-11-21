#!/usr/bin/env python3
"""
PIXABAY_COOK ile Playwright uzerinden gercek arama testi.
Pipeline'in kullandigi tam ayni yontem: cookie'leri yukle, arama sayfasina git,
video linklerini say.
"""
import asyncio, json, os, sys
from pathlib import Path
from playwright.async_api import async_playwright

async def main() -> int:
    raw = os.environ.get("PIXABAY_COOK", "").strip()
    if not raw:
        print("HATA: PIXABAY_COOK bos", file=sys.stderr); return 1

    try:
        cookies = json.loads(raw)
    except Exception as e:
        print(f"HATA: PIXABAY_COOK JSON degil: {e}", file=sys.stderr); return 1
    print(f"[1] Yuklenen cookie sayisi: {len(cookies)}", flush=True)
    for c in cookies:
        print(f"    {c.get('domain',''):20} {c.get('name',''):25} len={len(str(c.get('value','')))}",
              flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")

        if cookies:
            await ctx.add_cookies(cookies)

        page = await ctx.new_page()
        try:
            print("\n[2] pixabay.com/videos/search/nature/ sayfasina gidiliyor...", flush=True)
            resp = await page.goto("https://pixabay.com/videos/search/nature/",
                                   wait_until="domcontentloaded", timeout=60000)
            print(f"[2] HTTP status: {resp.status if resp else None}", flush=True)

            # CF bekleme
            for i in range(12):
                body = ""
                try:
                    body = (await page.inner_text("body", timeout=2000))[:300]
                except Exception:
                    pass
                if "Verify you are human" not in body and "Just a moment" not in body \
                        and "Performing security" not in body:
                    print(f"[cf] {i*5}s sonra gecti", flush=True)
                    break
                # Checkbox'a tiklamayi dene
                try:
                    for frame in page.frames:
                        cb = frame.locator("input[type='checkbox'], label:has-text('Verify')").first
                        if await cb.is_visible(timeout=500):
                            print(f"[cf] Checkbox bulundu, tiklaniyor...", flush=True)
                            await cb.click(force=True, timeout=3000)
                            break
                except Exception:
                    pass
                await page.wait_for_timeout(5000)
                await page.screenshot(path=f"/tmp/pixabay_cf_{i}.png")

            await page.wait_for_timeout(5000)
            title = await page.title()
            cur = page.url
            print(f"[3] URL: {cur[:100]}", flush=True)
            print(f"[3] Title: {title[:100]}", flush=True)

            video_links = await page.locator("a[href*='/videos/']").count()
            body = await page.inner_text("body")
            login_indicators = ["Log out", "Logout", "My account", "Upload", "Following",
                                "avatar", "My Pixabay"]
            logged_in = any(kw in body for kw in login_indicators)
            print(f"[3] video links: {video_links}", flush=True)
            print(f"[3] logged_in izleri: {logged_in}", flush=True)

            await page.screenshot(path="/tmp/pixabay_cookie_test.png")

            if video_links >= 5 and "Just a moment" not in title:
                print("\nSONUC: ✅ PIXABAY_COOK CALISIYOR — arama sonucu alindi", flush=True)
                return 0
            else:
                print(f"\nSONUC: ❌ Calismiyor (video_links={video_links}, title={title})",
                      file=sys.stderr)
                return 1
        finally:
            await ctx.close()
            await browser.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
