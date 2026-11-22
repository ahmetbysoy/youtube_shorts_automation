#!/usr/bin/env python3
"""Gemini Web oturumuyla tek metin/JSON üretim denemesi; yayın hattına bağlı değildir."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from content_engine import extract_json_object, validate_and_normalize_scenario
from scripts.gemini_web_story import (
    build_grounded_prompt,
    draft_to_script_metadata,
    finish_topic_reservation,
    recent_used_topics,
    select_researched_topic,
    validate_grounded_response,
)

COOKIE_ENV_NAMES = ("GEMINI_COOK", "GEMINI_COOKIES_JSON", "GEMINI_COOKIE")


def _env_float(name: str, default: float) -> float:
    """Pozitif float env okuyucu; gecersiz/eksik degerde default doner."""
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_backoff_schedule(raw: str | None, attempts: int) -> list[float]:
    """"10,20" benzeri listeyi (attempts-1) ogeli backoff dizisine cevirir.

    Eksik ogeler son gecerli degerle doldurulur; gecersizler atlanir.
    """
    gaps = max(0, attempts - 1)
    values: list[float] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = float(part)
        except ValueError:
            continue
        if value >= 0:
            values.append(value)
    while len(values) < gaps and values:
        values.append(values[-1])
    while len(values) < gaps:
        values.append(0.0)
    return values[:gaps]


def parse_cookie_payload(raw: str) -> dict[str, str]:
    """Secret JSON'ını doğrular; cookie değerlerini hiçbir zaman yazdırmaz."""
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Gemini cookie secret geçerli JSON değil.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Gemini cookie secret bir JSON nesnesi olmalı.")

    session_cookie = payload.get("__Secure-1PSID")
    refresh_cookie = payload.get("__Secure-1PSIDTS", "")
    if not isinstance(session_cookie, str) or not session_cookie.strip():
        raise ValueError("Gemini cookie secret içinde __Secure-1PSID alanı eksik.")
    if not isinstance(refresh_cookie, str):
        raise ValueError("__Secure-1PSIDTS alanı metin olmalı.")

    return {
        "__Secure-1PSID": session_cookie.strip(),
        "__Secure-1PSIDTS": refresh_cookie.strip(),
    }


def load_cookie_payload() -> dict[str, str]:
    raw = next((os.environ.get(name, "").strip() for name in COOKIE_ENV_NAMES
                if os.environ.get(name, "").strip()), "")
    if not raw:
        local_path = Path("jeton/gemini_cookies.json")
        if local_path.is_file():
            raw = local_path.read_text(encoding="utf-8")
    if not raw:
        raise ValueError("GEMINI_COOK secret/env bulunamadı.")
    return parse_cookie_payload(raw)


def validate_model_text(raw_text: str) -> dict[str, Any]:
    """Model yanıtının JSON ve Shorts içerik sözleşmesini doğrular."""
    raw = extract_json_object(raw_text)
    required = ("topic", "title", "description", "hook", "script_text", "visual_keywords")
    missing = [key for key in required if not raw.get(key)]
    if missing:
        raise ValueError("Gemini JSON çıktısında zorunlu alanlar eksik: " + ", ".join(missing))

    keywords = raw.get("visual_keywords")
    if not isinstance(keywords, list) or len(keywords) < 4:
        raise ValueError("Gemini en az dört sahneye özel visual_keywords üretmedi.")
    if any(not isinstance(item, str) or not item.strip() for item in keywords[:4]):
        raise ValueError("visual_keywords içinde boş veya metin olmayan arama terimi var.")

    scenario = validate_and_normalize_scenario(raw, "gemini-web-session")
    if not 55 <= scenario["word_count"] <= 95:
        raise ValueError(
            f"Senaryo kelime sayısı test aralığında değil: {scenario['word_count']} (55-95)."
        )
    if len(scenario["viral_hashtags"]) != 3:
        raise ValueError("Senaryo üç adet konuya özel hashtag'e normalize edilemedi.")
    return scenario


