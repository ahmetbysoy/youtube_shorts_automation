#!/usr/bin/env python3
"""Gemini Web init teshis probe (cookie ile, yayin hattina bagli degil).

Amac: CI'da kapak uretiminin neden init'te takildigini kesin olarak tespit etmek.
  Part A: curl_cffi ham baglanti matrisi (google.com + gemini.google.com/app) x impersonate hedefi
  Part B: GeminiClient.init() impersonate matrisi (verbose) — hangi TLS hedefi init'i geciriyor?
  Part C: ilk basarili init ile TAM kapak uretimi (kapak_gemini.json promptu + baslik = uretim akisi)

Guvenlik: cookie degerleri hicbir zaman yazdirilmaz; rapor token/cookie icermez.
Cikti: probe_report.json + (basariliysa) probe_cover.jpg
"""
from __future__ import annotations

import asyncio, json, os, re, sys, time, glob, shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DEFAULT_TARGETS = 'chrome145,chrome131,chrome124,edge101,safari184'


def log(msg: str) -> None:
    print(f'[PROBE] {msg}', flush=True)


def load_cookies() -> dict:
    raw = os.environ.get('GEMINI_COOKIES_JSON') or os.environ.get('GEMINI_COOK')
    if raw:
        return json.loads(raw)
    local = REPO / 'jeton' / 'gemini_cookies.json'
    if local.exists():
        return json.loads(local.read_text('utf8'))
    raise SystemExit('HATA: GEMINI_COOKIES_JSON / GEMINI_COOK env yok ve jeton/gemini_cookies.json yok')


def report(out: dict) -> None:
    print(json.dumps(out, ensure_ascii=False), flush=True)


async def part_a(targets: list[str]) -> list[dict]:
    from curl_cffi.requests import AsyncSession
    rows = []
    for target in targets:
        for url in ('https://www.google.com', 'https://gemini.google.com/app'):
            t0 = time.monotonic()
            row = {'part': 'A', 'target': target, 'url': url.split('/')[2]}
            try:
                async with AsyncSession(impersonate=target, timeout=20) as s:
                    r = await s.get(url)
                row.update(status=r.status_code, sn=round(time.monotonic() - t0, 1))
            except Exception as e:
                row.update(error=type(e).__name__, sn=round(time.monotonic() - t0, 1))
            rows.append(row)
            log(f"A {target} {row.get('url')} -> {row.get('status', row.get('error'))} ({row['sn']}sn)")
    return rows


async def init_one(cookies: dict, target: str, init_timeout: int = 25,
                   hard_cap: int = 30, skip_rpc: bool = True) -> tuple[object | None, dict]:
    from gemini_webapi import GeminiClient
    t0 = time.monotonic()
    row: dict = {'part': 'B', 'target': target, 'skip_rpc': skip_rpc}
    client = GeminiClient(cookies.get('__Secure-1PSID', ''), cookies.get('__Secure-1PSIDTS', ''))
    if skip_rpc:
        # 2026-11-18 sonrasi: init'in _init_rpc() telemetri RPC'leri (GET_USER_STATUS
        # vb.) batchexecute'dan HTTP 400 aliyor ve kutuphane ic retry'larla ~30sn
        # takiliyor. Bu RPC'ler generate_content icin gereksizdir (model=None ->
        # hesap varsayilani). Bypass ile init dogrudan tamamlanir.
        client._init_rpc = lambda: asyncio.sleep(0)
    try:
        await asyncio.wait_for(client.init(timeout=init_timeout, auto_refresh=False,
                                           impersonate=target, verbose=True),
                               timeout=hard_cap)
        sn = round(time.monotonic() - t0, 1)
        tok = client.access_token or ''
        row.update(ok=bool(tok), sn=sn, token_len=len(tok),
                   cookie_source=getattr(client, '_cookie_source', '?'))
        if tok:
            log(f"B {target} skip_rpc={skip_rpc} init OK ({sn}sn) token={len(tok)} karakter")
        else:
            row.update(ok=False, error='token_bos')
            client = None
    except Exception as e:
        row.update(ok=False, error=type(e).__name__, sn=round(time.monotonic() - t0, 1))
        log(f"B {target} skip_rpc={skip_rpc} init FAIL: {type(e).__name__} ({row['sn']}sn)")
        client = None
    report(row)
    return client, row


