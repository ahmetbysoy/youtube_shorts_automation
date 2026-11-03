# YouTube Shorts Automation — Sıfır Maliyetli İçerik Fabrikası

Python 3.13 ve FFmpeg tabanlı, modüler, hata toleranslı ve sıfır maliyetli YouTube Shorts otomasyon altyapısı.

## Mevcut Durum (Tamamlanan Fazlar)

- **Proje İskeleti & Doğrulama (`config/`, `tests/`, `main.py`):** Ortam değişkenlerine dayalı yapılandırma, dikey (1080×1920, 9:16) sabitler ve sistem/bağımlılık testleri.
- **Faz 1 — YouTube OAuth2 & Private Yükleme (`youtube_auth.py`, `upload_test.py`, `src/youtube_upload/`):**
  - Google'ın kaldırdığı `run_console()` yerine bulut/headless uyumlu **Loopback URL Kopyalama + PKCE (`code_verifier`)** akışı.
  - Süresi dolan `access_token`'ı `refresh_token` ile otomatik yenileyen, kesintiye dayanıklı (`resumable` + exponential backoff) ve **`privacyStatus="private"` zorunlu güvenlik kilitli** yükleyici.
- **Faz 2 — İçerik ve Seslendirme Motoru (`content_engine.py`, `src/content_generation/`):**
  - **Çok Katmanlı LLM Zinciri:** Groq Free API (`llama-3.3-70b-versatile`) -> Google Gemini Free API (`gemini-2.5-flash`) -> Doğrulanmış Çevrimdışı Yedek Senaryo Havuzu (`FALLBACK_SCENARIOS`).
  - **Gerçeklik Çapası:** Türkçe Wikipedia REST API üzerinden kaynak doğrulama ve `.used_topics.json` ile konu tekrarı engelleme.
  - **TTS & Milisaniye Senkronlu Altyazı:** `edge-tts` (`tr-TR-AhmetNeural` / `tr-TR-EmelNeural`) `WordBoundary` akışıyla Whisper'a gerek kalmadan 2-3 kelimelik dinamik Shorts `.srt` ve `word_timestamps` üretimi (+ `gTTS` yedeği).
- **Örnek Çıktılar (`samples/`):** Faz 1 ve Faz 2 test üretimleri (`test.mp4`, `voiceover.mp3`, `voiceover.srt`, `script.json`, `script.txt`).
- **Sıradaki Fazlar:**
  - *Faz 3:* `src/media_processing/` — Pexels/Pixabay dikey stok video çekimi, FFmpeg Ken Burns, ses miksajı ve dinamik altyazı gömme.
  - *Faz 4:* GitHub Actions CI/CD cron otomasyonu ve Secrets entegrasyonu.

---

## Kurulum — Debian 13 / Ubuntu / Python 3.13

```bash
sudo apt-get update && sudo apt-get install -y ffmpeg tree
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Kullanım

### Faz 1: YouTube OAuth2 Yetkilendirme & Private Test Yüklemesi

```bash
# 1. Headless ortamda yetkilendirme linki üret:
python youtube_auth.py --generate-url

# 2. Tarayıcıda onay sonrası yönlendirilen http://localhost:8080/?code=... adresini takas et:
python youtube_auth.py --exchange "http://localhost:8080/?state=...&code=..."

# 3. Private yükleme paketini kota harcamadan doğrula (Dry-Run):
python upload_test.py --video samples/test.mp4 --dry-run

# 4. Canlı Private test yüklemesi:
python upload_test.py --video samples/test.mp4
```

### Faz 2: Senaryo, Seslendirme ve Altyazı Üretimi

```bash
# Ortam değişkenlerini (.env) yapılandırıp çalıştırın (anahtar yoksa otomatik fallback çalışır):
python content_engine.py --concept "İlginç Bilgiler ve Tarih" --voice ahmet
```

## Testler

```bash
python -m unittest discover -s tests/ -p "test_scaffold.py" -v
python -m unittest discover -s tests/ -p "test_faz1_faz2.py" -v
```

## Gizli Bilgiler & Güvenlik

`.env.example` yalnızca şablondur. Gerçek API anahtarları `.env` dosyasında veya GitHub Secrets üzerinde tutulmalıdır. `.env`, `secrets/`, `client_secret*.json`, `*token*.json`, `cookies.json`, `storage_state.json` ve `*.har` dosyaları `.gitignore` ile koruma altındadır; asla depoya eklenmez.

## Faz 5–7: Playwright YouTube Studio Otonom Yayın (`PUBLIC`) & GitHub Actions Matris Çoğaltma

- **Faz 5 — Playwright YouTube Studio Backdoor (`youtube_studio_uploader.js`):** YouTube Data API v3 günlük kota sınırına (`10.000 birim`) takılmamak için Node.js + Playwright Chromium üzerinden doğrudan YouTube Studio (`studio.youtube.com`) arayüzünü otomatikleştirir. Oturum `cookies.json`, `storage_state.json` ve `session.har` (`0600`) ile kalıcı olarak korunur.
- **Faz 6 — Ana Orkestratör (`main.py`):** Senaryo/TTS (`content_engine.py`), dikey montaj (`src/media_processing/media_processor.py`) ve YouTube Studio yükleyicisini (`youtube_studio_uploader.js`) tek komutta uçtan uca zincirler.
- **Faz 7 — Tam Otonom Yayın (`PUBLIC`) ve Çoklu Kanal Matrisi (`.github/workflows/daily_shorts.yml`):**
  - Videolar artık sıfır manuel müdahaleyle doğrudan **`PUBLIC` (Herkese Açık)** olarak yayınlanır (`tp-yt-paper-radio-button[name="PUBLIC"]` + ek onay penceresi yönetimi).
  - GitHub Actions üzerinde `strategy.fail-fast: false` ve `matrix.channel_id: ['1', '2', '3']` mimarisiyle her gün **TSİ 18:00**'de (`0 15 * * *`) 3 paralel sunucuda (`build-and-upload (1)`, `build-and-upload (2)`, `build-and-upload (3)`) çakışmasız farklı senaryolar üretilip yayınlanır.
  - Kanal bazlı GitHub Secrets (`ENV_FILE_1..3`, `COOKIES_JSON_1..3`, `STORAGE_STATE_JSON_1..3`) dinamik olarak enjekte edilir.

