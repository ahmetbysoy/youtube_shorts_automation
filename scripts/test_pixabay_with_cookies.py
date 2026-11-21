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

    headless = not bool(os.environ.get("DISPLAY"))
    print(f"[1b] Chromium headless={headless} (DISPLAY={os.environ.get('DISPLAY','')})", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled",
                  "--start-maximized"],
        )
        ctx = await browser.new_context(
            locale="en-US",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        await ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>false});
            Object.defineProperty(navigator,'languages',{get:()=>['en-US','en','tr']});
            window.chrome = { runtime: {} };
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        if cookies:
            await ctx.add_cookies(cookies)

        page = await ctx.new_page()
        try:
            print("\n[2] pixabay.com ana sayfaya gidiliyor (CF isinlamasi icin)", flush=True)
            resp = await page.goto("https://pixabay.com/",
                                   wait_until="domcontentloaded", timeout=60000)
            print(f"[2] HTTP: {resp.status if resp else None}", flush=True)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/pixabay_home.png")

            # CF checkbox'ini iframe shadow DOM icinde bulup tikla
            cf_passed = False
            for attempt in range(15):
                body = ""
                try:
                    body = (await page.inner_text("body", timeout=2000))[:500]
                except Exception:
                    pass
                if "Performing security verification" not in body and "Just a moment" not in body \
                        and "Verify you are human" not in body and "Attention Required" not in body:
                    print(f"[cf] deneme {attempt+1}: gecti!", flush=True)
                    cf_passed = True
                    break

                print(f"[cf] deneme {attempt+1}: checkbox araniyor...", flush=True)
                clicked = False
                # Tüm frame'leri dolas
                for fr_idx, frame in enumerate(page.frames):
                    try:
                        # Farkli seciciler ile checkbox/label/input dene
                        for sel in [
                            "input[type='checkbox']",
                            "label",
                            "span[class*='checkbox']",
                            "div[role='checkbox']",
                            "[id*='cf']",
                            "[class*='ctp']",
                            "iframe",
                            "body *",
                        ]:
                            try:
                                loc = frame.locator(sel)
                                cnt = await loc.count()
                                for i in range(min(cnt, 10)):
                                    el = loc.nth(i)
                                    if not await el.is_visible(timeout=500):
                                        continue
                                    bbox = await el.bounding_box()
                                    if not bbox: continue
                                    txt = ""
                                    try:
                                        txt = (await el.inner_text(timeout=200))[:50]
                                    except Exception:
                                        pass
                                    # Checkbox veya "Verify" iceren eleman
                                    if "Verify" in txt or sel == "input[type='checkbox']" \
                                            or (bbox['width'] > 20 and bbox['height'] > 20
                                                and bbox['width'] < 80 and bbox['height'] < 80):
                                        print(f"[cf] frame{fr_idx} sel={sel} i={i} bbox={bbox} txt={txt!r}",
                                              flush=True)
                                        # Once human-benzeri mouse hareketi ile uzerine gel
                                        await page.mouse.move(
                                            bbox['x'] + bbox['width']/2,
                                            bbox['y'] + bbox['height']/2,
                                            steps=15,
                                        )
                                        await page.wait_for_timeout(200)
                                        await el.click(force=True, timeout=3000)
                                        clicked = True
                                        await page.wait_for_timeout(4000)
                                        break
                            except Exception as e:
                                continue
                            if clicked: break
                    except Exception:
                        continue
                    if clicked:
                        break

                # Dogrudan JavaScript ile shadow DOM icine ulasmayi dene
                if not clicked:
                    try:
                        clicked = await page.evaluate("""() => {
                            // iframe'leri bul
                            const iframes = document.querySelectorAll('iframe');
                            for (const iframe of iframes) {
                                try {
                                    const doc = iframe.contentDocument || iframe.contentWindow.document;
                                    // Turnstile checkbox
                                    const cb = doc.querySelector('input[type=\"checkbox\"], label, span.mark, div.cb-i, div[role=\"checkbox\"]');
                                    if (cb) { cb.click(); return true; }
                                    // Shadow root
                                    const host = doc.querySelector('*');
                                } catch(e) {}
                            }
                            // Ana sayfadaki checkbox
                            const cb = document.querySelector('label, input[type=\"checkbox\"], div[role=\"checkbox\"], span[class*=\"checkbox\"]');
                            if (cb) { cb.click(); return true; }
                            return false;
                        }""")
                        print(f"[cf] JS click denemesi: {clicked}", flush=True)
                        if clicked:
                            await page.wait_for_timeout(5000)
                    except Exception as e:
                        print(f"[cf] JS click hatasi: {e}", flush=True)

                await page.wait_for_timeout(3000)
                await page.screenshot(path=f"/tmp/pixabay_cf_{attempt}.png")

            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/pixabay_after_cf.png")
            print(f"[cf] sonuc: cf_passed={cf_passed}", flush=True)

            # Simdi videos/search sayfasina git
            print("\n[3] videos/search/nature/ sayfasina geciliyor...", flush=True)
            resp = await page.goto("https://pixabay.com/videos/search/nature/",
                                   wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(8000)
            # Kisa CF tekrar bekle
            for _ in range(6):
                try:
                    body = (await page.inner_text("body", timeout=2000))[:300]
                    if "Just a moment" not in body and "Performing security" not in body:
                        break
                except Exception:
                    pass
                await page.wait_for_timeout(4000)
            await page.wait_for_timeout(3000)

            title = await page.title()
            cur = page.url
            video_links = await page.locator("a[href*='/videos/']").count()
            body = await page.inner_text("body")
            logged_in = any(kw in body for kw in
                            ["Log out", "Logout", "Upload ", "My account", "My Pixabay",
                             "Bookmarks", "Following"])
            print(f"[4] URL: {cur[:100]}", flush=True)
            print(f"[4] Title: {title[:100]}", flush=True)
            print(f"[4] video_links: {video_links}", flush=True)
            print(f"[4] logged_in: {logged_in}", flush=True)
            await page.screenshot(path="/tmp/pixabay_cookie_test.png")

            if video_links >= 5 and "Just a moment" not in title:
                print("\nSONUC: ✅ PIXABAY_COOK CALISIYOR", flush=True)
                return 0
            else:
                print(f"\nSONUC: ❌ Calismiyor (video_links={video_links}, title={title})",
                      file=sys.stderr)
                # Cookie'leri kaydet (cf_clearance yenilendiyse)
                fresh = await ctx.cookies()
                fresh_pix = [c for c in fresh if "pixabay" in c.get("domain","")]
                Path("/tmp/fresh_pix_cookies.json").write_text(json.dumps(fresh_pix, indent=2))
                print(f"[sonuc] {len(fresh_pix)} pixabay cookie'si kaydedildi (/tmp/fresh_pix_cookies.json)",
                      flush=True)
                return 1
        finally:
            await ctx.close()
            await browser.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
