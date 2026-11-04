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
- **Rate limit (HTTP 402/429) yönetimi:** 4 deneme / 12s-60s bekleme. **Tüm denemeler 402 alırsa artık otomatik kare seçimine düşülmez** → Islah 10: yerel yedek kapak üretilir (bkz. aşağıdaki "Yerel Yedek Kapak").
- **FFmpeg ile 1080x1920'e ölçekleme** (YouTube minimum genişlik 640 px) + filigran kırpma.
- **Studio'ya yükleme:** `ytcp-thumbnail-uploader input[type="file"]` → özel kapak anında uygulanır (doğrulama: `ytcp-video-custom-still-editor`).
- Log satırları: `[*] AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...` → `[+] Kapak resmi başarıyla yüklendi.`

## FAZ 13 — Kanal Güveni, Kalite ve Marka Düzeltmeleri (Denetim Tabanlı)

**Tarih:** 2026-11-04 · **Kaynak:** kanal denetimi (herkese açık 9 Shorts, kapaklar, otomatik altyazılar)
**Canlı TODO:** `docs/FAZ13_AUDIT_PLAN.md`

### 13.1 — Açıklama Güvenliği (ürün iddiası ↔ gerçek link)

Denetim bulgusu: *"Bu teleskobu incele", "Bu kitabı oku", "Bu bilim setini incele"*
metinleri **abone linkine** bağlandığı için açıklamalar yanıltıcıydı.

Kök neden `content_engine.py::resolve_affiliate_offer()`: varsayılan affiliate URL'i
kanalın abone linkiydi (`https://www.youtube.com/@mentansiytas?sub_confirmation=1`),
CTA metni ise ürün iddiasıydı.

| Durum | Davranış |
| :--- | :--- |
| Link = kanalın kendi abone linki | CTA: `Benzer videolar için abone ol: <link>` — **ürün iddiası yok** |
| Link = gerçek ürün/affiliate URL (`AFFILIATE_URL_SPACE/HISTORY/SCIENCE`) | `Bu teleskobu incele: <link> (Bu bir affiliate bağlantısıdır.)` |
| LLM hook'unda uydurma URL | Gerçek link ile değiştirilir (`uydurma_link`) |
| LLM hook'unda ürün iddiası + kanal linki | Dürüst CTA'ya çevrilir (`urun_iddiasi`) |

Ürün iddiası tespiti Türkçe ek toleranslıdır (`teleskobu`, `kitabı`, `bilim setini`, `mikroskoba`…).

### 13.2 — Kaynak satırı + iddia/rakam doğrulama

Her açıklamaya doğrulanmış bir kaynak eklenir:

```
[1] Benzer videolar için abone ol: <link>
[2] Etkileşim CTA
[3] Gövde
[4] Kaynak: NASA — https://svs.gsfc.nasa.gov/11260/
[5] #hashtag1 #hashtag2 #hashtag3
```

**Kaynak haritası** (`content_engine.py::KNOWLEDGE_SOURCES`) — 23/23 senaryo için
2026-11-04'te canlı HTTP 200 ile doğrulandı (NASA, NOAA, UNESCO, Smithsonian,
Wikipedia). Bot koruması veren kaynaklar (Britannica 403) kullanılmadı.

**Düzeltilen iddialar:**

| Konu | Önce | Sonra | Kaynak |
| :--- | :--- | :--- | :--- |
| Nötron yıldızı | 6 milyar ton, "küp şeker" | **1 milyar ton**, tek ölçü: çay kaşığı | NASA SVS 11260 |
| Denizanası | "asla yaşlanmayan", "sonsuza kadar", "insan yaşlanmasını durdurur" | "yaşlanmayı biyolojik geri alabilir", "fiziksel olarak ölümsüz değildir", "doğrulanmış tedavi yok" | Smithsonian |
| Emu Savaşı | "devekuşu", "resmen savaş" | "emu", "resmî bir savaş değildi" | Wikipedia (tr) |
| Göbeklitepe | 12.000 yıl | ~11.000 yıl (MÖ 9600–8200) | UNESCO |
| Antikythera | "bin dört yüz yıl sonra" | "en az bin yıl daha üretilmedi" | Smithsonian |
| Napolyon | "üç bin tavşan" | "binlerce evcil tavşan" | Wikipedia (tr) |

Testler: `tests/test_faz13_trust.py` (79 testin tamamı yeşil).

### 13.3 — Kapak iyileştirmesi (konu uygunluğu doğrulama bekliyor)

Denetim: "Nötron yıldızı" kapağı bitiş kartıydı (konu görseli yok), "Denizanası"
çok karanlıktı, "Antikythera"da asıl mekanizma görünmüyordu.

