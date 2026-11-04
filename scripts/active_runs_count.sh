#!/usr/bin/env bash
# Aktif (queued/in_progress/waiting/requested) kosu sayisini dondurur.
# Kullanim: bash scripts/active_runs_count.sh [workflow_dosya_adi]
# Kendi (GITHUB_RUN_ID) kosumuz sayilmaz.
set -uo pipefail

WORKFLOW="${1:-daily_shorts.yml}"
API="https://api.github.com/repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW}/runs?per_page=30"

if [ -z "${GH_TOKEN:-}" ]; then
  echo 0
  exit 0
fi

curl -s -H "Authorization: Bearer ${GH_TOKEN}" "${API}" \
  | python3 -c '
import json, os, sys

try:
    data = json.load(sys.stdin)
except Exception:
    print(0)
    raise SystemExit(0)

me = os.environ.get("GITHUB_RUN_ID", "")
active = 0
for run in data.get("workflow_runs", []) or []:
    if str(run.get("id")) == me:
        continue
    if run.get("status") in ("queued", "in_progress", "waiting", "requested", "pending"):
        active += 1

print(active)
' 2>/dev/null || echo 0
