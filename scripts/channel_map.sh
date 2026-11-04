#!/usr/bin/env bash
# =============================================================================
# Kanal Benzersizlik Analizi (Faz 11 - "kanallari kurmadan" guard)
# -----------------------------------------------------------------------------
# 10 kanal icin ayri YouTube hesabi olup olmadigini tespit eder.
# Ayni hesabi isaret eden kanallar (cookies+storage_state ayni) ayiklanir; aksi
# halde 10 paralel job ayni kanala yukleyip gunluk kotayi 10x harcar.
#
# Girdi (env): C1..C10 (COOKIES_JSON), S1..S10 (STORAGE_STATE_JSON)
# Cikti (GITHUB_OUTPUT): distinct_matrix, next_channel, distinct_count
# -----------------------------------------------------------------------------
set -euo pipefail

hash_of() { printf '%s' "$1" | sha256sum | cut -c1-12; }

declare -A SEEN
ORDER=()

for i in 1 2 3 4 5 6 7 8 9 10; do
  var_c="C${i}"
  var_s="S${i}"
  c="${!var_c:-}"
  s="${!var_s:-}"
  if [ -z "$c" ] || [ -z "$s" ]; then
    echo "[UYARI] Kanal ${i}: secret eksik -> atlandi."
    continue
  fi
  h=$(hash_of "${c}${s}")
  if [ -n "${SEEN[$h]:-}" ]; then
    echo "[AYNI HESAP] Kanal ${i} = Kanal ${SEEN[$h]} (hash ${h}) -> atlandi (gunluk kota korunuyor)."
  else
    SEEN[$h]="$i"
    ORDER+=("$i")
    echo "[AYRI HESAP] Kanal ${i} (hash ${h}) -> uretime dahil."
  fi
done

if [ "${#ORDER[@]}" -eq 0 ]; then
  echo "[UYARI] Ayri hesapli kanal bulunamadi -> yalnizca Kanal 1 kullanilacak."
  ORDER=(1)
fi

# GitHub, "[" ve "{" iceren job output'larini "secret icerebilir" diye ATIYOR.
# Bu yuzden JSON degil, VIRGULLU liste cikartiyoruz; is akisi
# fromJSON('["' + join(distinct_csv, '","') + '"]') ile geri ceviriyor.
MATRIX=$(printf '%s,' "${ORDER[@]}")
MATRIX="${MATRIX%,}"

RUN_NUMBER="${GITHUB_RUN_NUMBER:-1}"
IDX=$(( (RUN_NUMBER - 1) % ${#ORDER[@]} ))
NEXT="${ORDER[$IDX]}"

echo "[*] Benzersiz kanallar: ${ORDER[*]}"
echo "[*] Siradaki kanal (rotasyon ${RUN_NUMBER}): ${NEXT}"

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "distinct_csv=${MATRIX}" >> "$GITHUB_OUTPUT"
  # NOT: JSON array ("[\"1\"]") GitHub tarafindan secret sanilip MASKELENIR
  # ("Skip output ... may contain secret") ve output ATILIR -> matris bos kalir.
  # Bu yuzden output duz string (virgulle) tutulur; workflow tarafinda
  # fromJSON(format('["{0}"]', join(split(distinct_csv, ','), '","'))) ile ARRAY'e cevrilir.
  echo "next_channel=${NEXT}" >> "$GITHUB_OUTPUT"
  echo "distinct_count=${#ORDER[@]}" >> "$GITHUB_OUTPUT"
fi
