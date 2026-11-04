#!/usr/bin/env python3
"""Fallback başlıkları ile gerçek Atom anlık görüntüsünü karşılaştırır.

Yalnızca denetim raporudur; yayını engellemez veya yeni açı doğrulamaz.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Bağlaçlar ve genel başlık kalıpları konu eşleşmesini şişirmemelidir.
STOP = frozenset("bir daha kadar sonra sadece tarihin gercek gercegi shorts neden nasil oldu hangi dunyanin uzayda antik yillik milyar".split())


def tokens(text: str) -> set[str]:
    text = text.replace("I", "ı").replace("İ", "i").lower().replace("ı", "i")
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return {word for word in re.findall(r"[a-z]+", text) if len(word) >= 4 and word not in STOP}


def compare(a: str, b: str) -> dict:
    left, right = tokens(a), tokens(b)
    common = left & right
    union = left | right
    return {"jaccard": round(len(common) / len(union), 4) if union else 0.0,
            "common_tokens": sorted(common)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="audit_public_feed.py çıktısı")
    args = parser.parse_args()
    try:
        data = json.loads(args.snapshot.read_text(encoding="utf-8"))
        videos = data["videos"]
        if not isinstance(videos, list):
            raise ValueError("videos liste olmalı")
        from content_engine import FALLBACK_SCENARIOS
        results = []
        for scenario in FALLBACK_SCENARIOS:
            matches = []
            for video in videos:
                match = compare(scenario["title"], video["title"])
                if match["common_tokens"]:
                    matches.append({"video_id": video["video_id"], "published_title": video["title"], **match})
            matches.sort(key=lambda x: (-x["jaccard"], x["video_id"]))
            if matches:
                results.append({"candidate_title": scenario["title"], "best_match": matches[0]})
        results.sort(key=lambda x: (-x["best_match"]["jaccard"], x["candidate_title"]))
        print(json.dumps({"snapshot_captured_at": data["captured_at"], "channel_id": data["channel_id"],
                          "feed_videos": len(videos), "pool_size": len(FALLBACK_SCENARIOS),
                          "limitations": "Başlık token örtüşmesi yalnızca ipucudur; eşanlam, ekler ve yeni açı güvenilir biçimde anlaşılamaz. Eksik akış verisi kaçırılmış tekrar demektir. Otomatik karar verilmez.",
                          "candidates_with_any_title_overlap": results}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, KeyError, TypeError, ValueError, ImportError) as exc:
        print(f"Karşılaştırma başarısız: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
