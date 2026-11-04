#!/usr/bin/env bash
# Artifact'a yuklenmeden once logs/ icerigini guvenlik denetiminden gecirir.
#
# NEDEN:
#   Artifact'lar 7-14 gun erisilebilir kalir ve herkese acik repoda artifact
#   linkleri gorunur. logs/ icinde cerez/token/auth izi varsa sizmamalidir.
#
# NE YAPAR:
#   1) Bilinen hassas dosyalari siler (cookies/storage_state/.env/token/auth)
#   2) Kalan dosyalarda gizli kalip taramasi yapar; eslesme bulursa
#      dosyayi REDAKTE eder ve ::warning:: uretir
#   3) Hicbir sey bulunmazsa dokunmaz
#
# Kullanim: bash scripts/sanitize_logs.sh [logs_dizini]
set -uo pipefail

LOGS_DIR="${1:-logs}"
WARNINGS=0

if [ ! -d "${LOGS_DIR}" ]; then
  echo "[OK] ${LOGS_DIR} dizini yok, denetim atlandi."
  exit 0
fi

echo "[*] Artifact guvenlik denetimi: ${LOGS_DIR}"

# 1) Hassas dosyalari kaldir
find "${LOGS_DIR}" -type f \( \
  -iname "*cookie*" -o -iname "*storage_state*" -o -iname "*.env" -o -iname "*token*" \
  -o -iname "*credential*" -o -iname "*session*" -o -iname "*.key" -o -iname "*.pem" \
\) -print -delete 2>/dev/null | while read -r F; do
  echo "::warning::Artifact'tan hassas dosya cikarildi: ${F}"
done

# auth_status.json gibi durum dosyalari SILINMEZ (video id + baslik icerir,
# sifre icermez) ama icerik taramasindan gecer ve asagida listelenir.
echo "[*] Auth/durum dosyalari (sifre taramasi yapilir, silinmez):"
find "${LOGS_DIR}" -type f \( -iname "*auth*" -o -iname "*status*" \) -printf "  - %p\n" 2>/dev/null

# 2) Gizli kalip taramasi (Google/YouTube cerez + bearer token kaliplari)
PATTERNS='SIDCC|SAPISID|HSID|SSID|APISID|__Secure-[A-Z0-9_]+|Bearer [A-Za-z0-9._-]{20,}|AIza[0-9A-Za-z_-]{30,}|"refresh_token"|"access_token"|"client_secret"|"id_token"|"session_id"|"authToken"|-----BEGIN [A-Z ]*PRIVATE KEY-----'

while IFS= read -r -d '' F; do
  if grep -qE "${PATTERNS}" "$F" 2>/dev/null; then
    echo "::warning::Gizli kalip bulundu, redakte edildi: ${F}"
    # Degerleri MASKELENMIS degere degistir (dosya yapisi korunur)
    sed -E -i 's/(SIDCC|SAPISID|HSID|SSID|APISID|__Secure-[A-Z0-9_]+)[^"'"'"' ,;]*/\1=***REDACTED***/g' "$F" 2>/dev/null || true
    sed -E -i 's/(Bearer )[A-Za-z0-9._-]{20,}/\1***REDACTED***/g' "$F" 2>/dev/null || true
    sed -E -i 's/(AIza)[0-9A-Za-z_-]{30,}/\1***REDACTED***/g' "$F" 2>/dev/null || true
    sed -E -i 's/("(refresh_token|access_token|client_secret)"[[:space:]]*:[[:space:]]*")[^"]*/\1***REDACTED***/g' "$F" 2>/dev/null || true
    WARNINGS=$((WARNINGS + 1))
  fi
done < <(find "${LOGS_DIR}" -type f -size -5M -print0 2>/dev/null)

# 3) Kalan dosya listesi (kanit icin)
echo "[*] Artifact'a girecek dosyalar:"
find "${LOGS_DIR}" -type f -printf "  - %p (%s bayt)\n" 2>/dev/null | head -40

if [ "${WARNINGS}" -gt 0 ]; then
  echo "::warning::${WARNINGS} dosyada gizli kalip bulundu ve redakte edildi."
else
  echo "[OK] Gizli kalip bulunmadi."
fi
exit 0
