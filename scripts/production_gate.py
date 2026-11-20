#!/usr/bin/env python3
"""Production gate — Faz C safety controller.

Her üretim çalışmasından önce çağrılır. Aşağıdaki kontrolleri yapar,
herhangi biri RED ise üretimi durdurur (exit 0 = skip değil, exit 2 = gracefully skip
with reason — workflow "if: gate passed" şeklinde devam eder):

  1. EMERGENCY STOP: "EMERGENCY_STOP" etiketli açık issue var mı?
  2. COOKIE SAĞLIK: PEXELS_COOK / PIXABAY_COOK / GEMINI_COOK / YT cookie
     ortamda mevcut mu, minimum uzunlukta mı?
  3. GÜNLÜK KOTA: bugün yüklenen video sayısı < DAILY_LIMIT mi?
     (logs/published_log.json içinden sayar)
  4. SON YÜKLEME ARALIĞI: son yüklemeden MIN_SPACING_MINUTES geçti mi?
  5. ARDIŞIK HATA FRENİ: son N hata sayısı < MAX_CONSECUTIVE_ERRORS mi?

Kullanım:
  python scripts/production_gate.py [--daily-limit 8] [--min-spacing 60]
Çıktı: JSON olarak gate_result, exit code:
  0 = üretime izin var (continue)
  2 = bu tur atlanmalı (reason belirtilir)
  1 = içsel hata (kapı kendisi bozuldu)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BASE_DIR / "logs"
PUBLISHED_LOG = LOG_DIR / "published_log.json"
RUN_STATUS = LOG_DIR / "run_status.json"
ERROR_LOG = LOG_DIR / "error_log.json"

# Varsayılanlar Faz C hedefine gore
DAILY_LIMIT_DEFAULT = 8
MIN_SPACING_MINUTES_DEFAULT = 60
MAX_CONSECUTIVE_ERRORS = 3


def log_line(level: str, msg: str) -> None:
    print(f"[gate][{level}] {msg}", file=sys.stderr)


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log_line("warn", f"{path.name} okunamadi: {e}")
    return default


def check_emergency_stop() -> tuple[bool, str]:
    """GitHub issue ile acil durdurma.

    EMERGENCY_STOP secret'i "1" ise veya STOP file varsa dur.
    (GitHub issue label kontrolu ayri bir script tarafindan STOP file'a yazilir,
    dogrudan API cagrisi PAT gerektirir.)
    """
    if os.environ.get("EMERGENCY_STOP", "").strip() in ("1", "true", "TRUE", "stop"):
        return False, "EMERGENCY_STOP secret set"
    stop_file = BASE_DIR / ".emergency_stop"
    if stop_file.exists():
        reason = stop_file.read_text(encoding="utf-8").strip()[:200] or "stop file present"
        return False, f"stop file: {reason}"
    return True, ""


def check_cookies_present() -> tuple[bool, str]:
    """Tum gerekli cookie'lerin varligini ve minimum uzunlugunu kontrol et."""
    required = {
        "GEMINI_COOK": 50,
        "PEXELS_COOK": 50,
        "PIXABAY_COOK": 50,
    }
    # YouTube cookie: COOKIES_JSON veya YT_EMAIL+YT_PASSWORD veya COOKIES_JSON_1
    yt_ok = False
    for v in ("COOKIES_JSON", "COOKIES_JSON_1", "STORAGE_STATE_JSON",
              "STORAGE_STATE_JSON_1"):
        if len(os.environ.get(v, "").strip()) > 50:
            yt_ok = True
            break
    if not yt_ok:
        # Email/sifre ile auth da kabul
        if os.environ.get("YT_EMAIL") and os.environ.get("YT_PASSWORD"):
            yt_ok = True
    if not yt_ok:
        return False, "YouTube cookie/giris bilgisi eksik"
    for name, min_len in required.items():
        v = os.environ.get(name, "").strip()
        if len(v) < min_len:
            return False, f"{name} eksik/çok kısa ({len(v)} chars)"
    return True, ""


def count_today_published() -> int:
    """Bugun UTC olarak kac video yayinlandigini say."""
    log = _load_json(PUBLISHED_LOG, [])
    if not isinstance(log, list):
        log = []
    today = datetime.now(timezone.utc).date()
    count = 0
    for entry in log:
        try:
            ts = entry.get("timestamp") or entry.get("published_at") or ""
            if not ts:
                continue
            d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
            if d == today and entry.get("status") == "published":
                count += 1
        except Exception:
            continue
    return count


def check_daily_budget(limit: int) -> tuple[bool, str, int]:
    n = count_today_published()
    if n >= limit:
        return False, f"daily budget dolu: {n}/{limit}", n
    return True, "", n


