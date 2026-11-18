"""Security-only helpers for publication-free media probes, never production setup.

ENV_FILE is dotenv DATA, with interpolation disabled. Only the two exact runtime
stock-key names may leave the parser, in memory and addressed to one provider.
No sourcing, eval, secret mutation, alias guessing or cookie refresh is allowed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

STOCK_KEYS = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}
STOCK_DOMAINS = {"pexels.com", "www.pexels.com", "pixabay.com", "www.pixabay.com"}
SECRET_PATTERN = re.compile(rb"(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{30,}")


@dataclass
class ProviderConfiguration:
    presence: dict
    _keys: dict[str, str] = field(repr=False)

    def key_for(self, provider: str) -> str:
        return self._keys[provider]


def consume_provider_configuration(environ=None) -> ProviderConfiguration:
    environ = os.environ if environ is None else environ
    raw = environ.pop("PHASE4_PROVIDER_ENV", "")
    parsed = dotenv_values(stream=StringIO(raw), interpolate=False) if raw else {}
    keys, presence = {}, {"env_file_supplied": bool(raw), "interpolation_enabled": False, "providers": {}}
    for provider, name in STOCK_KEYS.items():
        direct = environ.pop(name, "") or ""
        from_file = parsed.get(name) or ""
        effective = (direct or from_file).strip()
        placeholder = any(marker in effective.lower() for marker in ("your_", "senin_gercek"))
        keys[provider] = effective if effective and not placeholder else ""
        # Only booleans: never the key, its length, prefix, suffix or hash.
        presence["providers"][provider] = {
            "direct_name_supplied": bool(direct), "allowlisted_env_name_present": bool(from_file),
            "placeholder_detected": placeholder, "api_key_present": bool(keys[provider]),
        }
    return ProviderConfiguration(presence, keys)


def prepare_media_cookies(path: Path, raw: str) -> dict:
    if path.exists():
        raise ValueError("probe_refuses_to_overwrite_existing_cookie_file")
    if not raw:
        return {"secret_supplied": False, "stock_cookie_file_created": False}
    data = json.loads(raw)
    data = data.get("cookies", []) if isinstance(data, dict) else data
    if not isinstance(data, list):
        raise ValueError("media_cookie_payload_invalid")
    allowed_fields = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    cookies = [{k: v for k, v in c.items() if k in allowed_fields} for c in data if isinstance(c, dict)
               and str(c.get("domain", "")).lstrip(".").lower() in STOCK_DOMAINS]
    if cookies:
        # Exclusive creation + mode 0600; no Google/YouTube sessions are written.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(cookies, handle)
    return {"secret_supplied": True, "stock_cookie_file_created": bool(cookies)}


def cookie_only_preflight(path: Path, raw: str, *, api_presence: dict | None = None) -> dict:
    """No API credential is read/required. Counts are matching-cookie counts.

    Secret material stays in memory or an exclusive 0600 ephemeral cookie file;
    the RETURN VALUE is safe booleans/counts/fixed status codes only.
    """
    api_presence = {} if api_presence is None else api_presence
    result = {"access_mode": "cookie_only", "status": "failed", "media_cookies_secret_present": bool(raw),
        "pexels_api_key_present": api_presence.get("pexels") is True, "pixabay_api_key_present": api_presence.get("pixabay") is True,
        "api_presence_scope": "direct_repository_secret_names_boolean_only" if api_presence else "not_supplied_to_cookie_only_preflight",
        "api_credentials_evaluated": False, "api_credentials_loaded": False, "env_file_read": False,
        "pexels_cookie_domain_count": 0, "pixabay_cookie_domain_count": 0,
        "stock_cookie_file_created": False, "missing_configuration": []}
    created = False
    try:
        if not raw:
            result["missing_configuration"] = ["MEDIA_COOKIES_JSON"]; return result
        data = json.loads(raw)
        data = data.get("cookies") if isinstance(data, dict) else data
        if not isinstance(data, list): raise ValueError("invalid_cookie_json")
        allowed = {"pexels.com", "www.pexels.com", ".pexels.com", "pixabay.com", "www.pixabay.com", ".pixabay.com"}
        fields = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
        rows = []; identities = {}
        for row in data:
            if not isinstance(row, dict): raise ValueError("invalid_cookie_json")
            domain = row.get("domain")
            if not isinstance(domain, str) or domain.lower() not in allowed: continue
            c = {k: v for k, v in row.items() if k in fields}; c["domain"] = domain.lower(); c.setdefault("path", "/")
            if not isinstance(c.get("name"), str) or not c["name"] or not isinstance(c.get("value"), str): raise ValueError("invalid_cookie_json")
            if not isinstance(c["path"], str) or not c["path"].startswith("/"): raise ValueError("invalid_cookie_json")
            if any(ord(ch) < 32 or ord(ch) == 127 for key in ("name", "value", "path") for ch in c[key]): raise ValueError("invalid_cookie_json")
            if any(key in c and type(c[key]) is not bool for key in ("secure", "httpOnly")): raise ValueError("invalid_cookie_json")
            if "expires" in c and (type(c["expires"]) not in (int, float) or not -1 <= c["expires"] < 10**12): raise ValueError("invalid_cookie_json")
            if "sameSite" in c:
                value = c["sameSite"]
                normalized = {"strict": "Strict", "lax": "Lax", "none": "None", "no_restriction": "None"}.get(value.lower() if isinstance(value, str) else "")
                if normalized is None: raise ValueError("invalid_cookie_json")
                c["sameSite"] = normalized
            identity = c["domain"], c["path"], c["name"]
            if identity in identities:
                if identities[identity] != c: raise ValueError("conflicting_cookie_rows")
                continue
            identities[identity] = c; rows.append(c)
        for provider in ("pexels", "pixabay"):
            result[provider+"_cookie_domain_count"] = sum(c["domain"].lstrip(".").removeprefix("www.") == provider+".com" for c in rows)
        if not all(result[p+"_cookie_domain_count"] for p in ("pexels", "pixabay")):
            result["missing_configuration"] = ["MEDIA_COOKIES_JSON"]; return result
        if path.exists(): raise ValueError("cookie_path_already_exists")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(fd, "w") as handle: json.dump(rows, handle)
        result.update(status="passed", stock_cookie_file_created=True)
    except Exception:
        if created: path.unlink(missing_ok=True)
        # Never serialize parser/Playwright messages, cookie names or values.
        result["error_class"] = "invalid_cookie_configuration"
        result["invalid_configuration"] = ["MEDIA_COOKIES_JSON"]
    return result


def _audit_values(environ) -> list[bytes]:
    """Compare available secret material IN MEMORY, with no value output."""
    values = []
    for name in ("PHASE4_PROVIDER_ENV", "AUDIT_PROVIDER_ENV"):
        raw = environ.get(name, "")
        if raw:
            for key, value in dotenv_values(stream=StringIO(raw), interpolate=False).items():
                if value and re.search(r"key|token|password|cookie|secret", key, re.I):
                    values.append(value)
    for name in (*STOCK_KEYS.values(), "GITHUB_TOKEN", "GH_TOKEN"):
        if environ.get(name): values.append(environ[name])
    raw = environ.get("MEDIA_COOKIES_JSON", "")
    if raw:
        data = json.loads(raw)
        data = data.get("cookies", []) if isinstance(data, dict) else data
        values.extend(str(c.get("value", "")) for c in data if isinstance(c, dict))
    return [value.encode() for value in values if len(value) >= 8]


def _check_urls(value):
    if isinstance(value, dict):
        for item in value.values(): _check_urls(item)
    elif isinstance(value, list):
        for item in value: _check_urls(item)
    elif isinstance(value, str):
        # Credits/descriptions can embed a URL inside prose as well as in a URL
        # field. Signed parameters must not escape through those text fields.
        for url in re.findall(r'https?://[^\s<>"\)]+', value):
            p = urlsplit(url.rstrip(";,."))
            if p.query or p.fragment or p.username or p.password:
                raise ValueError("artifact_contains_query_or_credential_bearing_url")


def audit_artifacts(root: Path, environ=None) -> dict:
    values = _audit_values(os.environ if environ is None else environ)
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError("no_probe_evidence_to_audit")
    records = []
    for path in files:
        if path.is_symlink() or path.suffix not in {".json", ".mp4", ".jpg"} or any(x in path.name.lower() for x in ("cookie", ".env", "storage_state")):
            raise ValueError("artifact_file_not_allowlisted")
        raw = path.read_bytes()
        if SECRET_PATTERN.search(raw) or any(value in raw for value in values):
            raise ValueError("artifact_secret_audit_failed")
        if path.suffix == ".json": _check_urls(json.loads(raw))
        records.append({"path": str(path.relative_to(root)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return {"status": "passed", "known_secret_matches": 0, "credential_pattern_matches": 0,
            "url_query_or_credentials_matches": 0, "files": records}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("operation", choices=["cookies", "preflight", "audit"])
    ap.add_argument("--path", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    try:
        if args.operation == "preflight":
            # Actions evaluates these two booleans WITHOUT passing key values.
            presence = {p: os.environ.pop(p.upper()+"_API_KEY_PRESENT", "false").lower() == "true" for p in STOCK_KEYS}
            result = cookie_only_preflight(args.path, os.environ.pop("MEDIA_COOKIES_JSON", ""), api_presence=presence)
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(result, indent=2)+"\n")
            print("PHASE4C_PREFLIGHT="+json.dumps(result))
            return 0 if result["status"] == "passed" else 1
        if args.operation == "cookies":
            result = prepare_media_cookies(args.path, os.environ.pop("MEDIA_COOKIES_JSON", ""))
            print("MEDIA_COOKIE_CONFIGURATION="+json.dumps(result))
        else:
            result = audit_artifacts(args.path)
            # Audit report contains only file hashes/counts, never secret hashes.
            (args.path/"artifact_audit.json").write_text(json.dumps(result, indent=2)+"\n")
            audit_artifacts(args.path)
            print("Evidence credential audit passed.")
    except Exception as exc:
        print("PROBE_SECURITY_FAILURE="+type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
