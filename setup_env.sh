#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[KURULUM] FFmpeg kuruluyor..."
    sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
fi

if [ ! -d ".venv" ]; then
    echo "[KURULUM] Python sanal ortamı (.venv) oluşturuluyor..."
    python3 -m venv .venv
fi

echo "[KURULUM] Python bağımlılıkları yükleniyor..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
echo "[HAZIR] Ortam başarıyla kuruldu."
