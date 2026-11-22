#!/usr/bin/env python3
"""Playwright ile Gemini Web UI'dan METIN uretir (batchexecute 400 bypass).

2026-11-22 kapak teshisiyle ayni kok: Google, gemini_webapi 2.1.1'in tum
batchexecute POST'larina HTTP 400 donuyor; GET/app + SNlM0e ve gercek tarayici
akisi ise saglam. Kapak icin kanitlanan Playwright yolu (gemini_cover_pw.py)
metin uretimine tasindi: ayni oturum (tam storage_state), ayni textbox/gonderim
mekanigi — gorsel bekleme yerine yanit metni KARARLILIK takibi.

Transport-only arac: prompt'u dosyadan okur, ham yanit metnini dosyaya yazar.
Konu secimi/research/JSON dogrulama gemini_web_text_probe katmaninda kalir
(ayni validator zinciri: validate_grounded_response).

Kullanim:
  python3 gemini_story_pw.py --prompt-file /tmp/p.txt --out /tmp/r.txt [--timeout 150]
Basari: stderr'de STORY_OK(PW) ve exit 0. Hata: STORY_FAIL(...) ve non-zero exit.
"""
from __future__ import annotations

import asyncio, json, os, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

PAGE_LOAD_TIMEOUT_S = int(os.environ.get('GEMINI_PW_LOAD_TIMEOUT_S', '45'))
MIN_RESPONSE_CHARS = int(os.environ.get('GEMINI_PW_MIN_CHARS', '30'))
STABLE_POLLS = int(os.environ.get('GEMINI_PW_STABLE_POLLS', '4'))  # 4x2sn = 8sn kararli


def log(msg: str) -> None:
    print(f'[STORY-PW] {msg}', file=sys.stderr, flush=True)


# kapak adapter ile ayni oturum yukleyiciler (tek kaynak dogruluk)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gemini_cover_pw import (  # noqa: E402
    load_cookies, load_storage_state, _as_playwright_state,
)

# Tum frame'lerdeki SON model yanitinin metnini toplar (kullanici mesaji degil).
# once bilinen seciciler, sonra genel '[class*=response]' fallback'i — Gemini DOM'u
# surekli degistigi icin tek seciciye bagli kalmamak gerekir (run 45034450228 dersleri)
_EXTRACT_JS = """
() => {
  const sels = ['model-response', '.model-response-text',
                '.response-container-content', '[data-test-id="model-response-text"]',
                'message-content'];
  const roots = [document];
  for (const f of document.querySelectorAll('iframe')) {
    try { if (f.contentDocument) roots.push(f.contentDocument); } catch (e) {}
  }
  const pick = (root, sel) => {
    const nodes = root.querySelectorAll(sel);
    for (let i = nodes.length - 1; i >= 0; i--) {
      const t = (nodes[i].innerText || '').trim();
      if (t) return t;
    }
    return '';
  };
  for (const root of roots) {
    for (const sel of sels) {
      const t = pick(root, sel);
      if (t) return t;
    }
    const t2 = pick(root, '[class*="response"]');
    if (t2) return t2;
  }
  return '';
}
"""

# Kullanicinin gonderdigi mesaj gercekten sohbete dustu mu?
_SENT_JS = """
() => {
  const roots = [document];
  for (const f of document.querySelectorAll('iframe')) {
    try { if (f.contentDocument) roots.push(f.contentDocument); } catch (e) {}
  }
  for (const root of roots) {
    if (root.querySelectorAll('user-query, [class*="user-query"]').length) return true;
  }
  return false;
}
"""


def is_response_stable(samples: list[str]) -> bool:
    """Son N ornegin tumu bos degil ve birbirine esit ise yanit kararli sayilir.

    Saf fonksiyon — offline birim testiyle dogrulanir.
    """
    if len(samples) < STABLE_POLLS:
        return False
    window = samples[-STABLE_POLLS:]
    return all(len(s) >= MIN_RESPONSE_CHARS for s in window) and len(set(window)) == 1


