#!/usr/bin/env python3
"""SKILL §9 — KPI ve başarı metrikleri anlık görüntüsü.

Ağ çağrısı yapmaz; yerel kanıtlardan türetir:
  - logs/published_log.json   : yayınlanan videolar (PUBLIC/draft sayıları, kanal dağılımı)
  - prune_report.json         : son pruner çalışması (silinen, dry_run)
  - analytics_feedback.json    : kazanan niş / boost kararı
  - .used_topics.json         : tekrar korumalı konu havuzu büyüklüğü

Çıktı: logs/kpi_snapshot.json; günlük hedef (varsayılan 5) altında kalınırsa
``target_gap`` pozitif olur ve özet logu uyarı verir (SKILL: tutulmazsa açık raporla).

Kullanım:
  python3 scripts/kpi_snapshot.py [--target 5] [--hours 24] [--out logs/kpi_snapshot.json]
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return fallback


def build_snapshot(
    entries: list[dict[str, Any]],
    prune_report: dict[str, Any] | None,
    analytics: dict[str, Any] | None,
    topics_count: int,
    now: datetime,
    target: int,
    window_hours: int,
) -> dict[str, Any]:
    """Saf hesaplama; test edilebilir çekirdek."""
    cutoff = now - timedelta(hours=window_hours)
    published: list[dict[str, Any]] = []
    for row in entries or []:
        if not isinstance(row, dict):
            continue
        if row.get("status") != "published":
            continue
        ts = _parse_ts(row.get("timestamp"))
        if ts is None or ts < cutoff:
            continue
        published.append(row)

    public_count = sum(1 for r in published if str(r.get("visibility", "")).upper() == "PUBLIC")
    draft_count = sum(1 for r in published if str(r.get("visibility", "")).upper() in ("PRIVATE", "DRAFT", "UNLISTED", ""))
    by_channel = dict(Counter(str(r.get("channel_id", "?")) for r in published))

    prune = prune_report or {}
    analytics = analytics or {}

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "daily_target": target,
        "published_window": len(published),
        "public_window": public_count,
        "non_public_window": draft_count,
        "target_gap": max(0, target - len(published)),
        "by_channel": by_channel,
        "recent_titles": [r.get("title", "") for r in published[-5:]],
        "prune": {
            "started_at": prune.get("started_at"),
            "deleted_count": int(prune.get("deleted_count", 0) or 0),
            "dry_run": bool(prune.get("dry_run", True)),
            "scanned": int(prune.get("scanned", 0) or 0),
        },
        "analytics": {
            "winning_topic": analytics.get("winning_topic"),
            "boost_active": bool(analytics.get("boost_active", False)),
            "outperformance_ratio": analytics.get("outperformance_ratio"),
            "directive": analytics.get("optimization_directive"),
        },
        "topics_used_total": int(topics_count or 0),
        "status": "ok",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="SKILL §9 KPI snapshot")
    ap.add_argument("--target", type=int, default=int(os.getenv("KPI_DAILY_TARGET", "5")))
    ap.add_argument("--hours", type=int, default=int(os.getenv("KPI_WINDOW_HOURS", "24")))
    ap.add_argument("--out", default=str(LOGS_DIR / "kpi_snapshot.json"))
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    published = _load_json(PROJECT_ROOT / "logs" / "published_log.json", [])
    prune = _load_json(PROJECT_ROOT / "prune_report.json", None)
    analytics = _load_json(PROJECT_ROOT / "analytics_feedback.json", None)
    topics_raw = _load_json(PROJECT_ROOT / ".used_topics.json", {})
    topics_count = len(topics_raw.get("used_titles", [])) if isinstance(topics_raw, dict) else 0

    snapshot = build_snapshot(published, prune, analytics, topics_count, now, args.target, args.hours)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    gap = snapshot["target_gap"]
    print(f"[KPI] son {args.hours}s: {snapshot['public_window']} PUBLIC / hedef {args.target} "
          f"(fark={gap}); kanallar={snapshot['by_channel']}; "
          f"prune_silinen={snapshot['prune']['deleted_count']} dry_run={snapshot['prune']['dry_run']}; "
          f"kazanan_nis={snapshot['analytics']['winning_topic']}")
    if gap > 0:
        print(f"[!] GÜNLÜK HEDEF EKSİK: {gap} kısa video hedef altında ({snapshot['published_window']}/{args.target}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