async def part_c(client, cookies: dict, title: str) -> dict:
    """Uretim akisinin birebir aynisi: kapak_gemini.json promptu + '\n\nVideo basligi: <title>'."""
    row = {'part': 'C'}
    try:
        prompt = json.loads((REPO / 'kapak_gemini.json').read_text('utf8')).get('prompt', '')
        full_prompt = (prompt + '\n\nVideo basligi: ' + title)
        log(f"C prompt uzunlugu {len(prompt)} + baslik {len(title)} — uretim basliyor")
        t0 = time.monotonic()
        resp = await asyncio.wait_for(client.generate_content(full_prompt), timeout=90)
        if not resp or not getattr(resp, 'images', None):
            row.update(ok=False, error='gorsel_yok',
                       text=(getattr(resp, 'text', '') or '')[:200])
            report(row)
            return row
        img = resp.images[0]
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            await img.save(path=td, filename='cover', verbose=False)
            files = sorted(glob.glob(str(Path(td) / 'cover.*'))) or sorted(glob.glob(str(Path(td) / '*')))
            if not files:
                row.update(ok=False, error='dosya_yok')
                report(row)
                return row
            out = REPO / 'probe_cover.jpg'
            shutil.copyfile(files[0], out)
            try:
                from PIL import Image
                with Image.open(out) as im:
                    w, h = im.size
                    im.convert('RGB').save(out, 'JPEG', quality=94)
                row.update(width=w, height=h)
            except Exception:
                pass
            row.update(ok=True, sn=round(time.monotonic() - t0, 1),
                       bytes=out.stat().st_size, path=str(out))
    except Exception as e:
        row.update(ok=False, error=type(e).__name__, detail=str(e)[:200])
    report(row)
    return row


async def part_d(client) -> list[dict]:
    """batchexecute 400 teshisi: kutuphaneyle ayni POST'u elle kurup yanit gövdesini oku.

    Varyantlar: D1 birebir klon, D2 f.sid'siz, D3 bl'siz, D4 minimal f.req.
    Yanit gövdesi (Google hata mesaji) sansürlenerek yazdirilir.
    """
    from gemini_webapi.constants import Endpoint, Headers, GRPC, MODEL_HEADER_KEY
    from gemini_webapi.types import RPCData

    def scrub(text: str) -> str:
        # uzun base64 benzeri tokenleri maskele (guvenlik, cookie/token asla loglanmaz)
        return re.sub(r'[A-Za-z0-9_-]{40,}', '<masked>', text or '')[:500]

    tests = []
    payloads = [RPCData(rpcid=GRPC.GET_USER_STATUS, payload='[]')]
    # ORNEK ONEM: kutuphane f.req ve header serialization icin ORJSON kullanir
    # (orjson.dumps bytes doner). Ayni serializer kullanilmali yoksa kiyas bozulur.
    import orjson
    freq = orjson.dumps([[p.serialize() for p in payloads]]).decode('utf8')
    base_params = {
        'rpcids': GRPC.GET_USER_STATUS,
        'hl': getattr(client, 'language', 'en-US') or 'en-US',
        '_reqid': getattr(client, '_reqid', 10000),
        'rt': 'c',
        'source-path': '/app',
    }
    if getattr(client, 'build_label', None):
        base_params['bl'] = client.build_label
    if getattr(client, 'session_id', None):
        base_params['f.sid'] = client.session_id
    batch_exec_headers = Headers.BATCH_EXEC.value.copy()
    h = orjson.loads(batch_exec_headers[MODEL_HEADER_KEY])
    h.append(client._sessionid)
    batch_exec_headers[MODEL_HEADER_KEY] = orjson.dumps(h).decode('utf8')
    request_headers = {**Headers.GEMINI.value, **batch_exec_headers, **Headers.SAME_DOMAIN.value}
    data = {'at': client.access_token or '', 'f.req': freq}

    variants = [
        ('D1_klon', dict(base_params), data),
        ('D2_fsid_yok', {k: v for k, v in base_params.items() if k != 'f.sid'}, data),
        ('D3_bl_yok', {k: v for k, v in base_params.items() if k != 'bl'}, data),
        ('D4_minimal_freq', dict(base_params),
         {'at': client.access_token or '', 'f.req': '[["otAQ7b","[]",null,"generic"]]'}),
    ]
    for name, params, d in variants:
        row = {'part': 'D', 'test': name}
        try:
            r = await client._live_client.post(Endpoint.BATCH_EXEC, params=params,
                                               headers=request_headers, data=d)
            row.update(status=r.status_code, body=scrub(r.text))
        except Exception as e:
            row.update(error=type(e).__name__, detail=str(e)[:150])
        tests.append(row)
        log(f"{name} -> {row.get('status', row.get('error'))} gövde: {row.get('body', row.get('detail', ''))[:200]}")
    return tests


