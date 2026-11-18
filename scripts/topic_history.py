"""Atomic topic/title history with GitHub Contents API compare-and-swap persistence.

Legacy `.used_topics.json` title lists are preserved on migration. In Actions,
a candidate is persisted as pending before production continues, then committed
or released by an always-run workflow step.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
import re
import tempfile
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from scripts.semantic_fact_check import _canonical_terms

DEFAULT_PATH = Path(__file__).resolve().parents[1] / ".used_topics.json"
MARKER_PATH = Path(__file__).resolve().parents[1] / ".topic_reservations.json"
RESERVATION_TTL_SECONDS = 1800
CAS_RETRIES = 6
_STOP = frozenset("bir ve veya ama olan olarak icin ile daha sonra neden nasil gercek shorts su bu en the and for from a an of in to is are was were".split())
_GENERIC_CATEGORIES = {"bilim", "tarih", "doga", "uzay", "science", "history", "nature", "technology"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: str) -> str:
    text = str(text or "").replace("İ", "i").replace("I", "ı").casefold()
    text = unicodedata.normalize("NFKD", text)
    return " ".join(re.findall(r"[a-z0-9]+", "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ı", "i")))


def _tokens(text: str) -> set[str]:
    return {term for term in _canonical_terms(str(text or "")) if term not in _STOP and len(term) > 1}


def _record(title: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or {}
    topic = str(metadata.get("topic") or metadata.get("category") or "").strip()
    script = str(metadata.get("script_text") or "").strip()
    fact_check = metadata.get("fact_check") if isinstance(metadata.get("fact_check"), dict) else {}
    claims_raw = metadata.get("claims") or fact_check.get("claims", [])
    claims = []
    if isinstance(claims_raw, list):
        for item in claims_raw:
            claim = item.get("claim") if isinstance(item, dict) else item
            if isinstance(claim, str) and claim.strip():
                claims.append(claim.strip())
    source_id = str(metadata.get("topic_source_id") or "").strip()
    topic_key = _norm(source_id.replace("_", " ")) if source_id else (_norm(topic) if _norm(topic) not in _GENERIC_CATEGORIES else "")
    topic_subject = source_id.replace("_", " ") if source_id else (topic if topic_key else title)
    entities: set[str] = set()
    for candidate in (topic, title, *claims):
        for word in re.findall(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b", candidate):
            if _norm(word) not in _STOP:
                entities.add(_norm(word))
    if source_id:
        entities.add(_norm(source_id.replace("_", " ")))
    claims_terms = [_tokens(claim) for claim in claims]
    return {
        "title": title.strip(),
        "topic": topic,
        "topic_subject": topic_subject,
        "topic_key": topic_key,
        "category": _norm(str(metadata.get("category") or topic)),
        "entities": sorted(entities),
        "claims": [sorted(terms) for terms in claims_terms],
        "scenario_tokens": sorted(_tokens(" ".join((topic, title, script, *claims)))),
        "created_at": _now().isoformat(),
    }


def _valid_record(record: Any, *, pending: bool = False) -> bool:
    if not isinstance(record, dict) or not isinstance(record.get("title"), str) or not record["title"].strip():
        return False
    if not isinstance(record.get("topic_key", ""), str) or not isinstance(record.get("category", ""), str):
        return False
    for key in ("entities", "scenario_tokens"):
        if not isinstance(record.get(key), list) or not all(isinstance(x, str) for x in record[key]):
            return False
    if not isinstance(record.get("claims"), list) or not all(
        isinstance(group, list) and all(isinstance(term, str) for term in group) for group in record["claims"]
    ):
        return False
    if not isinstance(record.get("created_at"), str):
        return False
    if pending and (not isinstance(record.get("reservation_id"), str) or not record.get("reservation_id") or not isinstance(record.get("run_id"), str)):
        return False
    return True


def _upgrade(data: Any) -> dict[str, Any]:
    if isinstance(data, list) and all(isinstance(item, str) for item in data):
        titles = data[-1000:]
        return {"version": 2, "used_titles": titles, "used_records": [_record(title) for title in titles], "pending": []}
    if not isinstance(data, dict) or data.get("version") != 2:
        raise ValueError(".used_topics.json biçimi geçersiz; tekrar koruması fail-closed durduruldu.")
    titles, records, pending = data.get("used_titles"), data.get("used_records"), data.get("pending")
    if not isinstance(titles, list) or not all(isinstance(item, str) for item in titles):
        raise ValueError(".used_topics.json used_titles bozuk; fail-closed.")
    if not isinstance(records, list) or not all(_valid_record(item) for item in records):
        raise ValueError(".used_topics.json used_records bozuk; fail-closed.")
    if not isinstance(pending, list) or not all(_valid_record(item, pending=True) for item in pending):
        raise ValueError(".used_topics.json pending bozuk; fail-closed.")
    result = {"version": 2, "used_titles": titles[-1000:], "used_records": records[-1000:], "pending": pending}
    existing = {item["title"] for item in result["used_records"]}
    result["used_records"].extend(_record(title) for title in result["used_titles"] if title not in existing)
    result["used_records"] = result["used_records"][-1000:]
    return result


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _duplicate(candidate: dict[str, Any], previous: dict[str, Any]) -> tuple[bool, str]:
    if _norm(candidate.get("title", "")) and _norm(candidate.get("title", "")) == _norm(previous.get("title", "")):
        return True, "exact_title"
    key_a, key_b = candidate.get("topic_key"), previous.get("topic_key")
    if key_a and key_b and key_a == key_b:
        return True, "same_normalized_topic"
    entities_a, entities_b = set(candidate.get("entities", [])), set(previous.get("entities", []))
    entity_overlap = bool(entities_a & entities_b)
    topic_a = _tokens(candidate.get("topic_subject") or candidate.get("title", ""))
    topic_b = _tokens(previous.get("topic_subject") or previous.get("title", ""))
    if entity_overlap and _jaccard(topic_a, topic_b) >= 0.34:
        return True, "same_topic_entity"
    claims_a = [set(group) for group in candidate.get("claims", []) if group]
    claims_b = [set(group) for group in previous.get("claims", []) if group]
    pairs = [(a, b) for a in claims_a for b in claims_b if min(len(a), len(b)) >= 3]
    coverage = max((len(a & b) / min(len(a), len(b)) for a, b in pairs), default=0.0)
    shared = max((len(a & b) for a, b in pairs), default=0)
    if (coverage >= 0.72 and entity_overlap) or (coverage >= 0.8 and shared >= 4):
        return True, "same_core_claim"
    if entity_overlap and _jaccard(set(candidate.get("scenario_tokens", [])), set(previous.get("scenario_tokens", []))) >= 0.45:
        return True, "similar_scenario"
    return False, "new_topic"


def _active_pending(data: dict[str, Any]) -> list[dict[str, Any]]:
    cutoff = _now() - timedelta(seconds=RESERVATION_TTL_SECONDS)
    active = []
    for entry in data["pending"]:
        try:
            created = datetime.fromisoformat(entry["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created >= cutoff:
                active.append(entry)
        except (TypeError, ValueError):
            continue
    return active


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


@contextmanager
def _file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class GitHubContentsStore:
    """GitHub Contents API store; the fetched blob SHA is a compare-and-swap version."""

    def __init__(self, repository: str, token: str, *, ref: str = "main", path: str = ".used_topics.json", session: Any = requests):
        if not repository or "/" not in repository or not token:
            raise ValueError("GitHub topic history credentials/repository are incomplete.")
        self.repository, self.token, self.ref, self.path, self.session = repository, token, ref, path, session
        self.url = f"https://api.github.com/repos/{repository}/contents/{quote(path, safe='/')}"
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

    def get(self) -> tuple[dict[str, Any], str | None]:
        response = self.session.get(self.url, headers=self.headers, params={"ref": self.ref}, timeout=(5, 20))
        if response.status_code == 404:
            return {"version": 2, "used_titles": [], "used_records": [], "pending": []}, None
        if response.status_code != 200:
            raise RuntimeError(f"Konu geçmişi GitHub'dan okunamadı (HTTP {response.status_code}); fail-closed.")
        try:
            body = response.json()
            old = json.loads(base64.b64decode(body["content"].replace("\n", ""), validate=True).decode("utf-8"))
            sha = str(body["sha"])
        except Exception as exc:
            raise RuntimeError(f"Konu geçmişi GitHub yanıtı bozuk ({type(exc).__name__}); fail-closed.") from None
        return _upgrade(old), sha

    def put(self, data: dict[str, Any], sha: str | None) -> bool:
        content = base64.b64encode((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()).decode()
        payload: dict[str, Any] = {"message": "chore: atomic topic history reservation", "content": content, "branch": self.ref}
        if sha:
            payload["sha"] = sha
        response = self.session.put(self.url, headers=self.headers, json=payload, timeout=(5, 20))
        if response.status_code in (409, 422):
            return False
        if response.status_code not in (200, 201):
            raise RuntimeError(f"Konu geçmişi GitHub'a yazılamadı (HTTP {response.status_code}); fail-closed.")
        return True


def _write_marker(path: Path, reservation_id: str, run_id: str) -> None:
    marker = path.with_name(".topic_reservations.json")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError
    except FileNotFoundError:
        data = []
    except (OSError, json.JSONDecodeError, ValueError):
        raise ValueError("Rezervasyon işaretçisi okunamadı; fail-closed.") from None
    data.append({"reservation_id": reservation_id, "run_id": run_id})
    _atomic_write(marker, data)


def _reserve_local(candidate: dict[str, Any], data: dict[str, Any], path: Path, reservation_id: str, run_id: str) -> dict[str, Any]:
    data["pending"] = _active_pending(data)
    for old in [*data["used_records"], *data["pending"]]:
        duplicate, reason = _duplicate(candidate, old)
        if duplicate:
            raise ValueError(f"Konu tekrarı engellendi ({reason}); yeni konu seçilmeli.")
    entry = {**candidate, "reservation_id": reservation_id, "run_id": run_id}
    data["pending"].append(entry)
    _atomic_write(path, data)
    _write_marker(path, reservation_id, run_id)
    return entry


def reserve_candidate(title: str, metadata: dict[str, Any] | None = None, *, path: Path = DEFAULT_PATH,
                      store: GitHubContentsStore | None = None, reservation_id: str | None = None,
                      run_id: str | None = None) -> dict[str, Any]:
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Boş başlık rezerve edilemez.")
    candidate = _record(title, metadata)
    reservation_id = reservation_id or str(uuid.uuid4())
    run_id = run_id or f"{os.environ.get('GITHUB_RUN_ID', 'local')}:{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    if store is None:
        with _file_lock(path):
            try:
                data = _upgrade(json.loads(path.read_text(encoding="utf-8")))
            except FileNotFoundError:
                data = _upgrade([])
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Konu geçmişi okunamadı; fail-closed ({type(exc).__name__}).") from None
            return _reserve_local(candidate, data, path, reservation_id, run_id)
    for attempt in range(CAS_RETRIES):
        data, sha = store.get()
        data["pending"] = _active_pending(data)
        for old in [*data["used_records"], *data["pending"]]:
            duplicate, reason = _duplicate(candidate, old)
            if duplicate:
                raise ValueError(f"Konu tekrarı engellendi ({reason}); yeni konu seçilmeli.")
        entry = {**candidate, "reservation_id": reservation_id, "run_id": run_id}
        data["pending"].append(entry)
        if store.put(data, sha):
            _atomic_write(path, data)
            _write_marker(path, reservation_id, run_id)
            return entry
        if attempt < CAS_RETRIES - 1:
            time.sleep(min(0.05 * (attempt + 1), 0.25))
    raise RuntimeError("GitHub Contents API SHA çakışması kontrollü yeniden denemelerden sonra da sürdü.")


def _remove_marker(path: Path, reservation_id: str) -> None:
    marker = path.with_name(".topic_reservations.json")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return
    if not isinstance(data, list):
        raise ValueError("Rezervasyon işaretçisi bozuk; fail-closed.")
    _atomic_write(marker, [item for item in data if item.get("reservation_id") != reservation_id])


def finalize_candidate(reservation_id: str, *, commit: bool, path: Path = DEFAULT_PATH,
                       store: GitHubContentsStore | None = None) -> None:
    attempts = CAS_RETRIES if store else 1
    for attempt in range(attempts):
        if store:
            data, sha = store.get()
        else:
            try:
                data = _upgrade(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Konu geçmişi okunamadı; fail-closed ({type(exc).__name__}).") from None
            sha = None
        matches = [item for item in data["pending"] if item.get("reservation_id") == reservation_id]
        if len(matches) != 1:
            raise ValueError("Rezervasyon bulunamadı veya yinelenmiş; geçmiş güvenli biçimde değiştirilmedi.")
        entry = matches[0]
        data["pending"] = [item for item in data["pending"] if item.get("reservation_id") != reservation_id]
        if commit:
            saved = {key: value for key, value in entry.items() if key not in {"reservation_id", "run_id"}}
            data["used_records"].append(saved)
            data["used_records"] = data["used_records"][-1000:]
            data["used_titles"].append(entry["title"])
            data["used_titles"] = data["used_titles"][-1000:]
        if not store or store.put(data, sha):
            _atomic_write(path, data)
            _remove_marker(path, reservation_id)
            return
        if attempt < attempts - 1:
            time.sleep(min(0.05 * (attempt + 1), 0.25))
    raise RuntimeError("GitHub Contents API SHA çakışması finalize sırasında tekrarlandı; fail-closed.")


def load_recent_titles(path: Path = DEFAULT_PATH) -> list[str]:
    try:
        data = _upgrade(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Konu geçmişi okunamadı; fail-closed ({type(exc).__name__}).") from None
    return list(dict.fromkeys(data["used_titles"] + [item["title"] for item in _active_pending(data)]))[-25:]


def make_store_from_environment() -> GitHubContentsStore | None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token and not repository:
        return None
    if not token or not repository:
        raise ValueError("GitHub topic history için token ve repository birlikte gerekli; fail-closed.")
    return GitHubContentsStore(repository, token, ref=os.environ.get("TOPIC_HISTORY_REF", "main"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["finalize"])
    parser.add_argument("--commit", choices=["true", "false"], required=True)
    args = parser.parse_args()
    try:
        store = make_store_from_environment()
        try:
            markers = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            markers = []
        if not isinstance(markers, list):
            raise ValueError("Rezervasyon işaretçisi bozuk; fail-closed.")
        for item in list(markers):
            if not isinstance(item, dict) or not item.get("reservation_id"):
                raise ValueError("Rezervasyon işaretçisi bozuk; fail-closed.")
            finalize_candidate(item["reservation_id"], commit=args.commit == "true", path=DEFAULT_PATH, store=store)
        print(f"[OK] Konu rezervasyonları {'commit edildi' if args.commit == 'true' else 'serbest bırakıldı'}: {len(markers)}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Konu geçmişi finalize edilemedi ({type(exc).__name__}); fail-closed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