def _pw_text_generate(prompt: str, cookies: dict, budget_s: float) -> str:
    """PW metin adapter'ini subprocess ile kosar (senkron; asyncio.to_thread ile sarmalanir).

    Cookie dict GEMINI_COOKIES_JSON env ile child'a gecer — log/artifact'a asla yazilmaz.
    """
    with tempfile.TemporaryDirectory() as td:
        pf = Path(td) / "prompt.txt"
        of = Path(td) / "response.txt"
        pf.write_text(prompt, encoding="utf8")
        env = dict(os.environ)
        env["GEMINI_COOKIES_JSON"] = json.dumps(cookies, ensure_ascii=False)
        cmd = [sys.executable, str(BASE_DIR / "scripts" / "gemini_story_pw.py"),
               "--prompt-file", str(pf), "--out", str(of),
               "--timeout", str(int(budget_s))]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=budget_s + 40, env=env)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"PW metin adapter zamana asimi ({budget_s + 40:.0f}sn)") from exc
        err_tail = (proc.stderr or "")[-400:]
        if proc.returncode != 0:
            raise RuntimeError(
                f"PW metin adapter basarisiz (rc={proc.returncode}): {err_tail}")
        if not of.exists():
            raise RuntimeError(f"PW metin adapter cikti yazmadi: {err_tail}")
        text = of.read_text("utf8")
        if not text.strip():
            raise RuntimeError("PW metin adapter bos yanit dondu.")
        return text


async def _one_topic_attempt(
    cookies: dict, topic_slug: str, research: dict,
    concept: str, recent_titles: list[str] | None,
    init_timeout_s: float = 35.0,
    generate_timeout_s: float = 55.0,
) -> dict[str, Any]:
    """Tek bir konu icin Gemini generate + validate. Tamami timeout'lu.

    Transport varsayilani 'pw': gercek Chromium (gemini_story_pw.py) — kapak
    adapter'i ile ayni kanitli yol; Google'in kutuphane batchexecute 400
    engelini bypass eder. 'library' = eski gemini_webapi yolu (rollback).
    """
    system_prompt, user_prompt = build_grounded_prompt(
        research,
        recent_topics=recent_used_topics(),
        recent_titles=recent_titles,
    )
    if concept.strip():
        user_prompt += "\nEk editoryal tercih (olguları değiştirmeden): " + concept.strip()
    full_prompt = system_prompt + "\n\n" + user_prompt

    transport = (os.environ.get("GEMINI_TEXT_TRANSPORT", "pw") or "pw").strip().lower()
    if transport == "pw":
        budget = _env_float("GEMINI_PW_TEXT_TIMEOUT_S", 150.0)
        response_text = await asyncio.wait_for(
            asyncio.to_thread(_pw_text_generate, full_prompt, cookies, budget),
            timeout=budget + 50,
        )
    else:
        from gemini_webapi import GeminiClient

        client = GeminiClient(cookies["__Secure-1PSID"], cookies["__Secure-1PSIDTS"])
        # 2026-11-22: Google kutuphanenin tum batchexecute POST'larina HTTP 400
        # donuyor (kapak teshisi ile ayni kok). _init_rpc bypass: init hizli,
        # generate hizli APIError → fallback erken tetiklenir.
        client._init_rpc = lambda: asyncio.sleep(0)
        await asyncio.wait_for(client.init(timeout=int(init_timeout_s), auto_refresh=False),
                               timeout=init_timeout_s)
        try:
            response = await asyncio.wait_for(
                client.generate_content(full_prompt),
                timeout=generate_timeout_s,
            )
        finally:
            try:
                await asyncio.wait_for(client.close(), timeout=5)
            except Exception:
                pass
        response_text = getattr(response, "text", None)
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("Gemini Web metin yanıtı boş veya okunamadı.")
    draft = validate_grounded_response(response_text, topic_slug=topic_slug, research=research)
    scenario = draft_to_script_metadata(draft)
    scenario.update({
        "word_count": draft["word_count"],
        "provider": draft["provider"],
        "draft_only": True,
        "publish": False,
        "topic_source_id": draft["topic_source_id"],
        "claims": draft["claims"],
        "prompt_version": draft["prompt_version"],
    })
    return scenario