| Katman | Değişiklik |
| :--- | :--- |
| AI kapak (pollinations) | Stil suffix'ine `single clear subject filling the frame`, `bright well-lit subject`, `no text, no logo, no end card, no split screen` eklendi. |
| Yedek kapak (`scripts/generate_fallback_thumbnail.py`) | Artık **video karesi + başlık kompoziti**: ffmpeg ile videodan 5 aday kare alınır, en kontrastlı kare seçilir, 1080×1920'e kırpılır, üstüne siyah konturlu sarı başlık + kırmızı konu rozeti + konuya işaret eden sarı ok + kırmızı "ABONE OL" butonu çizilir. Video yoksa eski metin kartına düşülür. |
| `content_engine.build_thumbnail_prompt()` | Prompt "the single main subject fills the frame, large, bright and instantly recognizable; no text, no watermark, no logo, no end card" ile güçlendirildi. |

Testler: `tests/test_faz13_trust.py::TestFaz13ThumbnailSubject` gerçek ffmpeg karesi ve renk farkını kontrol eder. **En yüksek kontrast, konu nesnesinin görünür olduğunu veya karede bitiş kartı/metin bulunmadığını kanıtlamaz.** Run #58, 13.3 öncesi yerel yedek kapağa aittir; yeni algoritma ve Studio sonucu için canlı doğrulama gereklidir.

13.4 tekrar koruması henüz uygulanmadı: `.used_topics.json` CI koşuları arasında kalıcı değildir ve sayısal kanal seçim yolu geçmişi kontrol etmez. Gerçek yayın geçmişi, güvenli kalıcılık, tüm seçim yolları ve havuz tükendiğinde güvenli durdurma planı için `docs/FAZ13_AUDIT_PLAN.md` belgesine bakın.

### 2b) Yerel Yedek Kapak (Islah 10 — AI servis rate-limit yedeği)

`image.pollinations.ai` kota/rate-limit verdiğinde (HTTP 402/429) **zorunlu kapak teslimi düşmez**:

1. `youtube_studio_uploader.js` → `generateAiThumbnail()` 4 deneme sonunda `null` döner.
2. `generateLocalFallbackThumbnail(title)` devreye girer → `python3 scripts/generate_fallback_thumbnail.py "<başlık>"` (PIL, 60 sn timeout).
3. Üretilen **1080x1920** PNG: siyah/koyu kırmızı gradyan zemin, kırmızı "SON BULMA" bandı, sarı kalın başlık (siyah kontur), sarı ok, kırmızı "ABONE OL" butonu — banner ile aynı görsel dil.
4. Dosya `logs/fallback_thumbnail.png` olarak kaydedilir ve **Studio'ya zorunlu kapak olarak yüklenir**.

