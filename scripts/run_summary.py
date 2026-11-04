#!/usr/bin/env python3
"""Run durum ozeti -> tek satirlik bildirim + GitHub Step Summary.

Kullanim: python scripts/run_summary.py [logs/run_status.json]

NEDEN:
  Ayşe'nin onerisi: "Her run sonunda tek satirlık bildirim at: Kanal 2:
  yüklendi / kota / iptal. Böylece Actions sayfasında kaybolmadan telefondan bakarsın."
  -> hem Actions loguna (::notice::) hem de run ozeti sekmesine (markdown) yazar.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STATUS_LABEL = {
    "uploaded": "YÜKLENDİ",
    "quota_skipped": "KOTA - ATLANDI",
    "error": "HATA",
    "started": "DEVAM EDİYOR",
}


def main() -> int:
    status_path = Path(sys.argv[1] if len(sys.argv) > 1 else "logs/run_status.json")
    data: dict = {}
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover
            data = {"status": f"parse_error: {exc}"}

    status = str(data.get("status") or "unknown")
    channel = str(data.get("channel_id") or "?")
    video_id = str(data.get("video_id") or "")
    url = str(data.get("url") or (f"https://youtube.com/shorts/{video_id}" if video_id else ""))
    title = str(data.get("title") or "")
    label = STATUS_LABEL.get(status, status.upper())

    line = f"Kanal {channel}: {label}"
    if video_id:
        line += f" | Video: {video_id}"
    if url:
        line += f" | {url}"
    if title:
        line += f" | {title}"

    print(f"::notice::{line}")
    print(line)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write("\n## YouTube Shorts Üretim Özeti\n\n")
                fh.write("| Kanal | Durum | Video | Başlık |\n")
                fh.write("| :--- | :--- | :--- | :--- |\n")
                fh.write(f"| {channel} | {label} | {video_id or '-'} | {title or '-'} |\n\n")
                if url:
                    fh.write(f"**Video:** {url}\n\n")
        except Exception as exc:  # pragma: no cover
            print(f"[!] Step summary yazilamadi: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
