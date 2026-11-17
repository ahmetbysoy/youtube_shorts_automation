#!/usr/bin/env python3
"""script.json için üretim öncesi fail-closed JSON Schema doğrulayıcısı."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = BASE_DIR / "schemas" / "script.schema.json"


def validate_payload(payload: Any, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    """Payload hatalarını insan tarafından okunabilir metinler olarak döndürür."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(map(str, err.absolute_path)))
    return [
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="script.json JSON Schema doğrulayıcısı")
    parser.add_argument("--input", default=str(BASE_DIR / "script.json"), help="Doğrulanacak JSON dosyası")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="JSON Schema dosyası")
    args = parser.parse_args()

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        errors = validate_payload(payload, Path(args.schema))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"[SCRIPT_JSON][FAIL] Dosya/şema okunamadı veya geçersiz: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"[SCRIPT_JSON][FAIL] {len(errors)} şema hatası bulundu:", file=sys.stderr)
        for error in errors[:30]:
            print(f"  - {error}", file=sys.stderr)
        return 1

    version = payload.get("schema_version", "legacy-v1") if isinstance(payload, dict) else "unknown"
    print(f"[SCRIPT_JSON][OK] {args.input} doğrulandı (schema={version}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
