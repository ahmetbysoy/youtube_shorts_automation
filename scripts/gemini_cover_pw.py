#!/usr/bin/env python3
"""Playwright ile Gemini Web UI'dan kapak uretir (batchexecute 400 bypass).

2026-11-22 teshisi: Google, gemini_webapi 2.1.1 kutuphanesinin gonderdigi tum
batchexecute POST'larina HTTP 400 donuyor (yanit govdesi: er/400, e=4,138 —
istek formati reddi). GET/app + SNlM0e token ise 0.2sn'de basarili. Yani cookie,
ag ve oturum saglam; kutuphanenin POST serilestirmesi eski kalmis.

Cozum: gercek tarayiciyi kullan — refresh_gemini_cookie.py'in kanitlanan yolu
(CI'da oturum acar, mesaj gonderir, cevap alir). Bu adapter ayni uretim formatini
korur: kapak_gemini.json'daki prompt + '\n\nVideo basligi: <title>'.

Kullanim: python3 gemini_cover_pw.py <out_path> <video_baslik> [--prompt "<ozel prompt>"]
JPEG olarak out_path'e yazar; hata olursa non-zero exit.
"""
from __future__ import annotations

import asyncio, glob, json, os, re, shutil, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CFG_PATH = REPO / 'kapak_gemini.json'

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

# 2026-11-23 kapak denetimi (kullanici canli ekran goruntusu): Gemini'ye giden
# promptta "metin yazma" kisiti yokken AI gorselin ICINE clickbait yazilar
# pisiyordu ("DEKOR KIRAN... ANILAR!", "MUTLAKA IZLE! 100% GERCEK", "SOK!").
# generate_fallback_thumbnail.py ardindan USTUNE ikinci basligi cizince iki metin
# ust uste biniyor -> kanal gridinde okunmaz kapak. Artik her prompta metin
# yasagi eklenir; gorunur metni compositor tek katman olarak ekler.
NO_TEXT_SUFFIX = (
    "\n\nKATEGORIK KURAL: Uretecegin gorselde HICBIR yazi, harf, sayi, logo, "
    "filigran, ok, rozet, badge, cerceve, kolaj veya bolunmus ekran OLMASIN. "
    "Metni SEN yazma; baslik metnini sistem ayrica guvenli bir katman olarak "
    "ekliyor, sen yazarsan iki metin ust uste biner. Sadece tek net, buyuk, "
    "ortada, taninabilir bir gorsel konu üret."
)

# Butce: embed_cover_frame.py'in 240s subprocess siniri icinde kalmali.
PAGE_LOAD_TIMEOUT_S = int(os.environ.get('GEMINI_PW_LOAD_TIMEOUT_S', '45'))
IMAGE_WAIT_TIMEOUT_S = int(os.environ.get('GEMINI_PW_IMG_TIMEOUT_S', '120'))
DOWNLOAD_TIMEOUT_S = int(os.environ.get('GEMINI_PW_DL_TIMEOUT_S', '15'))
MIN_IMAGE_PX = int(os.environ.get('GEMINI_PW_MIN_IMG_PX', '400'))
MIN_OUT_BYTES = int(os.environ.get('GEMINI_PW_MIN_OUT_BYTES', '20000'))


def log(msg: str) -> None:
    print(f'[KAPAK-PW] {msg}', file=sys.stderr, flush=True)


def load_cookies() -> dict:
    raw = os.environ.get('GEMINI_COOKIES_JSON') or os.environ.get('GEMINI_COOK')
    if raw:
        return json.loads(raw)
    local = REPO / 'jeton' / 'gemini_cookies.json'
    if local.exists():
        return json.loads(local.read_text('utf8'))
    raise SystemExit('HATA: GEMINI_COOKIES_JSON / GEMINI_COOK env yok ve jeton/gemini_cookies.json yok')


