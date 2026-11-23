#!/usr/bin/env python3
"""BOBI deney kayıt defteri makine yan yazarı (SKILL.md §5.1, §11).

İnsan kararları `docs/experiments.md` içinde tutulur; bu betik yalnız
`logs/experiments.json` mahalli sayaç dosyasını günceller (git ignored).
Amaç: her deney yüklemesinde tek değişkeni ve ölçüt bağını kayda geçirmek,
sonra karar satırını insan dokümanına taşımak.

Kullanım:
    python3 scripts/experiment_ledger.py add --id E1 --variant A \
        --hypothesis "soru hook ilk 3 sn tutmayı artırır" \
        --metric "viewed/swiped ratio; first 1h views" --window 7d \
        --status active --note "3 konuda varyasyon A üretildi"
    python3 scripts/experiment_ledger.py list
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from typing import Any, Iterable

DEFAULT_PATH = pathlib.Path("logs/experiments.json")
VALID_STATUS = {"planned", "active", "measuring", "won", "cut", "paused"}
VALID_FIELDS = {
    "id", "variant", "hypothesis", "variable", "metric", "window",
    "status", "decision", "note", "video_ids", "updated_at",
}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load(path: pathlib.Path) -> dict[str, Any]:
    """Mahalli JSON yükle; dosya yoksa boş şema döner (fail-okuma)."""
    if not path.exists():
        return {"version": 1, "experiments": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "experiments": []}
    if not isinstance(data, dict) or not isinstance(data.get("experiments"), list):
        return {"version": 1, "experiments": []}
    return data


def _key(record: dict[str, Any]) -> tuple[str, str]:
    return (str(record.get("id", "")), str(record.get("variant", "-")))


def upsert(records: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Aynı (id, variant) kaydı varsa üzerine yazar; yoksa ekler. Saf fonksiyon."""
    out = [dict(r) for r in records]
    entry = dict(entry)
    entry.setdefault("updated_at", _now())
    new_key = _key(entry)
    replaced = False
    for idx, rec in enumerate(out):
        if _key(rec) == new_key:
            merged = dict(rec)
            merged.update({k: v for k, v in entry.items() if v not in (None, "")})
            merged["updated_at"] = entry["updated_at"]
            out[idx] = merged
            replaced = True
            break
    if not replaced:
        out.append(entry)
    return out


def validate(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not str(entry.get("id", "")).strip():
        errors.append("id boş olamaz (örnek: E1)")
    if entry.get("status") and entry["status"] not in VALID_STATUS:
        errors.append(f"status geçersiz: {entry['status']}; izinler: {sorted(VALID_STATUS)}")
    unknown = {k for k in entry if k not in VALID_FIELDS}
    if unknown:
        errors.append(f"bilinmeyen alanlar: {sorted(unknown)}")
    return errors


def add(path: pathlib.Path, **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {k: v for k, v in fields.items() if v not in (None, "")}
    entry.setdefault("variant", "-")
    entry.setdefault("status", "planned")
    errors = validate(entry)
    if errors:
        raise ValueError("; ".join(errors))
    data = load(path)
    data["experiments"] = upsert(data["experiments"], entry)
    data["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


def format_list(records: Iterable[dict[str, Any]]) -> str:
    lines = []
    for r in records:
        lines.append(
            f"{r.get('id','?'):>3} [{r.get('status','?'):9}] "
            f"varyant={r.get('variant','-')} pencere={r.get('window','-')} "
            f"karar={r.get('decision','bekliyor')} not={r.get('note','')}"
        )
    return "\n".join(lines) if lines else "(kayıt yok)"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="BOBI deney makine kaydı (docs/experiments.md eşlikli)")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="deney kaydı ekle/güncelle")
    a.add_argument("--id", required=True)
    a.add_argument("--variant", default="-")
    a.add_argument("--hypothesis", default="")
    a.add_argument("--variable", default="")
    a.add_argument("--metric", default="")
    a.add_argument("--window", default="")
    a.add_argument("--status", default="planned")
    a.add_argument("--decision", default="")
    a.add_argument("--note", default="")
    a.add_argument("--path", default=str(DEFAULT_PATH))
    l = sub.add_parser("list", help="kayıtları listele")
    l.add_argument("--path", default=str(DEFAULT_PATH))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = pathlib.Path(args.path)
    if args.cmd == "add":
        try:
            entry = add(
                path,
                id=args.id, variant=args.variant, hypothesis=args.hypothesis,
                variable=args.variable, metric=args.metric, window=args.window,
                status=args.status, decision=args.decision, note=args.note,
            )
        except ValueError as exc:
            print(f"HATA: {exc}", file=sys.stderr)
            return 2
        print(f"OK {entry['id']}/{entry['variant']} -> {path}")
        return 0
    data = load(path)
    print(format_list(data["experiments"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
