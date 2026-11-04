#!/usr/bin/env python3
"""Gerçek Atom akışı ve Studio pruner raporundan kaynaklı gözlem geçmişi üretir.

Çıktı kanıtların birleşimidir, tam kanal geçmişi değildir. `observed_at` yayın
zamanı değildir. Bu araç üretim akışına bağlı değildir ve değişiklik yapmaz.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
VIDEO = re.compile(r"[A-Za-z0-9_-]{11}\Z")


def timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Zaman bilgisi metin değil")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Zaman dilimi olmayan tarih")
    return dt


def validated_id(value: object, pattern: re.Pattern, kind: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"Geçersiz {kind}")
    return value


def build_history(feed: dict, report: dict) -> dict:
    """Kanal kimliği eşleşen kayıtları video ID ile birleştir, kaynağı koru."""
    channel_id = validated_id(feed.get("channel_id"), CHANNEL, "akış kanalı")
    if report.get("channel_id") != channel_id:
        raise ValueError("Akış ve Studio raporunun kanal kimlikleri farklı")
    feed_time = timestamp(feed.get("captured_at"))
    report_time = timestamp(report.get("finished_at"))
    feed_videos = feed.get("videos")
    if not isinstance(feed_videos, list) or feed.get("count") != len(feed_videos):
        raise ValueError("Akış video listesi veya sayısı geçersiz")
    observations: dict[str, list[dict]] = {}
    seen_feed: set[str] = set()
    for video in feed_videos:
        video_id = validated_id(video.get("video_id"), VIDEO, "akış video kimliği")
        if video_id in seen_feed:
            raise ValueError("Akışta tekrarlı video kimliği")
        seen_feed.add(video_id)
        title = video.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Akış başlığı eksik")
        published = video.get("published")
        if timestamp(published) > feed_time:
            raise ValueError("Akış yayın tarihi gözlem tarihinden sonra")
        observations.setdefault(video_id, []).append({
            "source": "youtube_atom", "observed_at": feed["captured_at"],
            "title": title, "published_at": published,
        })
    # report.deleted öğeleri de kanalın Studio raporundan gelir. Tekrarlı ID,
    # örneğin hem target hem deleted, farklı durumlar olarak korunur.
    for group in ("protected", "targets", "deleted"):
        items = report.get(group, [])
        if not isinstance(items, list):
            raise ValueError(f"Studio raporu {group} liste değil")
        for video in items:
            if not isinstance(video, dict):
                raise ValueError("Studio kaydı nesne değil")
            video_id = validated_id(video.get("videoId"), VIDEO, "Studio video kimliği")
            title = video.get("title")
            if not isinstance(title, str) or not title.strip():
                raise ValueError("Studio video başlığı eksik")
            observations.setdefault(video_id, []).append({
                "source": "studio_pruner_report", "observed_at": report["finished_at"],
                "title": title, "report_group": group,
            })
    records = []
    for video_id, obs in observations.items():
        obs.sort(key=lambda x: timestamp(x["observed_at"]))
        records.append({"video_id": video_id, "latest_observed_title": obs[-1]["title"],
                        "observations": obs})
    records.sort(key=lambda x: x["video_id"])
    return {
        "channel_id": channel_id,
        "feed_captured_at": feed["captured_at"],
        "report_finished_at": report["finished_at"],
        "report_errors": report.get("errors", []),
        "limitations": "Yalnızca iki anlık görüntüde gözlemlenen kayıtlar; tam yayın geçmişi değildir. Studio gözlem zamanı yayın tarihi değildir. Durumlar zaman içinde değişebilir.",
        "record_count": len(records),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feed", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        feed = json.loads(args.feed.read_text(encoding="utf-8"))
        report = json.loads(args.report.read_text(encoding="utf-8"))
        print(json.dumps(build_history(feed, report), ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ValueError, TypeError, AttributeError) as exc:
        print(f"Gözlem geçmişi oluşturulamadı: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
