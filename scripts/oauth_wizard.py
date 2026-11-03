#!/usr/bin/env python3
"""
Canlı OAuth 2.0 Kurulum ve Doğrulama Sihirbazı (0.0.0.0:8080)
Kullanıcının kendi tarayıcısından indirdiği `client_secret.json` dosyasını güvenle yükleyip
tek tıkla OAuth onay URL'si üretmesini, yönlendirme kodunu takas ederek gerçek `token.json`
oluşturmasını ve maskelenmiş raporu almasını sağlar.
"""

from __future__ import annotations

import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.youtube_upload.oauth_handler import YouTubeOAuthHandler  # noqa: E402

HTML_PAGE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>YouTube OAuth 2.0 Canlı Kurulum Sihirbazı — Ramazan</title>
<style>
  :root {
    --bg: #0b1120;
    --card: #111827;
    --border: #1f2937;
    --accent: #ef4444;
    --accent-hover: #dc2626;
    --ok: #10b981;
    --text: #f3f4f6;
    --muted: #9ca3af;
    --code-bg: #030712;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
  }
  .container { max-width: 860px; margin: 0 auto; }
  h1 { margin: 0 0 6px; font-size: 22px; display: flex; align-items: center; gap: 10px; }
  .badge {
    font-size: 12px; padding: 3px 10px; border-radius: 999px;
    background: rgba(239,68,68,0.18); color: #fca5a5; border: 1px solid rgba(239,68,68,0.4);
  }
  .sub { color: var(--muted); font-size: 14px; margin-bottom: 20px; }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 16px;
  }
  .card h2 { margin: 0 0 10px; font-size: 16px; color: #fff; }
  .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
  .link-btn {
    display: block; text-decoration: none; color: var(--text);
    background: #1e293b; border: 1px solid #334155; padding: 10px 12px;
    border-radius: 8px; font-size: 13px; font-weight: 600; text-align: center;
  }
  .link-btn:hover { border-color: #60a5fa; background: #26354d; }
  textarea, input[type="text"] {
    width: 100%; background: var(--code-bg); color: var(--text);
    border: 1px solid #374151; border-radius: 8px; padding: 10px 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px;
  }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
  button {
    background: var(--accent); color: #fff; border: none; border-radius: 8px;
    padding: 10px 16px; font-size: 13px; font-weight: 600; cursor: pointer;
  }
  button:hover { background: var(--accent-hover); }
  button.secondary { background: #2563eb; }
  button.secondary:hover { background: #1d4ed8; }
  pre {
    background: var(--code-bg); border: 1px solid #1f2937; border-radius: 8px;
    padding: 12px; overflow-x: auto; font-size: 12.5px; color: #d1d5db;
    white-space: pre-wrap; word-break: break-all;
  }
  .status-pill { font-size: 13px; font-weight: 600; }
  .ok { color: var(--ok); }
  .warn { color: #fbbf24; }
  .err { color: #f87171; }
  .file-drop {
    border: 2px dashed #374151; border-radius: 8px; padding: 14px;
    text-align: center; margin-bottom: 10px; cursor: pointer; font-size: 13px; color: var(--muted);
  }
  .file-drop:hover { border-color: #60a5fa; color: #fff; }
</style>
</head>
<body>
<div class="container">
  <h1>YouTube OAuth 2.0 Canlı Sihirbazı <span class="badge">Ramazan Dev Engine</span></h1>
  <div class="sub">
    Google Cloud güvenlik duvarı (2FA / Oturum) nedeniyle <code>client_secret.json</code> yalnızca senin Google oturumun açık tarayıcından indirilebilir.
    Aşağıdaki 3 adımla 60 saniyede gerçek <code>token.json</code> üretilir.
  </div>

  <div class="card">
    <h2>Adım 1 — Google Cloud Console Hızlı Kısayolları (Kendi Tarayıcında Açılır)</h2>
    <div class="links">
      <a class="link-btn" target="_blank" rel="noopener" href="https://console.cloud.google.com/projectcreate">1. Proje Aç (YoutubeShortsAutoBot) ↗</a>
      <a class="link-btn" target="_blank" rel="noopener" href="https://console.cloud.google.com/apis/library/youtube.googleapis.com">2. YouTube Data API v3 Enable ↗</a>
      <a class="link-btn" target="_blank" rel="noopener" href="https://console.cloud.google.com/apis/credentials/consent">3. OAuth Consent & Test Users ↗</a>
      <a class="link-btn" target="_blank" rel="noopener" href="https://console.cloud.google.com/apis/credentials/oauthclient">4. Desktop App JSON İndir ↗</a>
    </div>
  </div>

  <div class="card">
    <h2>Adım 2 — İndirdiğin <code>client_secret.json</code> Dosyasını Yükle & Onay Linki Üret</h2>
    <label class="file-drop" for="secretFile">
      📁 Tıkla ve indirdiğin <code>client_secret_...json</code> dosyasını seç (veya aşağıya içeriğini yapıştır)
      <input type="file" id="secretFile" accept=".json,application/json" style="display:none" />
    </label>
    <textarea id="secretJson" rows="4" placeholder='{"installed":{"client_id":"...","project_id":"...","client_secret":"..."}}'></textarea>
    <div class="row">
      <button onclick="saveSecretAndGenerateUrl()">JSON Kaydet & Google Onay URL'si Üret</button>
      <span id="step2Status" class="status-pill"></span>
    </div>
    <div id="authUrlBox" style="display:none; margin-top:12px;">
      <div style="font-size:13px; margin-bottom:6px; color:#93c5fd;">
        <strong>Onay URL'si Hazır!</strong> (PM'e bu URL'yi verebilir veya doğrudan tıklayıp onaylayabilirsin):
      </div>
      <pre id="authUrlText"></pre>
      <div class="row">
        <a id="openAuthBtn" class="link-btn" target="_blank" rel="noopener" href="#" style="background:#16a34a;border-color:#15803d;">🔑 Google Hesabımla Onayla (Yeni Sekmede Aç) ↗</a>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Adım 3 — Yönlendirilen <code>http://localhost:8080/?code=...</code> Adresini Yapıştır</h2>
    <div style="font-size:13px; color:var(--muted); margin-bottom:8px;">
      Onay verdikten sonra tarayıcında "Bu siteye ulaşılamıyor" yazsa bile adres çubuğundaki tam URL'yi kopyalayıp buraya yapıştır:
    </div>
    <input type="text" id="callbackUrl" placeholder="http://localhost:8080/?state=...&code=4/0A..." />
    <div class="row">
      <button class="secondary" onclick="exchangeCode()">Kodu Takas Et & Gerçek token.json Oluştur</button>
      <span id="step3Status" class="status-pill"></span>
    </div>
    <div id="reportBox" style="display:none; margin-top:14px;">
      <div style="font-size:13px; font-weight:600; color:#34d399; margin-bottom:6px;">
        ✅ GERÇEK OAUTH TAMAMLANDI — PM Rapor Çıktısı (Maskelenmiş):
      </div>
      <pre id="reportText"></pre>
    </div>
  </div>
</div>

<script>
document.getElementById('secretFile').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const text = await file.text();
  document.getElementById('secretJson').value = text;
  saveSecretAndGenerateUrl();
});

async function checkInitialStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    if (d.has_secret) {
      document.getElementById('step2Status').textContent = '✓ client_secret.json mevcut';
      document.getElementById('step2Status').className = 'status-pill ok';
    }
    if (d.auth_url) {
      document.getElementById('authUrlBox').style.display = 'block';
      document.getElementById('authUrlText').textContent = d.auth_url;
      document.getElementById('openAuthBtn').href = d.auth_url;
    }
    if (d.report) {
      document.getElementById('reportBox').style.display = 'block';
      document.getElementById('reportText').textContent = d.report;
    }
  } catch (_) {}
}

async function saveSecretAndGenerateUrl() {
  const raw = document.getElementById('secretJson').value.trim();
  const st = document.getElementById('step2Status');
  st.textContent = 'İşleniyor...';
  st.className = 'status-pill warn';
  try {
    const r = await fetch('/api/upload-secret', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({content: raw})
    });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || 'Hata oluştu');
    st.textContent = '✓ client_secret.json kaydedildi (0600)';
    st.className = 'status-pill ok';
    document.getElementById('authUrlBox').style.display = 'block';
    document.getElementById('authUrlText').textContent = d.auth_url;
    document.getElementById('openAuthBtn').href = d.auth_url;
  } catch (err) {
    st.textContent = '✗ ' + err.message;
    st.className = 'status-pill err';
  }
}

async function exchangeCode() {
  const url = document.getElementById('callbackUrl').value.trim();
  const st = document.getElementById('step3Status');
  st.textContent = 'Google ile token takas ediliyor...';
  st.className = 'status-pill warn';
  try {
    const r = await fetch('/api/exchange', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({callback_url: url})
    });
    const d = await r.json();
    if (!r.ok || !d.ok) throw new Error(d.error || 'Takas başarısız');
    st.textContent = '✓ token.json başarıyla üretildi!';
    st.className = 'status-pill ok';
    document.getElementById('reportBox').style.display = 'block';
    document.getElementById('reportText').textContent = d.report;
  } catch (err) {
    st.textContent = '✗ ' + err.message;
    st.className = 'status-pill err';
  }
}

