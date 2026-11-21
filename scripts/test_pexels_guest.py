#!/usr/bin/env python3
"""Pexels'in misafir (cookiesiz) erisilebilir olup olmadigini Playwright ile test eder."""
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright

async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-dev-shm-usage"])
        ctx = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        )
        await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>false})")
        page = await ctx.new_page()
        try:
            # CF asmaya calis
            print("[1] pexels.com search sayfasina gidiliyor (guest)...", flush=True)
            resp = await page.goto("https://www.pexels.com/search/videos/nature/",
                                   wait_until="domcontentloaded", timeout=60000)
            print(f"[1] HTTP status: {resp.status if resp else None}", flush=True)
            await page.wait_for_timeout(8000)
            await page.screenshot(path="/tmp/pexels_guest_1.png")

            # CF kontrolu
            for _ in range(8):
                body = (await page.inner_text("body"))[:500]
                if "Verify you are human" not in body and "Just a moment" not in body \
                        and "Performing security" not in body:
                    break
                await page.wait_for_timeout(5000)
                await page.screenshot(path="/tmp/pexels_guest_cf.png")

            # Kac video linki var?
            await page.wait_for_timeout(2000)
            video_links = await page.locator("a[href*='/video/']").count()
            photo_links = await page.locator("a[href*='/photo/']").count()
            title = await page.title()
            print(f"[2] title={title[:80]}", flush=True)
            print(f"[2] video links={video_links}, photo links={photo_links}", flush=True)
            await page.screenshot(path="/tmp/pexels_guest_final.png")

            if video_links >= 3 or photo_links >= 3:
                print("\nSONUC: GUEST ERISIM CALISIYOR — Pexels cookiesiz de arama yapabiliyor", flush=True)
                return 0
            else:
                body = (await page.inner_text("body"))[:500]
                print(f"SONUC: GUEST erisim basarisiz (yeterli sonuc yok). body[:500]={body!r}",
                      file=sys.stderr)
                return 1
        finally:
            await ctx.close()
            await browser.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