def check_spacing(min_minutes: int) -> tuple[bool, str, str]:
    """Son yayindan bu yana min_minutes dk gecti mi?"""
    log = _load_json(PUBLISHED_LOG, [])
    if not isinstance(log, list):
        return True, "", ""  # log yok, ilk uretim
    published = [e for e in log if e.get("status") == "published" and e.get("timestamp")]
    if not published:
        return True, "", ""
    last = max(published, key=lambda e: e["timestamp"])
    try:
        last_ts = datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00"))
    except Exception:
        return True, "", ""
    now = datetime.now(timezone.utc)
    elapsed = (now - last_ts).total_seconds() / 60.0
    if elapsed < min_minutes:
        remaining = int(min_minutes - elapsed + 1)
        return False, f"son yüklemeden {int(elapsed)} dk geçti, {remaining} dk beklenmeli", last["timestamp"]
    return True, "", last["timestamp"]


def check_consecutive_errors(max_err: int) -> tuple[bool, str, int]:
    """Son calismalardaki ardışık hata sayisi."""
    err_log = _load_json(ERROR_LOG, [])
    if not isinstance(err_log, list):
        return True, "", 0
    recent = err_log[-max_err:]
    consecutive = 0
    for e in reversed(recent):
        if e.get("status") == "error":
            consecutive += 1
        else:
            break
    # Yeni gun ise sayaci sifirla (son hata 2 saatten eskiyse sayma)
    if recent and recent[-1].get("timestamp"):
        try:
            ts = datetime.fromisoformat(recent[-1]["timestamp"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - ts) > timedelta(hours=2):
                consecutive = 0
        except Exception:
            pass
    if consecutive >= max_err:
        return False, f"ardisik {consecutive} hata - fren", consecutive
    return True, "", consecutive


def record_result(status: str, **extra) -> None:
    """Run sonucunu logla."""
    LOG_DIR.mkdir(parents=True, exist_ok_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
    }
    entry.update(extra)
    # error log
    err_log = _load_json(ERROR_LOG, [])
    if not isinstance(err_log, list):
        err_log = []
    err_log.append(entry)
    # son 50 kaydi tut
    err_log = err_log[-50:]
    ERROR_LOG.write_text(json.dumps(err_log, ensure_ascii=False, indent=2), encoding="utf-8")
    # published log
    if status == "published":
        pub = _load_json(PUBLISHED_LOG, [])
        if not isinstance(pub, list):
            pub = []
        pub.append(entry)
        pub = pub[-200:]
        PUBLISHED_LOG.write_text(json.dumps(pub, ensure_ascii=False, indent=2), encoding="utf-8")


def cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-limit", type=int, default=DAILY_LIMIT_DEFAULT)
    ap.add_argument("--min-spacing", type=int, default=MIN_SPACING_MINUTES_DEFAULT)
    ap.add_argument("--max-errors", type=int, default=MAX_CONSECUTIVE_ERRORS)
    ap.add_argument("--record", choices=["published", "error", "skipped", "ok"], default=None,
                    help="Bu calismanin sonucunu kaydet (publish/error/skip/ok).")
    ap.add_argument("--check", action="store_true", default=True,
                    help="Sadece kapiyi kontrol et ve sonucu JSON olarak yazdir.")
    args = ap.parse_args()

    if args.record:
        record_result(args.record)
        print(json.dumps({"recorded": args.record}, ensure_ascii=False))
        return 0

    # Kontroller
    result = {"allow": False, "reasons": [], "metrics": {}}

    ok, reason = check_emergency_stop()
    if not ok:
        result["reasons"].append(f"emergency_stop: {reason}")
    result["metrics"]["emergency_stop"] = not ok

    ok, reason = check_cookies_present()
    if not ok:
        result["reasons"].append(f"cookies: {reason}")
    result["metrics"]["cookies_ok"] = ok

    ok, reason, today_count = check_daily_budget(args.daily_limit)
    if not ok:
        result["reasons"].append(f"daily_budget: {reason}")
    result["metrics"]["today_published"] = today_count
    result["metrics"]["daily_limit"] = args.daily_limit

    ok, reason, last_ts = check_spacing(args.min_spacing)
    if not ok:
        result["reasons"].append(f"spacing: {reason}")
    result["metrics"]["last_published"] = last_ts
    result["metrics"]["min_spacing_minutes"] = args.min_spacing

    ok, reason, err_count = check_consecutive_errors(args.max_errors)
    if not ok:
        result["reasons"].append(f"consecutive_errors: {reason}")
    result["metrics"]["consecutive_errors"] = err_count

    result["allow"] = len(result["reasons"]) == 0
    result["timestamp"] = datetime.now(timezone.utc).isoformat()

    # GitHub_OUTPUT'a yaz (workflow step output'u olarak)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"allow={'true' if result['allow'] else 'false'}\n")
            f.write(f"result_json={json.dumps(result, ensure_ascii=False)}\n")

    # Ekrana da yaz
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["allow"]:
        log_line("ok", f"production allowed (today={today_count}/{args.daily_limit} consecutive_errors={err_count})")
        return 0
    else:
        log_line("skip", "üretim atlandi: " + "; ".join(result["reasons"]))
        return 2  # graceful skip (not error)


if __name__ == "__main__":
    sys.exit(cli())