def load_storage_state() -> Path | None:
    """Tam Google oturum state'i bul: env GEMINI_STORAGE_STATE > workspace storage_state.json > cookies.json.

    refresh_gemini_cookie.py kanitlar: yalnizca PSID+PSIDTS cookie enjeksiyonu
    gemini.google.com'da oturum ACMAZ (accounts.google.com sign-in'e yonlenir);
    tam YouTube storage_state (SID/HSID/SSID/SAPISID/... .google.com cookie'leri)
    ise gercek oturum acar. Daily pipeline calisma dizininde cookies.json ve
    (varsa) storage_state.json yazar; probe workflow'u secrets'tan yazar.
    """
    raw = (os.environ.get('GEMINI_STORAGE_STATE') or '').strip()
    if raw:
        p = Path('/tmp/yt_storage_state_pw.json')
        p.write_text(raw, encoding='utf8')
        return p
    for name in ('storage_state.json', 'cookies.json'):
        p = REPO / name
        if p.exists() and p.stat().st_size > 50:
            return p
    return None


def _as_playwright_state(path: Path) -> dict | None:
    """storage_state.json (dict) veya cookies.json (liste) -> Playwright storage_state dict."""
    try:
        d = json.loads(path.read_text('utf8'))
    except Exception:
        return None
    if isinstance(d, dict) and isinstance(d.get('cookies'), list) and d['cookies']:
        return {'cookies': d['cookies'], 'origins': d.get('origins', [])}
    if isinstance(d, list) and d:
        return {'cookies': d, 'origins': []}
    return None


def load_default_prompt() -> str:
    return json.loads(CFG_PATH.read_text('utf8')).get('prompt', '')


# Sayfada buyuk img'leri tarayan JS (avatar/logo kucuk oldugu icin elenir)
_COLLECT_IMGS_JS = """
() => Array.from(document.querySelectorAll('img'))
  .filter(i => i.naturalWidth >= %d && i.naturalHeight >= %d)
  .map(i => ({ src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight }))
""" % (MIN_IMAGE_PX, MIN_IMAGE_PX)


def _upgrade_url(url: str) -> str | None:
    """googleusercontent boyut sonekini buyuk formata cevirir (=w1024-h1024 gibi)."""
    if 'googleusercontent.com' not in url:
        return None
    if re.search(r'=w\d+-h\d+', url):
        return re.sub(r'=w\d+-h\d+[^=]*$', '=w2048-h2048', url)
    if not url.endswith('=s0') and re.search(r'=s\d+$', url):
        return re.sub(r'=s\d+$', '=s2048', url)
    return None


async def _fetch_blob(page, src: str) -> bytes | None:
    # blob URL'ler ureten dokumanin context'ine ozgudur — Gemini cevabi iframe
    # icinde olabildigi icin TUM frame'lerde denenir
    for frame in page.frames:
        try:
            arr = await frame.evaluate(
                """async (src) => {
                    const r = await fetch(src);
                    if (!r.ok) return null;
                    const buf = await r.arrayBuffer();
                    return Array.from(new Uint8Array(buf));
                }""", src)
            if arr:
                return bytes(arr)
        except Exception as e:
            log(f"blob fetch ({frame.url[:50]}) atlandi: {type(e).__name__}")
    return None


async def _fetch_via_canvas(page, src: str) -> bytes | None:
    """img elementini bulup ayni dokumanda canvas'a cizer, PNG dataURL dondurur.

    blob fetch basarisiz olursa (CORS/origin) son care; ayni-origin blob'ta
    canvas temiz kalir.
    """
    import base64
    for frame in page.frames:
        try:
            b64 = await frame.evaluate(
                """async (src) => {
                    const img = [...document.querySelectorAll('img')]
                        .find(i => (i.currentSrc || i.src) === src);
                    if (!img || !img.naturalWidth) return null;
                    const c = document.createElement('canvas');
                    c.width = img.naturalWidth;
                    c.height = img.naturalHeight;
                    c.getContext('2d').drawImage(img, 0, 0);
                    return c.toDataURL('image/png');
                }""", src)
            if b64 and b64.startswith('data:image'):
                return base64.b64decode(b64.split(',', 1)[1])
        except Exception:
            continue
    return None


async def _fetch_https(context, url: str) -> bytes | None:
    try:
        resp = await context.request.get(url, timeout=DOWNLOAD_TIMEOUT_S * 1000)
        if resp.status != 200:
            log(f"https fetch {resp.status}: {url[:120]}")
            return None
        return resp.body()
    except Exception as e:
        log(f"https fetch hatasi: {type(e).__name__}: {str(e)[:120]}")
        return None


