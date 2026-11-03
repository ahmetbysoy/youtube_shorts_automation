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
| **Faz 7** | `daily_shorts.yml`, `youtube_studio_uploader.js`, `scripts/rotate_cookies.py` | Doğrudan **`PUBLIC` (Herkese Açık)** otomatik yayın, `matrix.channel_id: ['1'..'10']` ile **10 paralel bulut üretim hattı** ve 14 günlük otomatik Cookie/StorageState rotasyon aracı | ✅ |
| **Faz 8** | `content_engine.py`, `media_processor.py`, `main.py`, `daily_shorts.yml` | **15-Minute Blitzkrieg Sniper Modu:** MD5/zaman tabanlı 15dk benzersizlik garantisi (`23` asal senaryo havuzu), mobil-optimize sinematik FFmpeg (`unsharp` + `eq` + `MarginV=250`) ve `concurrency` kuyruk kilidi | ✅ |
| **Faz 9** | `content_engine.py`, `youtube_studio_uploader.js`, `analytics_scraper.js`, `daily_analytics.yml` | **Monetizasyon & Analitik Geri Bildirim Döngüsü:** Konu bazlı otomatik `affiliate_link` / CTA enjeksiyonu (açıklamanın en üst satırı) ve her sabah YouTube Studio izlenme/AVD verisini kazıyıp kazanan nişi (`%80` ağırlıkla) besleyen otonom analitik döngüsü | ✅ |

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

---

## Faz 10 — Otonom "Ölü Ağırlık" Temizliği (Auto-Pruner, Saatlik)

`.github/workflows/hourly_pruner.yml` iş akışı **her saat başı (`cron: '0 * * * *'`)** devreye girer, 10 kanallı matrisle (kanal `1..10`, `fail-fast: false`) YouTube Studio'ya girer ve **ilk 1 saatini geçmiş + 100 izlenmenin altında kalmış** videoları kalıcı olarak siler.

### Çalışma Mantığı (`prune_low_performers.js`)

| Adım | Gerçek YouTube Studio Yapısı (canlı kanalda doğrulandı) |
| :--- | :--- |
| **Video Satırları** | `ytcp-video-row` (her satırda `#video-title`, `a[href*="/video/{ID}"]`) |
| **İzlenme Sütunu** | `.tablecell-views` (Türkçe sayı biçimi: `1.234`, `1,2 B`, `3,4 Mn`) |
| **Yayın Tarihi Sütunu** | `.tablecell-date` (`3 Kas 2026` + `Yayınlandı` / `Yüklendi`) |
| **Seçenek Menüsü** | `ytcp-icon-button.open-menu-button` (`aria-label="Seçenekler"`) |
| **Silme Kalemi** | `tp-yt-paper-item[test-id="delete"]` (metin: **"Tamamen sil"**) |
| **Onay Penceresi** | `ytcp-video-delete-dialog` → `#confirm-checkbox #checkbox` (kalıcılık onayı) → `#confirm-button` |

### Yaş (Süre) Çözümleme — 3 Katmanlı, Asla Erken Silme Garantili

1. **Kanal RSS yayını** (`https://www.youtube.com/feeds/videos.xml?channel_id=...`) → kesin ISO yayın zamanı.
2. **`prune_state.json`** (ilk görülme kaydı) → gözlem tabanlı kesin yaş (gizli videolar için de çalışır).
3. **Studio tarih sütunu** → göreli (`3 saat önce`) veya mutlak tarih; mutlak tarihte video günün **en geç 23:59'unda** yayınlanmış sayılır (asla erken silinmez).

### Emniyet Kilitleri (Env ile ayarlanabilir)

| Değişken | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `PRUNE_MIN_VIEWS` | `100` | Bu izlenmenin altındakiler hedeflenir |
| `PRUNE_MIN_AGE_MINUTES` | `60` | İlk 1 saatteki videolar **dokunulmaz** |
| `PRUNE_MAX_DELETIONS` | `10` | Tek çalıştırmada silme üst sınırı |
| `PRUNE_MIN_REMAINING` | `1` | Kanalda bırakılacak en az video |
| `PRUNE_DRY_RUN` | `false` | `true` ise yalnızca raporlar, silmez |

### Çıktılar

