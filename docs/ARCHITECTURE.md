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
