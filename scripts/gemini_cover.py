#!/usr/bin/env python3
"""Tek bir video icin Gemini web'den kapak uret.
Kullanim: python3 gemini_cover.py <out_path> <video_baslik> [--prompt "<ozel prompt>"]
JPEG olarak out_path'e yazar. Hata olursa non-zero exit.
--prompt verilirse kapak_gemini.json'daki varsayilan prompt yerine onu kullanir.
"""
import asyncio, json, os, sys, glob, shutil, argparse
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
# süresi embed_cover_frame.py'daki 240s subprocess bütçesinin altında kalır:
# init 45 + (75 üretim + 10 bekleme) + 75 üretim = 205s < 240s.
GEN_TIMEOUT_S = int(os.environ.get('GEMINI_GEN_TIMEOUT_S', '75'))
COVER_ATTEMPTS = max(1, int(os.environ.get('GEMINI_COVER_ATTEMPTS', '2')))
COVER_BACKOFFS = (10, 20)

async def generate(out_path: str, title: str, prompt_override: str | None = None):
    cookies = load_cookies()
    if prompt_override:
        prompt = prompt_override
    else:
        prompt = load_default_prompt() + '\n\nVideo basligi: ' + title
    client = GeminiClient(cookies.get('__Secure-1PSID',''), cookies.get('__Secure-1PSIDTS',''))
    await client.init(timeout=45, auto_refresh=True)
    resp = None
    last_err: Exception | None = None
    for attempt in range(1, COVER_ATTEMPTS + 1):
        try:
            resp = await asyncio.wait_for(client.generate_content(prompt), timeout=GEN_TIMEOUT_S)
            if resp and resp.images:
                break
            last_err = RuntimeError('gemini_gorsel_dondurmedi')
            print(f'KAPAK deneme {attempt}/{COVER_ATTEMPTS}: gorsel yok, '
                  f'{"yeniden denenecek" if attempt < COVER_ATTEMPTS else "vazgecildi"}',
                  file=sys.stderr, flush=True)
        except Exception as exc:
            last_err = exc
            print(f'KAPAK deneme {attempt}/{COVER_ATTEMPTS} basarisiz: {type(exc).__name__}, '
                  f'{"yeniden denenecek" if attempt < COVER_ATTEMPTS else "vazgecildi"}',
                  file=sys.stderr, flush=True)
        resp = None
        if attempt < COVER_ATTEMPTS:
            await asyncio.sleep(COVER_BACKOFFS[min(attempt - 1, len(COVER_BACKOFFS) - 1)])
    if not resp or not resp.images:
        raise SystemExit(f'Gemini gorsel uretilemedi ({COVER_ATTEMPTS} deneme): '
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