checkInitialStatus();
</script>
</body>
</html>
"""


def build_masked_report(handler: YouTubeOAuthHandler) -> str:
    channel_title = "Kanal bulunamadı (youtube.com üzerinde kanal açın)"
    subs = "0"
    try:
        service = handler.get_service()
        resp = service.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()
        items = resp.get("items", [])
        if items:
            channel_title = items[0]["snippet"]["title"]
            subs = items[0]["statistics"].get("subscriberCount", "0")
    except Exception as exc:
        channel_title = f"Hata: {exc}"

    token_data = json.loads(handler.token_path.read_text(encoding="utf-8"))
    masked = dict(token_data)
    for secret_key in ("token", "refresh_token", "client_secret"):
        if secret_key in masked and masked[secret_key]:
            masked[secret_key] = "***"
    pretty_lines = json.dumps(masked, indent=2, ensure_ascii=False).splitlines()
    first_lines = "\n".join(pretty_lines[:6])

    return (
        "[+] BAŞARILI: OAuth kimlik doğrulaması tamamlandı. token.json oluşturuldu.\n"
        f"[+] Kanal Adı: {channel_title}\n"
        f"[+] Abone Sayısı: {subs}\n\n"
        "--- token.json (Maskelenmiş İlk Satırlar) ---\n"
        f"{first_lines}\n..."
    )


class WizardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.startswith("/api/status"):
            handler = YouTubeOAuthHandler()
            has_secret = handler.client_secret_path.exists()
            auth_url = None
            report = None
            if has_secret and not handler.token_path.exists():
                try:
                    auth_url = handler.generate_headless_auth_url()
                except Exception:
                    pass
            if handler.token_path.exists() and handler.authenticate():
                report = build_masked_report(handler)
            self._send_json(HTTPStatus.OK, {"ok": True, "has_secret": has_secret, "auth_url": auth_url, "report": report})
            return

        body = HTML_PAGE.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Geçersiz istek gövdesi."})
            return

        handler = YouTubeOAuthHandler()

        if self.path == "/api/upload-secret":
            content = str(payload.get("content", "")).strip()
            if content:
                try:
                    parsed = json.loads(content)
                except Exception:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Geçerli bir JSON girilmedi."})
                    return
                if "installed" not in parsed and "web" not in parsed:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "JSON içinde 'installed' (Desktop app) anahtarı bulunamadı."},
                    )
                    return
                handler.client_secret_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
                os.chmod(handler.client_secret_path, 0o600)

            if not handler.client_secret_path.exists():
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Önce client_secret.json seçin veya yapıştırın."})
                return

            try:
                auth_url = handler.generate_headless_auth_url()
                self._send_json(HTTPStatus.OK, {"ok": True, "auth_url": auth_url})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})
            return

        if self.path == "/api/exchange":
            cb = str(payload.get("callback_url", "")).strip()
            if not cb:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Yönlendirme URL'si boş."})
                return
            if handler.exchange_headless_code(cb):
                report = build_masked_report(handler)
                self._send_json(HTTPStatus.OK, {"ok": True, "report": report})
            else:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": "Kod takası başarısız oldu. logs/oauth_handler.log dosyasını kontrol edin."},
                )
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Bilinmeyen uç nokta."})

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), WizardHandler)
    print(f"OAuth Kurulum Sihirbazı aktif -> http://0.0.0.0:{port}", flush=True)
    server.serve_forever()
