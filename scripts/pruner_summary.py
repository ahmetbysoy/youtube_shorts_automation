#!/usr/bin/env python3
"""Pruner tek satirlik ozet (Actions logu + Step Summary).

Kullanim: python scripts/pruner_summary.py [prune_report.json]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    report_path = Path(sys.argv[1] if len(sys.argv) > 1 else "prune_report.json")
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception as exc:
            data = {"error": str(exc)}
    else:
        data = {}

    channel = data.get("channel_id", "?")
    scanned = data.get("scanned", "?")
    deleted = len(data.get("deleted") or [])
    protected = len(data.get("protected") or [])
    line = f"Pruner Kanal {channel}: tarama {scanned} | silinen {deleted} | korunan {protected}"

    print(f"::notice::{line}")
    print(line)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write("\n### Temizlik Özeti\n\n")
                fh.write(f"{line}\n\n")
        except Exception as exc:  # pragma: no cover
            print(f"[!] Step summary yazilamadi: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
