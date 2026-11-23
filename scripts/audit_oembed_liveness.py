#!/usr/bin/env python3
"""SKILL v5.0 §6.2/§6.6 zorunlu oembed canlılık denetimi.

Ne yapar:
  - logs/published_log.json'daki (ve isteğe bağlı ek ID listesindeki) her videoyu
    YouTube oembed servisiyle yoklar: HTTP 200 = PUBLIC canlı, 404/401 = ölü/görünmez.
  - Sonucu logs/oembed_audit.json'a yazar (kanıt dosyası).
  - Genç (varsayılan <72 saat) bir video ölü ise çıkış kodu 1 -> Actions kırmızı
    yanar, kaza gözden kaçmaz. Eski ölü videolar yalnız raporlanır.

Neden: 2026-11-23 kazası — ledger'daki 13 videodan 12'si pruner/nedeni belirsiz
silmede gitti, kimse fark etmedi (prune_state'e bile düşmediler). Bu skript
artık saatlik pruner zincirinin ve (manuel) gün sonu denetiminin kalıcı adımı.

Kullanım:
  python3 scripts/audit_oembed_liveness.py                    # ledger'dan okur
  python3 scripts/audit_oembed_liveness.py --max-age-hours 72
  python3 scripts/audit_oembed_liveness.py --ids ID1,ID2      # ek ID
  python3 scripts/audit_oembed_liveness.py --quiet            # CI için tek satır
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
LEDGER = BASE / "logs" / "published_log.json"
REPORT = BASE / "logs" / "oembed_audit.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; OembedLivenessAudit/1.0)"}
TIMEOUT = 20


def oembed_check(video_id: str) -> dict:
    """Tek video canlılık sorgusu. 200=canlı, 404/401=ölü, ERR=ölçülemedi."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = Request(url, headers=UA)
        with urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                return {"alive": True, "http": 200}
            return {"alive": False, "http": resp.status}
    except HTTPError as e:
        return {"alive": False, "http": e.code}
    except (URLError, TimeoutError, OSError) as e:
        return {"alive": None, "http": None, "error": type(e).__name__}


def load_ledger_ids(limit: int) -> list[dict]:
    """Ledger kayıtları: {video_id, timestamp}. Yoksa boş liste."""
    if not LEDGER.exists():
        return []
    try:
        raw = json.loads(LEDGER.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    recs = raw if isinstance(raw, list) else raw.get("videos", [])
    out = []
    for r in recs[-limit:]:
        vid = r.get("video_id") or r.get("videoId")
        ts = r.get("timestamp")
        if vid:
            out.append({"video_id": vid, "timestamp": ts})
    return out


def age_hours(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="", help="Virgülle ayrık ek video ID'leri")
    ap.add_argument("--limit", type=int, default=15, help="Ledger'dan son N kayıt")
    ap.add_argument("--max-age-hours", type=float, default=72.0,
                    help="Bu yaştan genç ölü video alarm = çıkış 1")
    ap.add_argument("--quiet", action="store_true", help="CI için tek satır özet")
    args = ap.parse_args()

    entries = load_ledger_ids(args.limit)
    seen = {e["video_id"] for e in entries}
    for extra in filter(None, (s.strip() for s in args.ids.split(","))):
        if extra not in seen:
            entries.append({"video_id": extra, "timestamp": None})
            seen.add(extra)

    if not entries:
        print("oembed-audit: denetlenecek ID yok (ledger boş)")
        return 0

    results = []
    for e in entries:
        vid = e["video_id"]
        res = oembed_check(vid)
        h = age_hours(e.get("timestamp"))
        results.append({
            "video_id": vid,
            "timestamp": e.get("timestamp"),
            "age_hours": round(h, 1) if h is not None else None,
            "alive": res["alive"],
            "http": res["http"],
            "error": res.get("error"),
        })
        time.sleep(0.35)  # kibar ol: oembed'e selam gönder, top ateşleme yapma

    alive_n = sum(1 for r in results if r["alive"] is True)
    dead_n = sum(1 for r in results if r["alive"] is False)
    unknown_n = sum(1 for r in results if r["alive"] is None)
    young_dead = [r for r in results
                  if r["alive"] is False and r["age_hours"] is not None
                  and r["age_hours"] < args.max_age_hours]

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results), "alive": alive_n, "dead": dead_n,
        "unknown": unknown_n, "max_age_hours": args.max_age_hours,
        "young_dead_ids": [r["video_id"] for r in young_dead],
        "results": results,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    if args.quiet:
        print(f"oembed-audit: {alive_n} canlı / {dead_n} ölü / {unknown_n} ölçülemedi "
              f"(genç ölü: {len(young_dead)})")
    else:
        print(f"{'ID':<13}{'yaş(s)':<9}{'durum':<12}başlık-kaynağı")
        for r in results:
            durum = "CANLI" if r["alive"] else ("OLU" if r["alive"] is False else "ölçülemedi")
            yas = r["age_hours"] if r["age_hours"] is not None else "?"
            print(f"{r['video_id']:<13}{str(yas):<9}{durum:<12}HTTP {r['http']}")
        print(f"Özet: {alive_n} canlı / {dead_n} ölü / {unknown_n} ölçülemedi "
              f"-> logs/oembed_audit.json")

    if young_dead and unknown_n < len(results):
        # Bilinçli tasarım: genç ölü = kaza şüphesi, koşu kırmızı dönsün.
        # Ama 'ölçülemedi' (ağ) tek başına alarm açmaz (flaky değil, fail-open ölçüm).
        if unknown_n == 0:
            print(f"ALARM: {args.max_age_hours}s'ten genç {len(young_dead)} video ölü: "
                  f"{[r['video_id'] for r in young_dead]}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