def _walk_strings(node) -> iter:
    """Ic ice JSON yapilarindaki tum string degerleri soldan saga verir."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)


def find_story_text(bodies: list[str]) -> str:
    """Yakalanan batchexecute govdelerinden model yanit metnini cikarar.

    batchexecute satirlari 'uzunluk[JSON,...]' bicimindedir; her satir json.loads
    edilip icindeki string'lerde story JSON isaretci ('script_text') aranan en
    uzun aday dondurulur. Saf fonksiyon — offline test edilebilir.
    """
    best = ''
    for body in bodies:
        cleaned = (body or '').strip()
        if cleaned.startswith(")]}'"):
            cleaned = cleaned[4:].strip()
        for raw_line in cleaned.split('\n'):
            line = raw_line.strip()
            if not line or not line[0].isdigit():
                continue
            bracket = line.find('[')
            if bracket == -1:
                continue
            try:
                data = json.loads(line[bracket:])
            except Exception:
                continue
            for s in _walk_strings(data):
                if 'script_text' in s and len(s) > len(best):
                    best = s
    return best


async def generate(out_path: str, prompt: str, budget_s: int) -> None:
    started = time.monotonic()
    from playwright.async_api import async_playwright

    if not prompt.strip():
        raise SystemExit('STORY_FAIL(bos prompt)')
    log(f"prompt hazir ({len(prompt)} karakter)")

    cookies = load_cookies()
    psid = cookies.get('__Secure-1PSID', '')
    if len(psid) < 20:
        raise SystemExit('STORY_FAIL(cookie __Secure-1PSID eksik/kisa)')

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])

        ss_path = load_storage_state()
        state = _as_playwright_state(ss_path) if ss_path else None
        if state:
            log(f"tam storage state kullaniliyor: {ss_path.name} ({len(state['cookies'])} cookie)")
            context = await browser.new_context(
                storage_state=state, user_agent=USER_AGENT, locale='tr-TR',
                viewport={'width': 1280, 'height': 800})
        else:
            log('UYARI: tam storage state yok — yalnizca PSID/PSIDTS deneniyor')
            context = await browser.new_context(
                user_agent=USER_AGENT, locale='tr-TR',
                viewport={'width': 1280, 'height': 800})
            psidts = cookies.get('__Secure-1PSIDTS', '')
            base_cookie = {'domain': '.google.com', 'path': '/', 'secure': True,
                           'sameSite': 'Lax', 'httpOnly': False}
            await context.add_cookies([
                {**base_cookie, 'name': '__Secure-1PSID', 'value': psid},
                {**base_cookie, 'name': '__Secure-1PSIDTS', 'value': psidts},
            ])
        page = await context.new_page()

        # Ag yakalama: tarayicinin KENDI batchexecute yanitlari calisiyor (UI saglam);
        # DOM extraction basarisizsa model metni bu govdelerden kurtaririz.
        captured: list[str] = []

        async def _capture(resp) -> None:
            try:
                if 'batchexecute' in resp.url and resp.request.method == 'POST':
                    body = await resp.text()
                    if body:
                        captured.append(body)
            except Exception:
                pass

        page.on('response', lambda r: asyncio.ensure_future(_capture(r)))

        try:
            await page.goto('https://accounts.google.com/',
                            wait_until='domcontentloaded', timeout=20000)
            await page.wait_for_timeout(2000)
        except Exception as e:
            log(f"SSO isinma atlandi: {type(e).__name__}")

        try:
            await page.goto('https://gemini.google.com/app',
                            wait_until='domcontentloaded',
                            timeout=PAGE_LOAD_TIMEOUT_S * 1000)
        except Exception as e:
            raise SystemExit(f'STORY_FAIL(gemini.google.com acilamadi: {type(e).__name__})')
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
            await page.screenshot(path='/tmp/gemini_story_pw_no_session.png')
            raise SystemExit('STORY_FAIL(oturum kanitlanamadi) — screenshot /tmp/gemini_story_pw_no_session.png')

        # Textbox: deadline'li poll (kapak adapter ile ayni)
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
            await page.screenshot(path='/tmp/gemini_story_pw_no_textbox.png')
            raise SystemExit('STORY_FAIL(mesaj kutusu bulunamadi)')

        await ta.click(force=True, timeout=5000)
        await page.wait_for_timeout(400)

        # Uzun prompt icin fill() (hizli); gonderim dogrulanir, dusmezse type() fallback.
        # Kanit (run 45034450228): fill+Enter bazen sessizce yutuluyor — dogrulama sart.
        async def _sent() -> bool:
            try:
                return bool(await page.evaluate(_SENT_JS))
            except Exception:
                return False

        async def _try_send(how: str) -> bool:
            if how == 'fill':
                await ta.fill(prompt, timeout=8000)
            else:
                await ta.click(force=True, timeout=5000)
                await ta.type(prompt, delay=2)
            await page.wait_for_timeout(500)
            await page.keyboard.press('Enter')
            for _ in range(4):
                await page.wait_for_timeout(1500)
                if await _sent():
                    return True
            # Enter yutulduysa bir kez daha dene
            await page.keyboard.press('Enter')
            for _ in range(3):
                await page.wait_for_timeout(1500)
                if await _sent():
                    return True
            return False

        if not await _try_send('fill'):
            log("fill ile gonderim alinmadi — type(delay=2) fallback")
            if not await _try_send('type'):
                await page.screenshot(path='/tmp/gemini_story_pw_no_send.png')
                raise SystemExit('STORY_FAIL(prompt gonderilemedi) — screenshot /tmp/gemini_story_pw_no_send.png')
        log(f"prompt gonderildi, sohbete dustu ({time.monotonic() - started:.0f}sn) — yanit bekleniyor")

        # Yanit metni kararliylik takibi: son model-response metni N ornegin ayni olmali
        samples: list[str] = []
        deadline = time.monotonic() + budget_s
        response_text = ''
        while time.monotonic() < deadline:
            await page.wait_for_timeout(2000)
            try:
                text = await page.evaluate(_EXTRACT_JS)
            except Exception:
                text = ''
            if text:
                samples.append(text)
                if is_response_stable(samples):
                    response_text = samples[-1]
                    log(f"yanit kararli: {len(response_text)} karakter "
                        f"({time.monotonic() - started:.0f}sn)")
                    break
        await context.close()
        await browser.close()

        if not response_text:
            # DOM extraction basarisiz — ag yakalamasindan kurtarmayi dene
            recovered = find_story_text(captured)
            if recovered.strip():
                response_text = recovered
                log(f"ag yakalamasindan kurtarildi: {len(response_text)} karakter "
                    f"({len(captured)} govde tarandi)")
        if not response_text:
            diag = (f"({budget_s}sn icinde kararli yanit yok; son_ornek={len(samples)}; "
                    f"yakalanan_govde={len(captured)}")
            raise SystemExit(f'STORY_FAIL{diag})')

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(response_text, encoding='utf8')
        print(f'STORY_OK(PW): {out_path} ({len(response_text)} karakter, '
              f'{time.monotonic() - started:.0f}sn)', file=sys.stderr)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--prompt-file', required=True, help='prompt metni iceren dosya')
    ap.add_argument('--out', required=True, help='yanit metninin yazilacagi dosya')
    ap.add_argument('--timeout', type=int,
                    default=int(os.environ.get('GEMINI_PW_TEXT_TIMEOUT_S', '150')))
    args = ap.parse_args()
    pf = Path(args.prompt_file)
    if not pf.exists():
        raise SystemExit('STORY_FAIL(prompt dosyasi yok)')
    prompt = pf.read_text('utf8')
    asyncio.run(generate(args.out, prompt, args.timeout))


if __name__ == '__main__':
    main()
