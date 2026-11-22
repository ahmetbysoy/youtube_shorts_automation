#!/usr/bin/env python3
"""Tek bir video icin Gemini web'den kapak uret.
Kullanim: python3 gemini_cover.py <out_path> <video_baslik> [--prompt "<ozel prompt>"]
JPEG olarak out_path'e yazar. Hata olursa non-zero exit.
--prompt verilirse kapak_gemini.json'daki varsayilan prompt yerine onu kullanir.
"""
import asyncio, json, os, sys, glob, shutil, argparse, time
from pathlib import Path
from gemini_webapi import GeminiClient

REPO = Path(__file__).resolve().parent.parent
CFG_PATH = REPO / 'kapak_gemini.json'

def load_cookies():
    raw = os.environ.get('GEMINI_COOKIES_JSON') or os.environ.get('GEMINI_COOK')
    if raw:
        return json.loads(raw)
    local = REPO / 'jeton' / 'gemini_cookies.json'
    if local.exists():
        return json.loads(local.read_text('utf8'))
    raise SystemExit('HATA: GEMINI_COOKIES_JSON / GEMINI_COOK env yok ve jeton/gemini_cookies.json yok')

def load_default_prompt():
    return json.loads(CFG_PATH.read_text('utf8')).get('prompt','')

# Faz4L: Gemini web gorsel uretimi bazen 2+ dk sürüyor veya tek istekte
# timeout'a düşüyor. Burada sinirli retry/backoff uygulanır; toplam kötü durum
# süresi embed_cover_frame.py'daki 240s subprocess bütçesinin altında kalır.
# 2026-11-21 23:52 kosusu kanıtı: init 45sn hard-cap'siz bırakılınca kütüphane
# iç retry'lar toplam 240s dış bütçeyi tüketti (dış kill → 35s boşa). init
# asyncio.wait_for ile hard-cap'lenir + üretim 65sn: 45+65+10+65 = 185s < 240s.
GEN_TIMEOUT_S = int(os.environ.get('GEMINI_GEN_TIMEOUT_S', '65'))
INIT_TIMEOUT_S = int(os.environ.get('GEMINI_COVER_INIT_TIMEOUT_S', '45'))
COVER_ATTEMPTS = max(1, int(os.environ.get('GEMINI_COVER_ATTEMPTS', '2')))
COVER_BACKOFFS = (10, 20)
PW_BUDGET_S = int(os.environ.get('GEMINI_PW_BUDGET_S', '200'))

# 2026-11-22 teshisi: Google, kutuphanenin tum batchexecute POST'larina HTTP 400
# donuyor (yanit: er/400 + e=4,138 — istek formati reddi; GET/app + SNlM0e ise
# 0.2sn'de basarili). Cozum: once Playwright UI adapter'i (gemini_cover_pw.py,
# gercek tarayici = guncel sozlesme), sonra kutuphane fallback'i. Fallback'te
# _init_rpc telemetri RPC'leri bypass edilir (generate icin gereksiz; bu RPC'ler
# 400 alip ~30sn ic retry ile budget yakar).
PW_SCRIPT = Path(__file__).resolve().parent / 'gemini_cover_pw.py'


def _try_playwright(out_path: str, title: str, prompt_override: str | None) -> bool:
    if not PW_SCRIPT.exists():
        return False
    import subprocess
    cmd = [sys.executable, str(PW_SCRIPT), out_path, title]
    if prompt_override:
        cmd += ['--prompt', prompt_override]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=PW_BUDGET_S)
    except subprocess.TimeoutExpired:
        print(f'KAPAK-PW zamana asimi ({PW_BUDGET_S}s) — kutuphane fallback denenecek',
              file=sys.stderr, flush=True)
        return False
    if res.returncode == 0 and Path(out_path).exists() \
            and Path(out_path).stat().st_size > 20_000:
        tail = (res.stderr or '').strip().splitlines()
        print(f'KAPAK Playwright yolu ile uretildi: {tail[-1] if tail else "OK"}',
              file=sys.stderr, flush=True)
        return True
    err = (res.stderr or res.stdout or '').strip().replace('\n', ' ')[:300]
    print(f'KAPAK-PW basarisiz (cikis {res.returncode}): {err}', file=sys.stderr, flush=True)
    return False


