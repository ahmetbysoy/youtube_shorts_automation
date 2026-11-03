# Sistem Mimarisi ve Teknik Veri Sözleşmeleri (`ARCHITECTURE.md`)

> **Sürüm:** Faz 7 (Tam Otonom `PUBLIC` Yayın & GitHub Actions 3'lü Matris Mimarisi)  
> **Son Güncelleme:** `2026-11-03`

Bu doküman, `youtube_shorts_automation` boru hattındaki modüllerin iç yapısını, dosya sözleşmelerini (data contracts), FFmpeg filtre grafiğini ve Playwright DOM seçicilerini açıklar. Devir teslim ve operasyonel kurallar için kök dizindeki [`AI_HANDOFF.md`](../AI_HANDOFF.md) dosyasına bakın.

---

## 1. Uçtan Uca Boru Hattı (Pipeline) Akışı

```text
[GitHub Actions Cron (15:00 UTC) / workflow_dispatch]
        │
        ├──► Job 1: MATRIX_CHANNEL_ID=1 ──┐
        ├──► Job 2: MATRIX_CHANNEL_ID=2 ──┼──► Paralel Ubuntu Sunucuları (Xvfb 1366x900x24)
        └──► Job 3: MATRIX_CHANNEL_ID=3 ──┘
                                          │
                                          ▼
                                   [ python main.py ]
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         ▼                                ▼                                ▼
 1. content_engine.py        2. media_processor.py          3. youtube_studio_uploader.js
 ────────────────────        ─────────────────────          ─────────────────────────────
 • Groq / Gemini /           • Pexels / Pixabay /           • storage_state.json +
   Matris Havuzu               Wikimedia dikey klip           cookies.json yükleme
 • Türkçe Wikipedia          • 3 kelimelik dinamik          • Google AccountChooser &
   gerçeklik çapası            Pop-up .ass altyazı            ara ekran bypass
 • edge-tts (AhmetNeural)    • Tek geçişli (single-pass)    • Başlık, açıklama, etiket,
 • WordBoundary milisaniye     FFmpeg 1080x1920 H.264         "Çocuklara özel değil"
   kelime zamanlaması          + arka plan müzik miksajı    • Görünürlük: PUBLIC
         │                                │                 • "Yayınla" + onay diyalogları
         ▼                                ▼                                │
   script.json                     output/final_short.mp4                  ▼
   voiceover.mp3                   output/final.ass           Canlı YouTube Shorts URL
   voiceover.srt                                              logs/auth_status.json
```

---

## 2. Modül ve Dosya Yapısı

```text
youtube_shorts_automation/
├── .github/workflows/
│   ├── daily_shorts.yml           # Faz 6–8: 15dk Blitzkrieg 10'lu Matris üretim ve PUBLIC yayın akışı
│   └── daily_analytics.yml        # Faz 9: Sabah 09:00 TSİ YouTube Studio analitik kazıma ve geri besleme akışı
├── AI_HANDOFF.md                  # Yapay zeka devir teslim ve operasyon kılavuzu
├── README.md                      # Genel proje özeti ve kurulum rehberi
├── main.py                        # Faz 6–8: Ana orkestratör (--channel_id destekli)
├── content_engine.py              # Faz 2, 8 & 9: 15dk Seed + Affiliate CTA + Analitik beslemeli içerik motoru
├── youtube_studio_uploader.js     # Faz 5, 7 & 9: Playwright YouTube Studio PUBLIC + Affiliate yükleyici
├── analytics_scraper.js           # Faz 9: YouTube Studio İzlenme & AVD kazıyıcı -> analytics_feedback.json
├── youtube_auth.py                # Faz 1: OAuth2 PKCE konsol/loopback yetkilendirme aracı
├── upload_test.py                 # Faz 1: Resmi YouTube Data API v3 test yükleyicisi
├── assets/
│   └── background_music.mp3       # Telifsiz arka plan ambiyans müziği (%12 ses seviyesi)
├── config/
│   ├── constants.py               # 1080x1920, 30 FPS, ses/video sabitleri
│   └── settings.py                # Ortam değişkeni doğrulayıcı
├── docs/
│   ├── ARCHITECTURE.md            # Bu teknik mimari belgesi
│   └── setup/                     # Kurulum ve bağımlılık karar raporları
├── src/
│   ├── content_generation/        # İçerik motoru paket sarmalayıcısı
│   ├── media_processing/
│   │   └── media_processor.py     # Faz 3: Stok video indirme, .ass altyazı ve FFmpeg montaj
│   └── youtube_upload/
│       ├── oauth_handler.py       # OAuth2 token yenileme ve PKCE yöneticisi
│       └── youtube_uploader.py    # YouTube Data API v3 resumable yükleyici (yedek modül)
├── samples/                       # Örnek senaryo, ses, SRT ve test MP4 çıktıları
└── tests/                         # 22 adet birim ve entegrasyon testi (unittest)
```

---

## 3. Veri Sözleşmeleri (Data Contracts)

### `script.json` (Faz 2 Çıktısı -> Faz 3 & Faz 5 Girdisi)
```json
{
  "topic": "Tarih",
  "title": "Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe! #Shorts",
  "description": "Şanlıurfa'daki Göbeklitepe insanlık tarihini nasıl baştan yazdı? #göbeklitepe #tarih #ilginçbilgiler #shorts",
  "hook": "Mısır piramitlerinden bile tam yedi bin yıl daha eski...",
  "script_text": "Tam seslendirme metni...",
  "visual_keywords": ["ancient stone temple", "archaeology excavation desert"],
  "provider": "local-fallback-matrix-2",
  "voice": "tr-TR-AhmetNeural",
  "audio_file": "voiceover.mp3",
  "subtitle_file": "voiceover.srt",
  "duration_seconds": 36.4
}
```

### `logs/auth_status.json` (Faz 5/7 Çıktısı)
```json
{
  "timestamp": "2026-11-03T18:27:30.297Z",
  "state": "upload_completed",
  "title": "Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe! #Shorts",
  "videoUrl": "https://youtube.com/shorts/atw6R7iSY88",
  "visibility": "PUBLIC",
  "matrixChannelId": "2",
  "channelUrl": "https://studio.youtube.com/channel/UCBZVbwc7s7TeUCcOaN58oHQ"
}
```

---

## 4. FFmpeg Montaj Mimarisi (`src/media_processing/media_processor.py`)

- **Çözünürlük ve Mobil-Optimize Sinematik Filtreler (Faz 8):** `1080x1920` (`setsar=1`, `30 fps`, `yuv420p`, `libx264`, `-preset fast`, `-crf 23`), keskinleştirme (`unsharp=5:5:1.0:5:5:0.0`), canlı renk/kontrast patlaması (`eq=contrast=1.15:saturation=1.2:brightness=0.05`) ve dinamik `zoompan=z='min(zoom+0.0015,1.5)':d=1`.
- **Bellek Dostu Döngü:** FFmpeg `loop` filtresi yerine girdi seviyesinde `-stream_loop` + `-t` kullanılarak bulut sunucularında RAM taşması (OOM) tamamen engellenir.
- **Altyazı Stili (`output/final.ass` & `force_style`):** YouTube mobil arayüz butonlarının altında kalmaması için güvenli bölgeye (`FontName=Montserrat-Bold,FontSize=56,PrimaryColour=&H0000FFFF,Outline=5,Shadow=3,Alignment=2,MarginV=250`) konumlandırılır.
- **Ses Miksajı:** Seslendirme (`1.0` ses seviyesi) + arka plan müziği (`0.12` ses seviyesi, son 1.5 saniyede `afade=t=out`) `amix=inputs=2:duration=first` ile birleştirilir.

---

## 5. Playwright YouTube Studio Seçici Haritası (`youtube_studio_uploader.js`)

| Adım | Kullanılan Birincil Seçiciler |
| :--- | :--- |
| **Yükleme Modalı Açma** | `ytcp-button#create-icon`, `ytcp-icon-button#upload-icon`, `tp-yt-paper-item#text-item-0`, ` studio.youtube.com/channel/{ID}/videos/upload?d=ud` doğrudan URL yedeği |
| **Dosya Yükleme** | `input[type="file"]` |
| **Başlık & Açıklama** | `ytcp-social-suggestions-textbox#title-textarea #textbox`, `ytcp-social-suggestions-textbox#description-textarea #textbox` |
| **Çocuklara Özel Değil** | `tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]` |
| **İleri Adımları (3×)** | `ytcp-button#next-button` |
| **Herkese Açık (`PUBLIC`)** | `tp-yt-paper-radio-button[name="PUBLIC"]`, `#public-radio-button`, `input[value="PUBLIC"]` |
| **Yayınla & Ek Onaylar** | `ytcp-button#done-button` -> varsa `ytcp-prechecks-warning-dialog #secondary-action-button` / `ytcp-confirmation-dialog #confirm-button` / `button:has-text("Yine de yayınla")` |

---

## 6. Faz 10 — Otonom "Ölü Ağırlık" Temizleyici (`prune_low_performers.js`)

### 6.1 Genel Akış

```
[cron '0 * * * *']  hourly_pruner.yml
        │
        ├─ matrix: channel_id ['1'..'10']  (fail-fast: false, job-level concurrency: pruner-studio-lock)
        │
        ├─ Secrets: ENV_FILE_<id> / COOKIES_JSON_<id> / STORAGE_STATE_JSON_<id>  (fallback: ENV_FILE / COOKIES_JSON / STORAGE_STATE_JSON)
        │
        ├─ xvfb-run -a --server-args="-screen 0 1366x900x24" node prune_low_performers.js
        │        │
        │        ├─ 1) YouTube Studio → /channel/{UC...}/videos/short  (+ /videos/upload)
        │        ├─ 2) Satır taraması: ytcp-video-row → .tablecell-views / .tablecell-date
        │        ├─ 3) Yaş çözümleme: RSS (kesin) → prune_state.json (kesin) → Studio tarihi (muhafazakâr)
        │        ├─ 4) Karar: yaş ≥ 60 dk VE izlenme < 100  →  HEDEF
        │        ├─ 5) Silme: open-menu-button → tp-yt-paper-item[test-id="delete"] →
        │        │          #confirm-checkbox #checkbox → #confirm-button → satır listeden kayboldu mu (doğrulama)
        │        └─ 6) Çıktı: prune_report.json + prune_state.json (artifact + repo)
        │
        └─ git commit "Faz 10 Auto-Pruner: Saatlik ölü ağırlık temizlik raporu [skip ci]"
```

### 6.2 Seçici Haritası (canlı kanalda doğrulandı — `UCBZVbwc7s7TeUCcOaN58oHQ`)

| Adım | Seçici | Not |
| :--- | :--- | :--- |
| Satır | `ytcp-video-row` | `ytcp-video-list-cell` **yoktur** (hücreler `div[role="cell"].cell-body`) |
| Başlık | `#video-title` | Video ID: `a[href*="/video/{ID}"]` |
| İzlenme | `.tablecell-views` | Düz sayı (`3`, `142`); binlik ayırıcı `,`/`.` karışıklığı `parseTrNumber` ile çözülür |
| Yayın tarihi | `.tablecell-date` (+ `.cell-description` → `Yayınlandı` / `Yüklendi`) | Mutlak tarihte 23:59 varsayılır |
| Görünürlük | `.tablecell-visibility` | `Herkese açık` / `Gizli` |
| Menü | `ytcp-icon-button.open-menu-button` | `aria-label="Seçenekler"` |
| Silme | `tp-yt-paper-item[test-id="delete"]` | Metin **"Tamamen sil"** (sadece "Sil" değil!) |
| Onay kutusu | `ytcp-confirmation-dialog #confirm-checkbox #checkbox` | `aria-checked="false"` → `true` yapılmalı |
| Onay butonu | `ytcp-video-delete-dialog #confirm-button` | "Tamamen sil" |

> **Tuzak:** `ytcp-video-delete-dialog` ve `ytcp-confirmation-dialog` sarmalayıcıları Playwright'e `visible=false` görünür (`display:contents`); bu yüzden **içindeki** `#confirm-button` / `#confirm-checkbox` hedeflenir.

### 6.3 Matris Notu

10 matris işi de aynı YouTube hesabını (`COOKIES_JSON_1..10` = aynı kanal) kullandığı için temizlik işleri `concurrency.group = pruner-studio-lock` ile **sıraya alınır**; aynı anda tek Studio oturumu açılır, böylece satır kayması kaynaklı yanlış silme riski ortadan kalkar.

---

## 7. Faz 11 — Viral Metadata + AI Kapak Akışı

```
content_engine.py
   ├─ build_llm_prompts()      -> hook | script_text | cta_line | thumbnail_prompt | viral_hashtags
   ├─ validate_and_normalize_scenario()
   │      ├─ sanitize_hashtag() / tr_lower()      (Türkçe + Latin doğru küçük harf)
   │      ├─ lookup_curated_hashtags()            (23 başlığa elle seçilmiş 3'er hashtag)
   │      └─ açıklama montajı: affiliate CTA → CTA → gövde → hashtag'ler
   └─ script.json  { description, cta_line, thumbnail_prompt, viral_hashtags, ... }

youtube_studio_uploader.js
   ├─ buildFinalDescription()            (aynı sıralama, idempotent)
   ├─ generateAiThumbnail()              (pollinations.ai -> ffmpeg 1080x1920)
   └─ uploadCustomThumbnail()            (ytcp-thumbnail-uploader input[type=file])
```

### 7.1 Kapak Yükleme Seçici Haritası (canlı kanalda doğrulandı)

| Adım | Seçici | Not |
| :--- | :--- | :--- |
| Küçük resim bölümü | `ytcp-video-thumbnail-editor` | `#autogen-thumb-label` = "Küçük resim" |
| Dosya alanı | `ytcp-thumbnail-uploader input[type="file"]` (`accept="image/jpeg,image/png"`, `#file-loader`) | Gizli input — `setInputFiles` ile doğrudan beslenir |
| "Dosya yükle" butonu | `ytcp-video-custom-still-editor` | Tıklanınca da aynı dosya alanı açılır |
| Özel kapak doğrulaması | `ytcp-video-custom-still-editor` varlığı | Yüklemeden sonra "Videodan seç" → "Seçenekler"e döner |
| Otomatik kapak (fallback) | `ytcp-thumbnail-editor #select-button` | Özel kapak yoksa YouTube kareyi seçer |

### 7.2 Cron Kilidi Kırma (Çift Kaynaklı Tetikleme)

```
cron (schedule)  ──(çalışıyorsa)──>  doğrudan çalışır
        │
        └──(çalışmıyorsa)──> cron-kick job'ı workflow_dispatch ile sonraki dilimi tetikler
                                   (slot_epoch = bir sonraki 15dk dilimi; iş başında sleep ile bekler)
```
- Tetikleyici kontrolü: `GET /repos/{repo}/actions/workflows/{file}/runs?event=schedule&per_page=1`
- `workflow_dispatch` **GITHUB_TOKEN ile tetiklenebilir** (GitHub'ın "GITHUB_TOKEN olayları yeni çalıştırma oluşturmaz" kuralının istisnasıdır).
- `[skip ci]` içeren commit mesajları zamanlayıcıyı sessizce atladığı için otomatik commit mesajlarında **kullanılmaz**.
