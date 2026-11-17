#!/usr/bin/env python3
"""Tek bir video icin Gemini web'den kapak uret.
Kullanim: python3 gemini_cover.py <out_path> <video_baslik>
JPEG olarak out_path'e yazar. Hata olursa non-zero exit.
"""
import asyncio, json, os, sys, glob, shutil
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

def load_prompt():
    return json.loads(CFG_PATH.read_text('utf8')).get('prompt','')

async def generate(out_path: str, title: str):
    cookies = load_cookies()
    prompt = load_prompt() + '\n\nVideo basligi: ' + title
    client = GeminiClient(cookies.get('__Secure-1PSID',''), cookies.get('__Secure-1PSIDTS',''))
    await client.init(timeout=30, auto_refresh=True)
    resp = await client.generate_content(prompt)
    if not resp or not resp.images:
        raise SystemExit('Gemini gorsel dondurmedi: ' + (resp.text[:300] if resp and resp.text else '(bos)'))
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
        sz = Path(out_path).stat().st_size
        print(f'KAPAK_OK: {out_path} ({sz} byte)', file=sys.stderr)

def main():
    if len(sys.argv) < 3:
        print('Kullanim: gemini_cover.py <out_path> "<video baslik>"', file=sys.stderr)
        sys.exit(2)
    asyncio.run(generate(sys.argv[1], sys.argv[2]))

if __name__ == '__main__':
    main()