async def generate(out_path: str, title: str, prompt_override: str | None = None) -> None:
    started = time.monotonic()
    from playwright.async_api import async_playwright

    cookies = load_cookies()
    if prompt_override:
        prompt = prompt_override + NO_TEXT_SUFFIX
    else:
        prompt = load_default_prompt() + NO_TEXT_SUFFIX + '\n\nVideo basligi: ' + title
    log(f"prompt hazir ({len(prompt)} karakter, metin-yasagi+baslik formati)")

    psid = cookies.get('__Secure-1PSID', '')
    psidts = cookies.get('__Secure-1PSIDTS', '')
    if len(psid) < 20:
        raise SystemExit('HATA: cookie __Secure-1PSID eksik/kisa')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])

        # Tam oturum state'i varsa onunla ac (kanitlanmis yol), yoksa bare cookie
        ss_path = load_storage_state()
        state = _as_playwright_state(ss_path) if ss_path else None
        if state:
            log(f"tam storage state kullaniliyor: {ss_path.name} "
                f"({len(state['cookies'])} cookie)")
            context = await browser.new_context(
                storage_state=state, user_agent=USER_AGENT, locale='tr-TR',
                viewport={'width': 1280, 'height': 800})
        else:
            log('UYARI: tam storage state yok — yalnizca PSID/PSIDTS deneniyor '
                '(buyuk olasilikla accounts.google.com sign-in yonlendirmesi olacaktir)')
            context = await browser.new_context(
                user_agent=USER_AGENT, locale='tr-TR',
                viewport={'width': 1280, 'height': 800})
            base_cookie = {
                'domain': '.google.com', 'path': '/', 'secure': True,
                'sameSite': 'Lax', 'httpOnly': False,
            }
            await context.add_cookies([
                {**base_cookie, 'name': '__Secure-1PSID', 'value': psid},
                {**base_cookie, 'name': '__Secure-1PSIDTS', 'value': psidts},
            ])
        page = await context.new_page()

        # SSO isinma: accounts.google.com'a kisa ugra (refresh script'in yolu —
        # oturum cookie'lerini canlandirir), ardindan Gemini app
        try:
            await page.goto('https://accounts.google.com/',
                            wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            log(f"SSO isinma atlandi: {type(e).__name__}")

        # 1) Gemini app acilisi + oturum kaniti
        try:
            await page.goto('https://gemini.google.com/app',
                            wait_until='domcontentloaded',
                            timeout=PAGE_LOAD_TIMEOUT_S * 1000)
        except Exception as e:
            await context.close()
            await browser.close()
            raise SystemExit(f'HATA: gemini.google.com acilamadi: {type(e).__name__}')
        await page.wait_for_timeout(5000)
        log(f"sayfa acildi: {page.url[:80]} ({time.monotonic() - started:.0f}sn)")

        session_ok = False
        for proof_sel, proof_label in [
            ("text=Yeni sohbet", "Yeni sohbet menusu"),
            ("text=Nereden başlayalım", "karsilama ekrani"),
            ("a[aria-label*='Google Account']", "Google Account linki"),
            ("[data-test-id='profile-avatar']", "profil avatar"),
        ]:
            try:
                el = page.locator(proof_sel).first
                if await el.is_visible(timeout=3000):
                    log(f"oturum kanitlandi: {proof_label}")
                    session_ok = True
                    break
            except Exception:
                continue
        if not session_ok:
            await page.screenshot(path='/tmp/gemini_cover_pw_no_session.png')
            await context.close()
            await browser.close()
            raise SystemExit('HATA: oturum kanitlanamadi (cookie gecersiz olabilir) — screenshot /tmp/gemini_cover_pw_no_session.png')

        # 2) Textbox bul — deadline'li poll (UI hidrasyonu gecikme yapabilir)
        ta = None
        tb_deadline = time.monotonic() + 30
        tb_selectors = ["div[contenteditable='true']", ".text-input-field_textarea",
                        "rich-textarea", "textarea"]
        while time.monotonic() < tb_deadline and ta is None:
            for sel in tb_selectors:
                try:
                    cand = page.locator(sel).first
                    if await cand.is_visible(timeout=2500):
                        ta = cand
                        break
                except Exception:
                    continue
            if ta is None:
                await page.wait_for_timeout(2000)
        if ta is None:
            await page.screenshot(path='/tmp/gemini_cover_pw_no_textbox.png')
            await context.close()
            await browser.close()
            raise SystemExit('HATA: gemini mesaj kutusu bulunamadi (30sn) — screenshot /tmp/gemini_cover_pw_no_textbox.png')
        await ta.click(force=True, timeout=5000)
        await page.wait_for_timeout(400)

        # 3) Gonderim ONCESI mevcut buyuk img'leri isaretle (yenisi aranacak)
        try:
            before = {i['src'] for i in await page.evaluate(_COLLECT_IMGS_JS)}
        except Exception:
            before = set()

        # 4) Baslik+prompt'u yaz ve gonder (uretim formati birebir)
        await ta.type(prompt, delay=8)
        await page.wait_for_timeout(500)
        await page.keyboard.press('Enter')
        log(f"prompt gonderildi ({time.monotonic() - started:.0f}sn) — gorsel bekleniyor")

        # 5) Yeni buyuk img bekle (Gemini 2.x cevabinin icinde gorsel doner)
        found = None
        deadline = time.monotonic() + IMAGE_WAIT_TIMEOUT_S
        while time.monotonic() < deadline:
            await page.wait_for_timeout(2000)
            try:
                imgs = await page.evaluate(_COLLECT_IMGS_JS)
            except Exception:
                imgs = []
            fresh = [i for i in imgs if i['src'] not in before]
            if fresh:
                # en buyuk naturalWidth'li yeni gorsel
                found = max(fresh, key=lambda i: i['w'])
                log(f"gorsel bulundu: {found['w']}x{found['h']} "
                    f"({time.monotonic() - started:.0f}sn) src={found['src'][:90]}")
                break
        if found is None:
            await page.screenshot(path='/tmp/gemini_cover_pw_no_image.png')
            await context.close()
            await browser.close()
            raise SystemExit(f'HATA: {IMAGE_WAIT_TIMEOUT_S}sn icinde gorsel uretilmedi (screenshot /tmp/gemini_cover_pw_no_image.png)')

        # 6) Gorseli indir: blob (tum frame'ler) -> canvas fallback -> buyuk URL -> orijinal src
        src = found['src']
        data = None
        if src.startswith('blob:'):
            data = await _fetch_blob(page, src)
            if data is None:
                log("blob fetch tum framelerde basarisiz — canvas fallback denenecek")
                data = await _fetch_via_canvas(page, src)
                if data:
                    log(f"canvas fallback calisti ({len(data)} byte)")
        else:
            up = _upgrade_url(src)
            if up:
                data = await _fetch_https(context, up)
                if data and len(data) < 30000:
                    data = None  # buyuk istek 400/dusuk donduyse orijinale dus
            if data is None:
                data = await _fetch_https(context, src)
        if not data or len(data) < 5000:
            # son care: canvas'i dene (non-blob icin de)
            data = await _fetch_via_canvas(page, src)
        if not data or len(data) < 5000:
            await context.close()
            await browser.close()
            raise SystemExit('HATA: gorsel indirilemedi (blob+canvas+https yollari basarisiz)')

        # 7) JPEG olarak yaz (uretim akisiyla ayni: RGB + quality 94)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        tmp_raw = str(out_path) + '.raw'
        Path(tmp_raw).write_bytes(data)
        try:
            from PIL import Image
            with Image.open(tmp_raw) as im:
                w, h = im.size
                im.convert('RGB').save(out_path, 'JPEG', quality=94)
            Path(tmp_raw).unlink(missing_ok=True)
            log(f"JPEG yazildi: {w}x{h}")
        except Exception:
            shutil.move(tmp_raw, out_path)  # zaten jpeg olabilir
        sz = Path(out_path).stat().st_size
        if sz < MIN_OUT_BYTES:
            raise SystemExit(f'HATA: cikti cok kucuk ({sz} byte)')
        print(f'KAPAK_OK(PW): {out_path} ({sz} byte, {time.monotonic() - started:.0f}sn)',
              file=sys.stderr)

        await context.close()
        await browser.close()


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('out_path', help='cikti JPEG yolu')
    ap.add_argument('title', help='video basligi')
    ap.add_argument('--prompt', default=None, help='ozel prompt (varsayilanin yerine gecer)')
    args = ap.parse_args()
    asyncio.run(generate(args.out_path, args.title, args.prompt))


if __name__ == '__main__':
    main()