async def generate(out_path: str, title: str, prompt_override: str | None = None):
    t_start = time.monotonic()
    # 1) Playwright adapter (birincil yol)
    if _try_playwright(out_path, title, prompt_override):
        return
    # 2) Kutuphane fallback — kalan butceyle sinirli deneme
    remaining = 235 - (time.monotonic() - t_start)
    gen_budget = min(GEN_TIMEOUT_S, 30)
    attempts = 1
    if remaining < 50:
        raise SystemExit('Gemini gorsel uretilemedi (Playwright yolu budceyi doldurdu)')
    print(f'KAPAK kutuphane fallback ({remaining:.0f}s kalan butce)', file=sys.stderr, flush=True)
    cookies = load_cookies()
    if prompt_override:
        prompt = prompt_override
    else:
        prompt = load_default_prompt() + '\n\nVideo basligi: ' + title
    client = GeminiClient(cookies.get('__Secure-1PSID',''), cookies.get('__Secure-1PSIDTS',''))
    # Telemetri RPC bypass: _init_rpc 400 alip ~30sn ic retry yapiyor; generate
    # icin gerekli degil (model=None -> hesap varsayilani). Init 0.2sn'e iner.
    client._init_rpc = lambda: asyncio.sleep(0)
    # auto_refresh=False + wait_for hard-cap: arka plan token yenileme görevi
    # bazen event loop'u kilitliyor (content tarafında da aynı nedenle False);
    # kütüphane iç timeout'ları toplam bütçeyi aşan iç retry'lara izin veriyor.
    await asyncio.wait_for(client.init(timeout=INIT_TIMEOUT_S, auto_refresh=False),
                           timeout=INIT_TIMEOUT_S)
    resp = None
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = await asyncio.wait_for(client.generate_content(prompt), timeout=gen_budget)
            if resp and resp.images:
                break
            last_err = RuntimeError('gemini_gorsel_dondurmedi')
            print(f'KAPAK deneme {attempt}/{attempts}: gorsel yok, '
                  f'{"yeniden denenecek" if attempt < attempts else "vazgecildi"}',
                  file=sys.stderr, flush=True)
        except Exception as exc:
            last_err = exc
            print(f'KAPAK deneme {attempt}/{attempts} basarisiz: {type(exc).__name__}, '
                  f'{"yeniden denenecek" if attempt < attempts else "vazgecildi"}',
                  file=sys.stderr, flush=True)
        resp = None
        if attempt < attempts:
            await asyncio.sleep(COVER_BACKOFFS[min(attempt - 1, len(COVER_BACKOFFS) - 1)])
    if not resp or not resp.images:
        raise SystemExit(f'Gemini gorsel uretilemedi ({attempts} deneme): '
                         f'{type(last_err).__name__ if last_err else "bos"}')
    img = resp.images[0]
    # Gecici dizinde uret
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        await img.save(path=td, filename='cover', verbose=False)
        # kutuphane timestamp + orijinal uzanti ile kaydeder, glob ile bul
        files = sorted(glob.glob(str(Path(td) / 'cover.*')))
        if not files:
            # img nesnesinin url uzantisina bak
            import re
            ext = '.jpg'
            if img.url:
                m = re.search(r'=jpeg$|=jpg$|=png$|=webp$', img.url)
                if m:
                    ext = '.' + m.group(0)[1:]
                elif 'png' in img.url: ext='.png'
                elif 'webp' in img.url: ext='.webp'
            # daha genis ara
            files = sorted(glob.glob(str(Path(td) / '*')))
            if not files:
                raise SystemExit('Kaydedilen dosya bulunamadi')
        src = Path(files[0])
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out_path)
        # JPEG'e donustur (PNG/WebP gelirse) ki generate_fallback_thumbnail tutarlı islesin
        try:
            from PIL import Image
            with Image.open(out_path) as im:
                im.convert('RGB').save(out_path, 'JPEG', quality=94)
        except Exception:
            pass
        sz = Path(out_path).stat().st_size
        print(f'KAPAK_OK: {out_path} ({sz} byte)', file=sys.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_path', help='cikti JPEG yolu')
    ap.add_argument('title', help='video basligi')
    ap.add_argument('--prompt', default=None, help='ozel prompt (varsayilanin yerine gecer)')
    args = ap.parse_args()
    asyncio.run(generate(args.out_path, args.title, args.prompt))

if __name__ == '__main__':
    main()