async def generate_text_scenario(
    concept: str = "", recent_titles: list[str] | None = None
) -> tuple[dict[str, Any], list[str]]:
    """Cookie ile Gemini Web'den senaryo üret.

    Sure bütçeleri env ile ayarlanabilir; varsayılanlar:
    - GEMINI_WEB_ATTEMPT_TIMEOUT_S=80   (tek konu denemesi üst sınırı)
    - GEMINI_WEB_TOTAL_TIMEOUT_S=240    (tüm Gemini akışı mutlak üst sınırı)
    - GEMINI_WEB_INIT_TIMEOUT_S=35      (oturum kurulum fazı)
    - GEMINI_WEB_GENERATE_TIMEOUT_S=55  (üretim fazı)
    - GEMINI_WEB_BACKOFF_SCHEDULE_S="10,20" (denemeler arası bekleme)

    Üst sınırlar aşılırsa TimeoutError yukarıya doğru yayılır
    (content_engine fallback'i tetikler).
    """
    MAX_TOPIC_ATTEMPTS = 3
    PER_ATTEMPT_TIMEOUT = _env_float("GEMINI_WEB_ATTEMPT_TIMEOUT_S", 80)
    TOTAL_TIMEOUT = _env_float("GEMINI_WEB_TOTAL_TIMEOUT_S", 240)
    INIT_TIMEOUT_S = _env_float("GEMINI_WEB_INIT_TIMEOUT_S", 35)
    GENERATE_TIMEOUT_S = _env_float("GEMINI_WEB_GENERATE_TIMEOUT_S", 55)
    BACKOFF_SCHEDULE = _parse_backoff_schedule(
        os.environ.get("GEMINI_WEB_BACKOFF_SCHEDULE_S", "10,20"), MAX_TOPIC_ATTEMPTS)
    # 2026-11-22: transport=pw (gercek Chromium) tek denemesi kutuphaneden uzun surer
    # (sayfa acilma + doldurma + yanit kararliligi). Butceler buna gore acilir.
    TRANSPORT = (os.environ.get("GEMINI_TEXT_TRANSPORT", "pw") or "pw").strip().lower()
    if TRANSPORT == "pw":
        PW_TEXT_BUDGET = _env_float("GEMINI_PW_TEXT_TIMEOUT_S", 150.0)
        PER_ATTEMPT_TIMEOUT = max(PER_ATTEMPT_TIMEOUT, PW_TEXT_BUDGET + 60)
        TOTAL_TIMEOUT = max(TOTAL_TIMEOUT, PW_TEXT_BUDGET + 90)
    cookies = load_cookie_payload()
    last_error: Exception | None = None
    excluded: set[str] = set()

    async def _run_all_attempts() -> dict[str, Any]:
        nonlocal last_error
        for attempt in range(MAX_TOPIC_ATTEMPTS):
            topic_slug, reservation_id, research = select_researched_topic(
                recent_titles=recent_titles, exclude_slugs=excluded)
            attempt_started = time.monotonic()
            try:
                scenario = await asyncio.wait_for(
                    _one_topic_attempt(cookies, topic_slug, research, concept, recent_titles,
                                       init_timeout_s=INIT_TIMEOUT_S,
                                       generate_timeout_s=GENERATE_TIMEOUT_S),
                    timeout=PER_ATTEMPT_TIMEOUT,
                )
                finish_topic_reservation(topic_slug, reservation_id, commit=True)
                return scenario
            except ValueError as exc:
                last_error = exc
                excluded.add(topic_slug)
                print(f"[GEMINI_WEB] konu={topic_slug} deneme {attempt+1}/{MAX_TOPIC_ATTEMPTS} "
                      f"basarisiz ({time.monotonic() - attempt_started:.0f}sn): {str(exc)[:150]}",
                      file=sys.stderr, flush=True)
            except asyncio.TimeoutError as exc:
                last_error = exc
                excluded.add(topic_slug)
                elapsed = time.monotonic() - attempt_started
                print(f"[GEMINI_WEB] konu={topic_slug} deneme {attempt+1}/{MAX_TOPIC_ATTEMPTS} "
                      f"timeout (deneme {elapsed:.0f}sn, ust sinir {PER_ATTEMPT_TIMEOUT:.0f}sn) "
                      f"— konu atlandi", file=sys.stderr, flush=True)
            except Exception as exc:
                last_error = exc
                excluded.add(topic_slug)
                print(f"[GEMINI_WEB] konu={topic_slug} deneme {attempt+1}/{MAX_TOPIC_ATTEMPTS} "
                      f"harici hata ({time.monotonic() - attempt_started:.0f}sn): "
                      f"{type(exc).__name__}", file=sys.stderr, flush=True)
            # Basarisiz denemede rezervasyonu serbest birak
            try:
                finish_topic_reservation(topic_slug, reservation_id, commit=False)
            except Exception:
                pass
            # Denemeler arasi backoff: Google'in gecici kisitlamalarina nefes
            # alani verir; uclu denemenin toplam butce icinde kalmasini korur.
            if attempt < MAX_TOPIC_ATTEMPTS - 1 and BACKOFF_SCHEDULE:
                delay = BACKOFF_SCHEDULE[min(attempt, len(BACKOFF_SCHEDULE) - 1)]
                if delay > 0:
                    print(f"[GEMINI_WEB] denemeler arasi backoff: {delay:.0f}sn",
                          file=sys.stderr, flush=True)
                    await asyncio.sleep(delay)
        assert last_error is not None
        raise last_error

    runner = asyncio.ensure_future(_run_all_attempts())
    try:
        scenario = await asyncio.wait_for(runner, timeout=TOTAL_TIMEOUT)
    except asyncio.TimeoutError as exc:
        # Dikkat: wait_for ic gorev BITTIYSE ic gorevin kendi hatasini oldugu
        # gibi yaydigi icin bu catch'e dusulebilir. Gercek toplam zamanaasimi ile
        # son deneme hatasini ayristirmak icin gorevin bittigi/kendisi hatasi mi
        # kontrol edilir (yoksa log 'TOPLAM TIMEOUT' diye yaniltir).
        try:
            inner_done_self = runner.done() and runner.exception() is exc
        except BaseException:
            inner_done_self = False
        if inner_done_self:
            print(f"[GEMINI_WEB] tum denemeler tukendi ({type(exc).__name__}) — "
                  f"fallback'e donuluyor", file=sys.stderr, flush=True)
        else:
            print(f"[GEMINI_WEB] TOPLAM TIMEOUT ({TOTAL_TIMEOUT:.0f}sn) — fallback'e donuluyor",
                  file=sys.stderr, flush=True)
        raise  # content_engine fallback'e
    return scenario, list(cookies.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gemini Web cookie oturumuyla yayın yapmayan metin/JSON testi."
    )
    parser.add_argument("--concept", default="", help="İsteğe bağlı editoryal tercih; konu kaynaklardan seçilir.")
    parser.add_argument("--output", type=Path, default=Path("text_probe_result.json"))
    args = parser.parse_args()

    try:
        scenario, cookie_values = asyncio.run(generate_text_scenario(args.concept))
        serialized = json.dumps(scenario, ensure_ascii=False, indent=2)
        if any(value and value in serialized for value in cookie_values):
            raise ValueError("Güvenlik kontrolü: çıktı içinde cookie değeri tespit edildi.")

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    except Exception as exc:
        # İstisna metni bazı istemci sürümlerinde oturum verisi taşıyabilir.
        print(f"[HATA] Gemini Web metin testi başarısız: {type(exc).__name__}", file=sys.stderr)
        return 1

    print("GEMINI_WEB_TEXT_OK")
    print("PROVIDER=gemini-web-session")
    print(f"WORD_COUNT={scenario['word_count']}")
    print("DRAFT_ONLY=1")
    print("PUBLISH=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
