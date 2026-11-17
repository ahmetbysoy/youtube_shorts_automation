#!/usr/bin/env python3
"""Gemini Web oturumuyla tek metin/JSON üretim denemesi; yayın hattına bağlı değildir."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from content_engine import (
    build_llm_prompts,
    extract_json_object,
    validate_and_normalize_scenario,
)

COOKIE_ENV_NAMES = ("GEMINI_COOK", "GEMINI_COOKIES_JSON", "GEMINI_COOKIE")


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


async def generate_text_scenario(concept: str) -> tuple[dict[str, Any], list[str]]:
    cookies = load_cookie_payload()

    # Bu testte yalnızca mevcut Gemini Web oturumu kullanılır.
    # GEMINI_API_KEY / GOOGLE_API_KEY okunmaz ve API endpoint'i çağrılmaz.
    from gemini_webapi import GeminiClient

    fact = {
        "title": "NASA Science: Venus Facts",
        "extract": (
            "Venus completes one rotation in about 243 Earth days and one orbit "
            "in about 225 Earth days. A solar day, from one sunrise to the next, "
            "is about 117 Earth days."
        ),
    }
    system_prompt, user_prompt = build_llm_prompts(concept, [], wiki_fact=fact)
    client = GeminiClient(cookies["__Secure-1PSID"], cookies["__Secure-1PSIDTS"])
    await client.init(timeout=30, auto_refresh=True)
    response = await asyncio.wait_for(client.generate_content(system_prompt + "\n\n" + user_prompt), timeout=90)

    response_text = getattr(response, "text", None)
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("Gemini Web metin yanıtı boş veya okunamadı.")

    scenario = validate_model_text(response_text)
    return scenario, list(cookies.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gemini Web cookie oturumuyla yayın yapmayan metin/JSON testi."
    )
    parser.add_argument("--concept", default="Venüs'ün dönüş ve yörünge süreleri")
    parser.add_argument("--output", type=Path, default=Path("text_probe_result.json"))
    args = parser.parse_args()

    try:
        scenario, cookie_values = asyncio.run(generate_text_scenario(args.concept))
        serialized = json.dumps(scenario, ensure_ascii=False, indent=2)
        if any(value in serialized for value in cookie_values):
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
