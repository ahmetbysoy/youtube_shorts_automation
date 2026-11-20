#!/usr/bin/env python3
"""Artifact yuklemesinden once script.json icindeki secret alanlarini temizle."""
from __future__ import annotations
import json
import sys
from pathlib import Path

SECRET_KEYS = {
    "cookie", "cookies", "token", "secret", "credential", "credentials",
    "api_key", "apikey", "access_token", "refresh_token", "auth",
    "password", "passwd", "private_key",
}


def strip_secrets(obj, depth=0):
    if depth > 10:
        return obj
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SECRET_KEYS:
                continue
            out[k] = strip_secrets(v, depth + 1)
        return out
    if isinstance(obj, list):
        return [strip_secrets(x, depth + 1) for x in obj]
    return obj


def main():
    if len(sys.argv) < 2:
        print("usage: sanitize_script_json.py <path>", file=sys.stderr)
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.exists():
        print(f"[warn] {p} yok")
        sys.exit(0)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[warn] {p} okunamadi: {e}")
        sys.exit(0)
    cleaned = strip_secrets(d)
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {p} icindeki secret alanlari temizlendi.")


if __name__ == "__main__":
    main()