async def main_async(args) -> int:
    targets = [t.strip() for t in args.targets.split(',') if t.strip()]
    cookies = load_cookies()
    log(f"cookie yuklendi (PSID {len(cookies.get('__Secure-1PSID', ''))} / PSIDTS {len(cookies.get('__Secure-1PSIDTS', ''))} karakter) — deger yazdirilmiyor")

    import curl_cffi
    import importlib.metadata as md
    try:
        gw_ver = md.version('gemini-webapi')
    except Exception:
        gw_ver = '?'
    summary = {'curl_cffi': curl_cffi.__version__, 'gemini_webapi': gw_ver,
               'targets': targets, 'a': [], 'b': [], 'c': None, 'd': [],
               'started': time.strftime('%Y-%m-%dT%H:%M:%S')}

    summary['a'] = await part_a(targets)
    summary['b'] = []

    winner = None
    for target in targets:
        client, row = await init_one(cookies, target)
        summary['b'].append(row)
        if client is not None and row.get('ok'):
            winner = client
            winner_target = target
            break

    if winner is not None:
        log(f"init BASARILI: {winner_target} — batchexecute teshis varyantlari (Part D)")
        try:
            summary['d'] = await part_d(winner)
        except Exception as e:
            log(f"Part D hatasi: {type(e).__name__}: {str(e)[:150]}")
        log(f"tam kapak uretim testi (Part C)")
        summary['c'] = await part_c(winner, cookies, args.title)
        try:
            await asyncio.wait_for(winner.close(), timeout=10)
        except Exception:
            pass
    else:
        log('hicbir impersonate hedefi init i geciremedi (Part C atlandi)')

    if winner is not None:
        summary['c_target'] = winner_target
    out = Path(args.output)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf8')
    log(f"rapor: {out}")
    # Basari kosulu: en az bir hedef init gecmeli; kapak uretimi (Part C) bilgi amacli
    return 0 if any(r.get('ok') for r in summary['b']) else 2


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--title', default="Ay'a Gitmek Icin Hicbir Zaman Cikmayacak: Iste Gercek Sebep!")
    ap.add_argument('--targets', default=DEFAULT_TARGETS)
    ap.add_argument('--output', default='probe_report.json')
    args = ap.parse_args()
    # loguru DEBUG: kutuphanin verbose loglari gorunsun (cookie icermez)
    try:
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level='DEBUG', format='{time:HH:mm:ss} {level} {message}')
    except Exception:
        pass
    sys.exit(asyncio.run(main_async(args)))


if __name__ == '__main__':
    main()