- `prune_report.json` → tarama/HD/KORUNDU/silme raporu (artifact + repo'ya yazılır).
- `prune_state.json` → video ID → ilk görülme zamanı (yaş çözümleme hafızası).
- Log satırları: `[!] HEDEF TESPİT EDİLDİ: ...`, `[+] BAŞARILI: '...' kalıcı olarak silindi.`, `[*] KORUNDU: ...` ve `🚀 TEMİZLİK TAMAMLANDI: X adet düşük performanslı video imha edildi. 🚀`

### Manuel Tetikleme

```bash
curl -X POST -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/hourly_pruner.yml/dispatches \
  -d '{"ref":"main","inputs":{"target_channel":"1"}}'
```

---

## Faz 11 — Viral Metadata, AI Kapak (Thumbnail) ve Cron Kilidi Kırma

### 1) Viral Metadata Üretimi (`content_engine.py`)

LLM istemi artık metinle birlikte **algoritma hackleme metadatası** da üretir:

| Alan | Açıklama |
| :--- | :--- |
| `hook` | İlk 3 saniyenin kancası ("Merhaba" yasak) |
| `cta_line` | Videonun son cümlesi: yorum/abone çağrısı |
| `thumbnail_prompt` | **İngilizce**, dikey (9:16), yüksek kontrastlı kapak görseli promptu |
| `viral_hashtags` | **Tam 3 adet** spesifik trend hashtag (YouTube 3'ten fazlasını yok sayar) |

Açıklama sırası (YouTube'da görünen hâli):
```
[1] Affiliate CTA + link      (Faz 9: en üstte)
[2] Etkileşim CTA (cta_line)
[3] Govde metni
[4] #hashtag1 #hashtag2 #hashtag3
```
Yedek senaryo havuzu (LLM anahtarı yokken) için 23 başlığın **elle seçilmiş** hashtag haritası `FALLBACK_VIRAL_TAGS` içinde tanımlıdır.

### 2) Ücretsiz AI Kapak Üretimi + Yükleme (`youtube_studio_uploader.js`)

- **Görsel motoru:** `https://image.pollinations.ai/prompt/<prompt>?width=1080&height=1920&nologo=true&model=flux` (anahtar istemez, ücretsiz).
- **Rate limit (HTTP 402/429) yönetimi:** 4 deneme / 12s-60s bekleme; başarısız olursa YouTube otomatik kare seçimine düşer (yükleme asla çökmez).
- **FFmpeg ile 1080x1920'e ölçekleme** (YouTube minimum genişlik 640 px) + filigran kırpma.
- **Studio'ya yükleme:** `ytcp-thumbnail-uploader input[type="file"]` → özel kapak anında uygulanır (doğrulama: `ytcp-video-custom-still-editor`).
- Log satırları: `[*] AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...` → `[+] Kapak resmi başarıyla yüklendi.`

### 3) Günlük Kota Koruması

YouTube günlük yükleme limiti dolduğunda yükleme **çökmez**, planlı olarak atlanır:
`⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).` (çıkış kodu `42` → `main.py` bunu hata saymaz).

### 4) Cron Kilidi Kırma (Zamanlayıcı Bağımsız Zincir)

GitHub'ın `schedule` tetikleyicisi bu depoda **hiç otomatik tetiklenmemişti** (`event=schedule` toplam çalıştırma = 0). Çözüm:

1. `cron: '0,15,30,45 * * * *'` (kesin dilimler) + `permissions: contents/actions/pull-requests: write`.
2. **Otomatik commit mesajlarındaki `[skip ci]` kaldırıldı** — HEAD commit mesajında `[skip ci]` varsa zamanlayıcı sessizce atlanır.
3. **`cron-kick` job'ı (zincir):** Her çalıştırmanın sonunda zamanlayıcı canlı mı kontrol edilir (API: `?event=schedule`); **ölüyse** iş akışı `workflow_dispatch` ile kendini bir sonraki 15 dakikalık dilime yeniden tetikler. Böylece üretim zinciri zamanlayıcıdan bağımsız çalışır.
4. `.github/workflows/cron_probe.yml`: 5 dakikada bir "PROBE OK" atan nabız iş akışı (zamanlayıcı sağlık teşhisi).

### 5) Kanal Sırası + "Aynı Hesap" Koruması (Faz 11 düzeltmesi)

Daha önce 10 kanal **aynı anda** çalışıyordu ve 10 secret'in tamamı **aynı YouTube hesabını**
işaret ettiği için kanalın günlük yükleme kotası 10 katına kadar harcanıyordu.

| Sorun | Çözüm |
| :--- | :--- |
| 10 paralel job, aynı kanal | `max-parallel: 1` + zincir **tek kanal** tetikler (dizi kanal sırası) |
| 10 secret = aynı hesap | `scripts/channel_map.sh` → aynı hesabı işaret eden kanallar **ayıklanır** |
| Kota doluyken boşuna üretim | Zincir, kotaya takılan turdan sonra **4 saat** bekler (15 dk değil) |
| GitHub matris çıktısını siliyordu | Matris `distinct_csv` (virgüllü liste) olarak taşınır, iş akışında JSON'a çevrilir |

**Kanal haritası job'u** her çalıştırmada hangi kanalların AYRI hesap olduğunu loglar:
```
[AYRI HESAP] Kanal 1 (hash a4ae91d03ee1) -> uretime dahil.
[AYNI HESAP] Kanal 2 = Kanal 1 (hash a4ae91d03ee1) -> atlandi (gunluk kota korunuyor).
...
[*] Benzersiz kanallar: 1
[*] Siradaki kanal (rotasyon 17): 1
```

> ⚠️ **Kanal kurulumu:** `COOKIES_JSON_1..10` şu anda **tek hesabı** gösteriyor. Gerçek 10 kanal için
> her kanalın **ayrı bir YouTube hesabı** (ayrı `cookies.json` + `storage_state.json`) olmalı.
> Ayrı hesaplar girildikçe `channel_map.sh` otomatik olarak üretime alır (matris büyür).