Kanıt (run #52, 2026-11-04): pollinations 4/4 deneme HTTP 402 döndürdü → `***!*** Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak.` (özel kapak yok, zorunlu satır kayboldu).
Islah 10 sonrası aynı senaryoda beklenen log: `[*] Yerel yedek kapak hazir (PIL): <yol>` → `[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`

| Dosya | Rol |
| :--- | :--- |
| `scripts/generate_fallback_thumbnail.py` | PIL tabanlı yerel 1080x1920 kapak üreticisi (bağımsız, anahtar gerektirmez) |
| `youtube_studio_uploader.js` → `generateLocalFallbackThumbnail()` | AI kapak null döndüğünde yedeği devreye alır |

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

---

## Faz 12 — TOTAL DOMINATION (Silahlandırılmış Prompt + Agresif Kapak + Kanal Hijyeni)

### 1) Cron Throttle Bypass
```yaml
on:
  schedule:
    - cron: '0,13,27,41,55 * * * *'   # asal olmayan dakikalar
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true            # tıkanmış/eski job iptal, en güncel çalışır
permissions:
  contents: write
  actions: write
```
> Zincir (cron-kick) tetikleme POST'u tamamladıktan sonra iptal olur; self-perpetuating zincir bozulmaz.

### 2) Silahlandırılmış LLM Promptu
`content_engine.py → build_llm_prompts()` artık "algoritma hacker'ı" personasıyla çalışır:
scroll-stop hook (60-80 kelime), zorlayıcı CTA, **zorunlu kapak dili**
(`YouTube Shorts thumbnail, vertical 9:16, hyper-dramatic lighting, high contrast, vibrant colors,
glowing elements, 8k resolution, cinematic`), tam 3 spesifik hashtag + `affiliate_hook`.
JSON şeması: `topic, title, description, hook, script_text, cta_line, thumbnail_prompt,
viral_hashtags, affiliate_hook, visual_keywords`.

### 3) Agresif AI Kapak (CTR odaklı)
`youtube_studio_uploader.js` → kapak promptuna otomatik eklenen stil suffix'i:
`glowing arrows, shocked expression, unreal engine 5 render, dramatic shadows, 8k resolution...`
Yükleme iki katmanlıdır: önce `ytcp-thumbnail-uploader input#file-loader` (doğrulanmış yol),
olmazsa `Kapak resmi / Thumbnail` butonu + `filechooser` yedeği. Başarı logu:
`[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`

### 4) Açıklama Sırası (Metadata Zehiri)
```
[1] affiliate_hook (varsa) / affiliate CTA + link
[2] Etkileşim CTA (cta_line)
[3] Gövde
[4] Tam 3 trend hashtag
```

### 5) Kanal Hijyeni (otomasyon)
| Adım | Nerede | Durum |
| :--- | :--- | :--- |
| Banner (2560x1440, siyah + sarı/beyaz + kırmızı "ABONE OL") | `scripts/generate_banner.py` | ✅ üretildi & yüklendi |
| Kanal "Hakkında" açıklaması | `ytcp-social-suggestions-textbox#description-textbox` + "Yayınla" | ✅ güncellendi |
| Sabitlenmiş yorum | `ytd-comment-simplebox-renderer` → `İşlem menüsü` → "Sabitle" | ✅ yazıldı & sabitlendi (`#pinned-comment-badge`) |

Hepsi `scripts/channel_hygiene.js` ile yapılır; **hata olursa yayınlama akışı bozulmaz**.


---

## Faz 12.6 — Denetim İslahları (Ekip Denetimi, 04.11.2026)

Ekip denetimi 5 bulgu getirdi. Her bulgu için **neden** + **nasıl doğrulandı** kaydı:

### 1) İptal fırtınası (asıl dert) — DÜZELTİLDİ
**Kök neden:** `cron-kick` job'ı `if: always()` ile çalışıyordu. İptal edilen bir koşu
bile yeni bir zincir koşusu tetikliyordu → #34 iptal → #35 doğdu → #35 iptal → #36…
Ayrıca GitHub `schedule` olayı ile zincir **aynı anda** iki video üretiyordu.

| Önlem | Nerede |
| :--- | :--- |
| `if: always()` → `if: ${{ !cancelled() }}` (iptal edilen koşu yeni koşu doğurmaz) | `daily_shorts.yml`, `hourly_pruner.yml` |
| Tetiklemeden önce aktif koşu kontrolü (`scripts/active_runs_count.sh`) | `cron-kick` |
| Cron artık **bekçi (watchdog)**: zincir aktifse üretim yapmaz (`scripts/production_gate.sh`) | `build-and-upload` |
| Zincir koşuları ayrı concurrency grubunda (`chain=1`) → elle/schedule koşusu yayını iptal etmez | `concurrency.group` |

**Doğrulama:** zincir kırıkken zincir yeni koşu üretmiyor; `schedule` koşusu aktif zincir
varsa `produce=false` ile üretimi atlıyor; 57/57 unittest + actionlint temiz.

### 2) Ubuntu 26.04 geçişi — SABİTLENDİ
GitHub 19 Ekim–19 Kasım 2026 arasında `ubuntu-latest` → 26.04'e geçiyor. Bu repo
`libass9`, `fonts-*`, `xvfb` ve `playwright install --with-deps` kullanıyor.

- Ana workflow'lar: `runs-on: ubuntu-24.04` (resmî öneri)
- Yeni `.github/workflows/ubuntu_26_test.yml`: `ubuntu-26.04` imajında paket kurulumu,
  Playwright, **altyazı montaj testi** (FontSize=56 / MarginV=250) ve birim testleri.
  (Geçiş öncesi ölçüm; kanal/yayın yapmaz.)
- `.github/actionlint.yaml`: actionlint'in etiket listesi 26.04'ü bilmiyor → ignore.

### 3) Node 20 uyarıları — YÜKSELTİLDİ
`action.yml → runs.using` doğrulandı (v4/v5 = node20, v6/v7 = node24):

| Action | Eski | Yeni | Breaking change etkisi |
| :--- | :--- | :--- | :--- |
| actions/checkout | v4 (node20) | **v7** (node24) | fork-PR engeli (kullanmıyoruz) + ESM → etkisiz |
| actions/setup-python | v5 (node20) | **v7** (node24) | `pip-install` input'u kaldırıldı (kullanmıyoruz) → etkisiz |
| actions/setup-node | v4 (node20) | **v7** (node24) | yeni output'lar, sahte `NODE_AUTH_TOKEN` kaldırıldı → etkisiz |
| actions/upload-artifact | v4 (node20) | **v7** (node24) | `archive:false` opsiyonel (varsayılan zip aynı) → etkisiz |

### 4) Koddan okunduğu buglar — DÜZELTİLDİ
- `ARGS` artık **bash array** (`ARGS=(--banner ... --about "$ABOUT_TEXT")` + `"${ARGS[@]}"`).
  Önceden `$ARGS` boşluklu metni (e-posta) birden fazla argümana bölüyordu.
- Hata `|| echo` ile yutulmuyor → `::warning::Kanal hijyeni başarısız (rc=…)` annotation'ı.
- `${{ inputs.slot_epoch }}` artık **env** (`SLOT_EPOCH`) ile geçiliyor (script injection riski yok).
- **actionlint bulgusu:** `join(distinct_csv, '","')` → GitHub ifadelerinde `join()` ARRAY
  bekler, `distinct_csv` STRING'dir (tek kanalda tesadüfen çalışıyordu). Artık
  `scripts/channel_map.sh` → `distinct_json='["1"]'` üretiyor, matrix `fromJSON(distinct_json)`.

### 5) Artifact güvenliği — EKLENDİ
`scripts/sanitize_logs.sh`: artifact'a girmeden önce `logs/` içinden
cookie/storage_state/token dosyaları **silinir**, kalan dosyalardaki
`SIDCC/SAPISID/HSID/SSID/__Secure-*`/`Bearer …`/`AIza…`/`refresh_token` kalıpları
**redakte** edilir ve `::warning::` üretilir.

### 6) Tek satırlık durum bildirimi — EKLENDİ
`scripts/run_summary.py` → `::notice::Kanal 1: YÜKLENDİ | Video: … | https://…`
(+ GitHub Step Summary tablosu). `scripts/pruner_summary.py` → pruner özeti.

### Tek üretim mekanizması: ZİNCİR
GitHub `schedule` olayı **best-effort**: 13 saatte sadece **2 kez** ve 4–6 dk gecikmeyle
tetiklendi (#28 01:51, #29 08:31). Bu yüzden:
- **Zincir (cron-kick) = asıl motor** (15 dk'da bir, kendini devam ettiren).
- **Cron = bekçi**: yalnızca zincir ölüyse devreye girer.


### 7) GitHub output maskeleme tuzağı (CI'da ölçüldü) — ÖNEMLİ
`channel-map` job'ının çıktısı **düz string** olmak zorunda. GitHub, **köşeli parantez
içeren** output değerlerini secret sanıp maskeliyor ve outputu **atıyor**:

| Output değeri | Sonuç (run 41851410202, channel-map job) |
| :--- | :--- |
| `["1"]` (tırnaklı JSON dizi) | `Skip output ... since it may contain secret` ✗ |
| `[1]` (sade JSON dizi) | `Skip output ... since it may contain secret` ✗ |
| `1` (düz string) | `Set output 'distinct_csv'` ✓ |

Bu yüzden `distinct_json` çıktısı **kullanılamaz**; matris şu ifadeyle kurulur
(runtime'da doğrulandı: schedule koşuları #28/#29 bu ifadeyle video üretti):
```yaml
channel_id: ${{ fromJSON(format('["{0}"]', join(needs.channel-map.outputs.distinct_csv, '","'))) }}
```
> `split()` **GitHub ifade dilinde yoktur** — `workflow_dispatch` 422 ile reddedilir
> ("Unrecognized function: 'split'"). actionlint de uyarır.

### 8) Ek denetim düzeltmeleri (2. tur)
| Bulgu | Durum |
| :--- | :--- |
| `hourly_pruner.yml` → `#{{ matrix.channel_id }}` yazım hatası | ✅ düzeltildi (`${{ }}`) |
| `cron_probe.yml` → `*/5` (ayda ~8.640 job) | ✅ saatliğe çekildi (`17 * * * *`) |
| `daily_analytics.yml` → push öncesi rebase yok | ✅ `git pull --rebase` eklendi |
| `sanitize_logs.sh` → dar dosya kalıpları | ✅ `*session*`, `*.key`, `*.pem`, `id_token`, `session_id` eklendi |
| Hijyeni adımı `if: always()` → gate `produce=false` iken About metnini ezip **kanal hakkında alanını bozabilirdi** | ✅ gate'e bağlandı |
| `actions/checkout@v7` "yok" iddiası | ❌ **yanlış** — v7.0.1 (20.07.2026) mevcut, `runs.using: node24`; CI'da fiilen çalıştı (#43/#44 başarılı) |
| `ubuntu-26.04` runner "yok" iddiası | ❌ **yanlış** — 17.09.2026 changelog'u duyurdu; `ubuntu_26_test.yml` iki kez 26.04'te **başarıyla** çalıştı (ffmpeg 8.0.1, altyazı montajı OK, 57 test OK) |
| `requirements.txt` "pinler bulunamaz" iddiası | ❌ **yanlış** — zaten tam pin (`==`) ve her CI koşusunda başarıyla kuruluyor |
