"""Grounded, publication-free Gemini Web story drafting helpers.

Only the existing Gemini Web cookie client is used. Research is fetched from a
real Wikipedia REST page; this module deliberately marks claim checking as
partial because substring checks cannot prove semantic entailment.
"""
from __future__ import annotations

import fcntl
import json
import os
import random
import re
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import requests
from jsonschema import Draft202012Validator, FormatChecker

from content_engine import WIKI_SEED_TOPICS, extract_json_object

BASE_DIR = Path(__file__).resolve().parents[1]
RESPONSE_SCHEMA_PATH = BASE_DIR / "schemas" / "gemini_story_response.schema.json"
PROMPT_PATH = BASE_DIR / "prompts" / "gemini_web_story_v1.md"
PROMPT_VERSION = "gemini-web-story-v1"
DEFAULT_LEDGER_PATH = BASE_DIR / ".gemini_topic_ledger.json"
WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
LEDGER_LOCK_TIMEOUT_SECONDS = 10
RESERVATION_TTL_SECONDS = 900


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _topic_id(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", title.casefold()).strip("_")


@contextmanager
def _ledger_lock(ledger_path: Path) -> Iterator[None]:
    """Serialize ledger read-modify-write operations between concurrent runs."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_suffix(ledger_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        deadline = time.monotonic() + LEDGER_LOCK_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Konu tekrar koruması kilidi zaman aşımına uğradı.")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_ledger(ledger_path: Path) -> dict[str, Any]:
    if not ledger_path.exists():
        return {"used": [], "pending": {}}
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Konu tekrar defteri okunamadı; güvenli biçimde durduruldu.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("used", []), list) or not isinstance(data.get("pending", {}), dict):
        raise ValueError("Konu tekrar defterinin biçimi geçersiz; güvenli biçimde durduruldu.")
    data.setdefault("used", [])
    data.setdefault("pending", {})
    return data


def _write_ledger(ledger_path: Path, data: dict[str, Any]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=ledger_path.name + ".", suffix=".tmp", dir=ledger_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, ledger_path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def reserve_topic(topic_slugs: list[str], ledger_path: Path = DEFAULT_LEDGER_PATH) -> tuple[str, str]:
    """Reserve an unused topic atomically; return its slug and reservation ID."""
    now = _utc_now()
    now_text = now.isoformat()
    with _ledger_lock(ledger_path):
        ledger = _read_ledger(ledger_path)
        pending = ledger["pending"]
        active_pending: dict[str, Any] = {}
        for slug, entry in pending.items():
            try:
                created = datetime.fromisoformat(entry["created_at"])
            except (TypeError, ValueError, KeyError):
                continue
            if (now - created).total_seconds() < RESERVATION_TTL_SECONDS:
                active_pending[slug] = entry
        used = set(ledger["used"])
        eligible = [slug for slug in topic_slugs if slug not in used and slug not in active_pending]
        if not eligible:
            raise ValueError("Son dönemde kullanılmamış konu kalmadı; tekrar üretim engellendi.")
        slug = random.choice(eligible)
        reservation_id = str(uuid.uuid4())
        active_pending[slug] = {"id": reservation_id, "created_at": now_text}
        ledger["pending"] = active_pending
        _write_ledger(ledger_path, ledger)
        return slug, reservation_id


def recent_used_topics(ledger_path: Path = DEFAULT_LEDGER_PATH, limit: int = 25) -> list[str]:
    """Return only the newest committed topic IDs from the durable local ledger."""
    with _ledger_lock(ledger_path):
        ledger = _read_ledger(ledger_path)
        return [str(topic) for topic in ledger["used"][-max(1, limit):]]


def finish_topic_reservation(
    slug: str,
    reservation_id: str,
    *,
    commit: bool,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> None:
    """Commit a successfully validated topic or release its failed reservation."""
    with _ledger_lock(ledger_path):
        ledger = _read_ledger(ledger_path)
        entry = ledger["pending"].get(slug)
        if not isinstance(entry, dict) or entry.get("id") != reservation_id:
            raise ValueError("Konu rezervasyonu eşleşmedi; tekrar koruması güvenli biçimde durduruldu.")
        ledger["pending"].pop(slug, None)
        if commit:
            ledger["used"].append(slug)
            ledger["used"] = ledger["used"][-1000:]
        _write_ledger(ledger_path, ledger)


def fetch_topic_research(topic_slug: str, *, session: Any = requests) -> dict[str, str]:
    """Fetch a current public source excerpt and reject redirects off Wikipedia."""
    url = WIKIPEDIA_API.format(quote(topic_slug.replace("_", " "), safe=""))
    try:
        response = session.get(
            url,
            headers={"User-Agent": "ShortsResearchBot/1.0 (publication-free factual draft)"},
            timeout=(5, 15),
            allow_redirects=True,
        )
        response.raise_for_status()
        final_url = str(response.url)
        payload = response.json()
    except Exception as exc:
        raise ValueError(f"Araştırma kaynağı alınamadı ({type(exc).__name__}).") from None
    if not final_url.startswith("https://en.wikipedia.org/"):
        raise ValueError("Araştırma yönlendirmesi izin verilen Wikipedia alan adının dışına çıktı.")
    title = payload.get("title") if isinstance(payload, dict) else None
    extract = payload.get("extract") if isinstance(payload, dict) else None
    page_url = payload.get("content_urls", {}).get("desktop", {}).get("page") if isinstance(payload, dict) else None
    if not all(isinstance(value, str) and value.strip() for value in (title, extract, page_url)):
        raise ValueError("Araştırma yanıtı başlık, içerik veya kaynak URL'si içermiyor.")
    if not page_url.startswith("https://en.wikipedia.org/wiki/"):
        raise ValueError("Araştırma kaynağının kanonik URL'si geçersiz.")
    return {
        "source_id": _topic_id(topic_slug),
        "title": title.strip(),
        "extract": extract.strip(),
        "url": page_url,
        "accessed_at": _utc_now().isoformat(),
    }


def _normalized_topic_text(text: str) -> str:
    import unicodedata

    text = text.replace("ı", "i").replace("İ", "i").replace("_", " ").casefold()
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _topic_appears_in_recent_titles(topic_slug: str, recent_titles: list[str]) -> bool:
    normalized_topic = _normalized_topic_text(topic_slug)
    topic_tokens = [token for token in normalized_topic.split() if len(token) >= 5]
    if not topic_tokens:
        return False
    for title in recent_titles:
        normalized_title = _normalized_topic_text(title)
        if normalized_topic in normalized_title:
            return True
        # Seed başlıkları özel adla başlar; bu token eşlemesi Türkçe ek/boşluk
        # farklılıklarına dayanıklıdır (ör. "Göbeklitepe'nin").
        if any(token in normalized_title for token in topic_tokens[:2]):
            return True
    return False


def select_researched_topic(
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    *,
    recent_titles: list[str] | None = None,
    session: Any = requests,
) -> tuple[str, str, dict[str, str]]:
    """Try unused source seeds, excluding durable recent title history."""
    titles = recent_titles or []
    slugs = [slug for slug in WIKI_SEED_TOPICS if not _topic_appears_in_recent_titles(slug, titles)]
    attempted: list[str] = []
    while slugs:
        slug, reservation_id = reserve_topic(slugs, ledger_path)
        attempted.append(slug)
        try:
            research = fetch_topic_research(slug, session=session)
            return slug, reservation_id, research
        except ValueError:
            finish_topic_reservation(slug, reservation_id, commit=False, ledger_path=ledger_path)
            slugs.remove(slug)
    raise ValueError(f"Seed konularının hiçbiri araştırılamadı ({len(attempted)} konu denendi).")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wÇĞİÖŞÜçğıöşü'-]+\b", text, flags=re.UNICODE))


def validate_grounded_response(
    raw_text: str,
    *,
    topic_slug: str,
    research: dict[str, str],
) -> dict[str, Any]:
    """Validate the raw Gemini draft contract and source-quote relationships."""
    raw = extract_json_object(raw_text)
    schema = json.loads(RESPONSE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(raw), key=lambda err: list(map(str, err.absolute_path)))
    if errors:
        first = errors[0]
        field = ".".join(map(str, first.absolute_path)) or "<root>"
        raise ValueError(f"Gemini içerik sözleşmesi geçersiz ({field}): {first.message}")

    expected_id = _topic_id(topic_slug)
    if raw["topic_source_id"] != expected_id or research["source_id"] != expected_id:
        raise ValueError("Üretilen konu, araştırma kaynağıyla eşleşmiyor.")
    script = raw["script_text"].strip()
    count = _word_count(script)
    if not 55 <= count <= 95:
        raise ValueError(f"Senaryo kelime sayısı uygun değil: {count} (55-95 bekleniyor).")
    if raw["hook"].strip() not in script:
        raise ValueError("Hook, senaryo metninin içinde birebir bulunmuyor.")
    if raw["cta_line"].strip() not in script:
        raise ValueError("CTA, senaryo metninin içinde birebir bulunmuyor.")

    for index, claim in enumerate(raw["claims"], start=1):
        if claim["script_span"].strip() not in script:
            raise ValueError(f"claim {index}: script_span senaryonun içinde birebir bulunmuyor.")
        if claim["evidence_quote"].strip() not in research["extract"]:
            raise ValueError(f"claim {index}: evidence_quote alınan kaynak metninde birebir bulunmuyor.")

    scene_ids = [scene["scene_id"] for scene in raw["storyboard"]]
    if scene_ids != list(range(1, len(scene_ids) + 1)):
        raise ValueError("Storyboard scene_id değerleri art arda 1'den başlamalı.")
    for index, scene in enumerate(raw["storyboard"], start=1):
        if scene["narration"].strip() not in script:
            raise ValueError(f"Storyboard sahne {index}: narration senaryoda birebir bulunmuyor.")

    now = _utc_now().isoformat()
    source = {
        "id": expected_id,
        "name": research["title"],
        "url": research["url"],
        "accessed_at": research["accessed_at"],
    }
    return {
        **raw,
        "topic_source_id": expected_id,
        "source": source,
        "fact_check": {
            "status": "partial",
            "checked_at": now,
            "claims": [
                {
                    "claim": claim["claim"],
                    "status": "partially_verified",
                    "source_ids": [expected_id],
                    "notes": "Script span and source evidence quote are exact substring matches; semantic entailment requires independent review.",
                }
                for claim in raw["claims"]
            ],
        },
        "word_count": count,
        "provider": "gemini-web-session",
        "prompt_version": PROMPT_VERSION,
        "draft_only": True,
        "publish": False,
    }


def build_grounded_prompt(
    research: dict[str, str],
    recent_topics: list[str] | None = None,
    recent_titles: list[str] | None = None,
) -> tuple[str, str]:
    """Create a strict JSON-only prompt grounded in the fetched source extract."""
    recent = ", ".join(recent_topics or []) or "yok"
    recent_title_summary = (recent_titles or [])[-25:]
    try:
        system = PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("Versiyonlu Gemini Web prompt dosyası okunamadı.") from exc
    user = {
        "task": "Kaynak özeti üzerinden yeni bir Türkçe konu, 55-95 kelimelik senaryo, metadata ve 4-8 sahne storyboard üret.",
        "topic_source_id": research["source_id"],
        "avoid_recent_topics": recent,
        "avoid_recent_titles": recent_title_summary,
        "source": {"title": research["title"], "url": research["url"], "extract": research["extract"]},
        "output_contract": json.loads(RESPONSE_SCHEMA_PATH.read_text(encoding="utf-8")),
        "rules": [
            "Yalnızca bu kaynak özetindeki olguları kullan; emin olmadığın ayrıntıyı çıkar.",
            "Senaryo hook ile başlasın, CTA son cümle olsun ve ikisi de metinde birebir bulunsun.",
            "claims için üç veya daha fazla merkezi olgusal iddia ve kaynakta birebir kanıt alıntısı ver.",
            "Storyboard sahneleri sırayla numaralandır; narration cümleleri senaryodan birebir seçilsin.",
            "Üç Türkçe hashtag üret; reklam/affiliate bağlantısı ekleme.",
        ],
    }
    return system, json.dumps(user, ensure_ascii=False)


def draft_to_script_metadata(draft: dict[str, Any]) -> dict[str, Any]:
    """Map validated storyboard scenes into the legacy media search interface."""
    scenes = draft.get("storyboard")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Medya aktarımı için doğrulanmış storyboard bulunamadı.")
    return {
        "topic": draft["topic"],
        "title": draft["title"],
        "description": draft["description"],
        "source": f"{draft['source']['name']} — {draft['source']['url']}",
        "hook": draft["hook"],
        "script_text": draft["script_text"],
        "cta_line": draft["cta_line"],
        "thumbnail_prompt": draft["thumbnail_prompt"],
        "viral_hashtags": draft["viral_hashtags"],
        "visual_keywords": [scene["visual_query"] for scene in scenes],
        "storyboard": scenes,
        "sources": [draft["source"]],
        "fact_check": draft["fact_check"],
        "llm_provider": draft["provider"],
    }
