# YouTube Shorts Automation — Tam Otonom İçerik Fabrikası (Faz 1–7)

Python, FFmpeg ve Node.js Playwright tabanlı; **sıfır API kotası**, **sıfır maliyet** ve **sıfır manuel müdahale** ile çalışan, GitHub Actions üzerinde her gün paralel olarak Türkçe YouTube Shorts üreten ve doğrudan **Herkese Açık (`PUBLIC`)** yayınlayan uçtan uca otomasyon sistemi.

> 🤖 **Projeyi Devralacak Yapay Zeka / Geliştirici İçin İlk Adım:**  
> Tüm sistem durumu, kimlik/oturum dosyalarının Google Drive & GitHub Secrets konumları, kritik güvenlik kuralları ve çözülmüş teknik tuzaklar için önce **[`AI_HANDOFF.md`](./AI_HANDOFF.md)** ve **[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)** belgelerini okuyun.

---

## Tamamlanan Fazlar ve Sistem Özeti

| Faz | Modül | Açıklama | Durum |
| :---: | :--- | :--- | :---: |
| **Faz 1** | `youtube_auth.py`, `src/youtube_upload/` | Headless/bulut uyumlu OAuth2 PKCE akışı ve YouTube Data API v3 yedek yükleme modülü | ✅ |
| **Faz 2** | `content_engine.py` | Groq / Gemini / Çakışmasız Matris Havuzu + Türkçe Wikipedia doğrulaması + `edge-tts` (`tr-TR-AhmetNeural`) seslendirme + milisaniye senkronlu `.srt` üretimi | ✅ |
| **Faz 3** | `src/media_processing/media_processor.py` | Dikey stok video indirme (Pexels / Pixabay / Wikimedia), pop-animasyonlu `.ass` altyazı, arka plan müziği miksajı ve tek geçişli `1080x1920` (30 FPS, H.264/AAC) FFmpeg montajı | ✅ |
| **Faz 4** | `src/youtube_upload/youtube_uploader.py` | Resumable API yükleme ve onay kuyruğu altyapısı (`22/22` birim testi) | ✅ |
| **Faz 5** | `youtube_studio_uploader.js` | API kotasını (`10.000 birim`) tamamen aşan Playwright Chromium YouTube Studio yükleyicisi + kalıcı oturum (`cookies.json`, `storage_state.json`) | ✅ |
| **Faz 6** | `main.py`, `.github/workflows/daily_shorts.yml` | Tüm fazları tek komutta zincirleyen Ana Orkestratör ve GitHub Actions `ubuntu-latest` + `Xvfb` bulut otomasyonu | ✅ |
| **Faz 7** | `daily_shorts.yml`, `youtube_studio_uploader.js` | Doğrudan **`PUBLIC` (Herkese Açık)** otomatik yayın ve `matrix.channel_id: ['1', '2', '3']` ile aynı anda **3 paralel bulut sunucusunda** çakışmasız üretim | ✅ |

---

## Hızlı Kurulum ve Çalıştırma

### 1. Sistem ve Dil Bağımlılıkları (Debian / Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-montserrat fonts-liberation fonts-dejavu-core libass9 xvfb

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm install
npx playwright install --with-deps chromium
```

### 2. Ortam ve Oturum Dosyaları

`.env.example` dosyasını `.env` olarak kopyalayın (veya devir teslim yedeğindeki `.env`, `cookies.json` ve `storage_state.json` dosyalarını kök dizine yerleştirin):

```bash
chmod 600 .env cookies.json storage_state.json
```

### 3. Uçtan Uca Üretim ve `PUBLIC` Yayın

```bash
# Sanal ekran (Xvfb) ile tam tarayıcı bütünlüğünde çalıştırma:
xvfb-run -a --server-args="-screen 0 1366x900x24" python main.py
```

### 4. Birim Testlerini Çalıştırma

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## GitHub Actions 7/24 Paralel Matris Otomasyonu

`.github/workflows/daily_shorts.yml` iş akışı her gün **TSİ 18:00'de (`cron: '0 15 * * *'`)** veya GitHub arayüzünden **`Run workflow` (`workflow_dispatch`)** butonuyla tetiklendiğinde:

1. `build-and-upload (1)`, `build-and-upload (2)` ve `build-and-upload (3)` olmak üzere **3 bağımsız bulut sunucusu** paralel ayağa kalkar (`fail-fast: false`).
2. Her hat kendi GitHub Secret setini (`ENV_FILE_<id>`, `COOKIES_JSON_<id>`, `STORAGE_STATE_JSON_<id>`) yükler ve birbirinden farklı bir senaryo seçer.
3. Videolar `1080x1920` dikey formatta montajlanıp doğrudan **Herkese Açık (`PUBLIC`)** olarak YouTube'da yayınlanır ve çıktılar `shorts-output-channel-<id>-<run_number>` artifact paketlerine yedeklenir.

---

## Gizli Bilgiler ve Güvenlik

`.env`, `cookies.json`, `storage_state.json`, `*.har`, `client_secret*.json` ve `*token*.json` dosyaları `.gitignore` ile koruma altındadır; **asla** Git deposuna eklenmez. Bulut ortamında yalnızca şifreli **GitHub Repository Secrets** ve özel **Google Drive** yedekleri kullanılır.
