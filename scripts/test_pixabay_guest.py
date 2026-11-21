#!/usr/bin/env python3
"""Pixabay'in misafir (cookiesiz) erisilebilir olup olmadigini Playwright ile test eder."""
import asyncio, sys
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
            print("[1] pixabay.com videos/search/ sayfasina gidiliyor (guest)...", flush=True)
            resp = await page.goto("https://pixabay.com/videos/search/nature/",
                                   wait_until="domcontentloaded", timeout=60000)
            print(f"[1] HTTP status: {resp.status if resp else None}", flush=True)
            await page.wait_for_timeout(8000)

            # CF kontrolu
            for _ in range(8):
                body = (await page.inner_text("body"))[:500]
                if "Verify you are human" not in body and "Just a moment" not in body \
                        and "Performing security" not in body:
                    break
                await page.wait_for_timeout(5000)

            await page.wait_for_timeout(3000)
            video_links = await page.locator("a[href*='/videos/']").count()
            title = await page.title()
            print(f"[2] title={title[:100]}", flush=True)
            print(f"[2] video links={video_links}", flush=True)
            await page.screenshot(path="/tmp/pixabay_guest_final.png")

            if video_links >= 5:
                print("\nSONUC: PIXABAY GUEST ERISIM CALISIYOR", flush=True)
                return 0
            else:
                body = (await page.inner_text("body"))[:500]
                print(f"SONUC: guest erisim basarisiz. body={body[:200]!r}", file=sys.stderr)
                return 1
        finally:
            await ctx.close()
            await browser.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
