#!/usr/bin/env python3
"""SKILL §6 — Yalnız KANAL KENDİ VİDEOLARINA CTA yorumu otomasyonu.

Kapsam kararı (2026-11-23): üçüncü/komşu kanallara yorum ATILMAZ. Yalnız
``logs/published_log.json`` listesinde yayınlanmış kendi video ID'leri için
plan üretir; ``--live`` ile Data API ``commentThreads.insert`` çağrılır.

Güvenlik:
  - Varsayılan ``dry-run``: yalnız planı yazar, hiçbir ağ çağrısı yapmaz.
  - ``--live`` (veya COMMENT_MODE=live) şarttır; OAuth kapsamı
    ``youtube.force-ssl`` yoksa token bozulmadan ``scope_insufficient`` raporlanır.
  - Durum ``logs/comments_state.json``; aynı video iki kez yorum almaz.

Kullanım:
  python3 scripts/auto_pinned_comment.py            # dry-run plan
  python3 scripts/auto_pinned_comment.py --live      # gerçek gönderim
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "logs" / "comments_state.json"
PUBLISHED_LOG = PROJECT_ROOT / "logs" / "published_log.json"
ANALYTICS_FILE = PROJECT_ROOT / "analytics_feedback.json"

DEFAULT_CTA = (
    "Beğen butonuna basmayı ve kanala abone olmayı unutma; her gün bu tarz "
    "belgesel kısa videolar geliyor. Yorumlarda konu hakkındaki fikrini yaz!"
)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _subscribe_url() -> str:
    env_url = os.getenv("SUBSCRIBE_URL", "").strip()
    if env_url:
        return env_url
    try:
        analytics = json.loads(ANALYTICS_FILE.read_text(encoding="utf-8"))
        cid = analytics.get("channel_id")
        if cid:
            return f"https://www.youtube.com/channel/{cid}?sub_confirmation=1"
    except (OSError, json.JSONDecodeError):
        pass
    return ""


def build_comment_text(title: str) -> str:
    url = _subscribe_url()
    base = DEFAULT_CTA
    if url:
        base = f"{base}\nAbone ol: {url}"
    return base


def plan_actions(
    entries: list[dict[str, Any]],
    state: dict[str, Any],
    now: datetime,
    max_per_run: int = 3,
    max_age_days: int = 7,
) -> list[dict[str, Any]]:
    """Saf planlama çekirdeği: yayınlanmış, yeni, çok yaşlı olmayan kendi videoları."""
    commented = set(state.get("commented_video_ids", []) or [])
    cutoff = now - timedelta(days=max_age_days)
    plan: list[dict[str, Any]] = []
    for row in entries or []:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "published":
            continue
        video_id = row.get("video_id")
        if not video_id or video_id in commented:
            continue
        ts = _parse_ts(row.get("timestamp"))
        if ts and ts < cutoff:
            continue
        plan.append({
            "video_id": video_id,
            "title": row.get("title", ""),
            "channel_id": str(row.get("channel_id", "")),
            "text": build_comment_text(str(row.get("title", ""))),
        })
        if len(plan) >= max_per_run:
            break
    return plan


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("commented_video_ids", [])
                data.setdefault("results", [])
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"commented_video_ids": [], "results": []}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _insert_comment_live(plan: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """Canlı gönderim. Kapsam/bağımlılık yoksa (None, reason) döner; hata fırlatmaz."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError as exc:  # pragma: no cover - ortam bağımlılığı
        return [], f"dependency_missing:{type(exc).__name__}"

    token_candidates = [
        PROJECT_ROOT / "token.json",
        PROJECT_ROOT / "secrets" / "youtube_token.json",
        PROJECT_ROOT / "secrets" / "token.json",
    ]
    token_path = next((p for p in token_candidates if p.exists()), None)
    if token_path is None:
        return [], "token_missing"

    try:
        creds = Credentials.from_authorized_user_file(str(token_path))
    except (ValueError, OSError) as exc:
        return [], f"token_invalid:{type(exc).__name__}"

    scopes = set(creds.scopes or [])
    if "https://www.googleapis.com/auth/youtube.force-ssl" not in scopes:
        return [], "scope_insufficient:youtube.force-ssl"

    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    results: list[dict[str, Any]] = []
    for item in plan:
        try:
            resp = service.commentThreads().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": item["video_id"],
                        "topLevelComment": {"snippet": {"textOriginal": item["text"]}},
                    }
                },
            ).execute()
            cid = resp.get("snippet", {}).get("topLevelComment", {}).get("id")
            results.append({"video_id": item["video_id"], "comment_id": cid, "ok": True})
        except HttpError as exc:
            results.append({"video_id": item["video_id"], "ok": False, "error": f"http_{exc.status_code}"})
        except Exception as exc:  # pragma: no cover - ağ/çalışma zamanı
            results.append({"video_id": item["video_id"], "ok": False, "error": type(exc).__name__})
    return results, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Kanal içi CTA yorumu (own-channel only)")
    ap.add_argument("--live", action="store_true", help="Gerçek gönderim (varsayılan: dry-run)")
    ap.add_argument("--max-per-run", type=int, default=int(os.getenv("COMMENT_MAX_PER_RUN", "3")))
    args = ap.parse_args()

    entries = []
    if PUBLISHED_LOG.exists():
        try:
            entries = json.loads(PUBLISHED_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            entries = []

    state = load_state()
    plan = plan_actions(entries, state, datetime.now(timezone.utc), max_per_run=args.max_per_run)
    print(f"[YORUM] Plan: {len(plan)} kendi video adayı (dry-run={'hayır' if args.live else 'evet'}).")
    for item in plan:
        print(f"  - {item['video_id']} :: {item['title'][:70]}")

    if not args.live:
        print("[*] Dry-run: hiçbir yorum gönderilmedi. Canlı için --live kullanın.")
        return 0

    results, reason = _insert_comment_live(plan)
    if reason:
        print(f"[!] Canlı gönderim yapılamadı: {reason}")
        print("[*] Kanal yayın kimliği/storage-state ile Studio yorumu ayrıca ele alınabilir.")
        return 2

    ok_ids = [r["video_id"] for r in results if r.get("ok")]
    state["commented_video_ids"].extend(ok_ids)
    state["results"].extend(results)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print(f"[✓] {len(ok_ids)} yorum gönderildi; durum {STATE_PATH.name} dosyasına yazıldı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
