#!/usr/bin/env python3
"""SKILL §8 — Acil durdurma (kill switch).

`.channel_kill_switch.json` aktif olduğunda üretim (daily_shorts) ve pruner
(hourly_pruner) workflow'ları yayın/silme adımlarını atlar. Ayrıca
``logs/run_status.json`` içine ``status: "blocked"`` yazar.

CLI:
  python3 scripts/kill_switch.py gate          # workflow: proceed=true/false yazar
  python3 scripts/kill_switch.py status        # JSON durum döker
  python3 scripts/kill_switch.py block "strike tespit edildi"
  python3 scripts/kill_switch.py clear

Koşullar:
  - blocked kaydı kalıcıdır; yalnız `clear` ile kaldırılır (yanlışlıkla otomatik açılmaz).
  - `gate` çıkışı GitHub Actions `steps.kill.outputs.proceed` ile tüketilir.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SWITCH_PATH = PROJECT_ROOT / ".channel_kill_switch.json"
RUN_STATUS_PATH = PROJECT_ROOT / "logs" / "run_status.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_state() -> dict[str, Any]:
    if not SWITCH_PATH.exists():
        return {"active": False, "reason": None, "updated_at": None}
    try:
        data = json.loads(SWITCH_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"active": False, "reason": None, "updated_at": None}
    if not isinstance(data, dict):
        return {"active": False, "reason": None, "updated_at": None}
    data.setdefault("active", False)
    data.setdefault("reason", None)
    data.setdefault("updated_at", None)
    return data


def is_blocked() -> bool:
    return bool(read_state().get("active"))


def _write_run_status_blocked(reason: str) -> None:
    RUN_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if RUN_STATUS_PATH.exists():
        try:
            existing = json.loads(RUN_STATUS_PATH.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update({
        "status": "blocked",
        "block_reason": reason,
        "blocked_at": _now(),
    })
    RUN_STATUS_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def block(reason: str) -> dict[str, Any]:
    state = {"active": True, "reason": reason or "manual_block", "updated_at": _now()}
    SWITCH_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_run_status_blocked(state["reason"])
    return state


def clear() -> dict[str, Any]:
    state = {"active": False, "reason": None, "updated_at": _now()}
    SWITCH_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description="SKILL §8 kill switch")
    ap.add_argument("command", choices=["gate", "status", "block", "clear"])
    ap.add_argument("reason", nargs="?", default="")
    args = ap.parse_args()

    if args.command == "gate":
        blocked = is_blocked()
        # GitHub Actions çıktı formatı
        print(f"proceed={'false' if blocked else 'true'}")
        print(json.dumps({"blocked": blocked, "reason": read_state().get("reason")}, ensure_ascii=False))
        return 0
    if args.command == "status":
        print(json.dumps(read_state(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "block":
        state = block(args.reason)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clear":
        state = clear()
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
