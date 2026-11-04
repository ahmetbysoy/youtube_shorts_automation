#!/usr/bin/env bash
# Uretim kapisi (watchdog).
# schedule (cron) kosusu SADECE bekci: zincir zaten calisiyorsa ikinci bir
# video uretmez. workflow_dispatch (elle/zincir) kosulari her zaman uretir.
# Cikti: "true" (uretebilir) / "false" (atla)
set -uo pipefail

EVENT="${1:-workflow_dispatch}"

if [ "${EVENT}" != "schedule" ]; then
  echo "true"
  exit 0
fi

ACTIVE="$(bash "$(dirname "$0")/active_runs_count.sh" daily_shorts.yml 2>/dev/null || echo 0)"
ACTIVE="${ACTIVE:-0}"

if [ "${ACTIVE}" -gt 0 ]; then
  echo "[BILGI] Aktif zincir kosusu var (${ACTIVE}) -> bu cron kosusu yalnizca bekci, uretim yapilmiyor." >&2
  echo "false"
  exit 0
fi

echo "[BILGI] Aktif zincir kosusu yok -> bu cron kosusu uretimi devraldi." >&2
echo "true"
exit 0
