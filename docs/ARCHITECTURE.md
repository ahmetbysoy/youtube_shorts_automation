# Sistem Mimarisi ve Teknik Veri Sözleşmeleri (`ARCHITECTURE.md`)

> **Güncel Faz 5 — 2026-11-16: Gerçek TTS WordBoundary zamanlaması UYGULANDI / KABUL BEKLİYOR.** Commit `7195e54` + sertleştirme yamaları. Fail-closed timing, SRT sahne sınırları, sessizlik ve clipping QC, 38 test (5'i gerçek edge-tts ağ entegrasyonu) geçti. CI kanıtı (phase4g_e2e_no_upload) bekleniyor. [Faz 5 kabul raporu](evidence/PHASE5_ACCEPTANCE.md). Faz6 başlatılmadı.
>
> **Tarihsel Faz 4C — 2026-11-18: Faz4B NOT_ACCEPTED.** Kaynak [`14f7896`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/14f78962f2444e9d03fe0d0caf9b22efff06d927); yeni CI [44313713933](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313713933) **361 Python + 16 alt test**, hedefli tekrar **35/182/8**, **16 Node** geçti. Kullanıcının yeni cookies’i **API kullanılmadan** [44313751238](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313751238) Actions koşusunda test edildi: preflight **8 Pexels + 7 Pixabay eşleşen cookie kaydı**, iki ayrı browser araması **HTTP403 / blocked_unverified**. Commons iki CC BY videoda source/deed/download **200**, tam byte/SHA256 ve container probe geçti; **full_decode_failed**, render/final QC not_reached. API/ENV_FILE bu run’da okunmadı; API key eksikliği cookie testi için blocker değildir. Yeşil CI/offline fixture veya eski yerel Commons, yeni canlı kabul yerine geçmez. Önceki iki-run history/gerçek409 proof’unun üç blob’u aynı; cleanup dört404 ile salt-okur tekrar doğrulandı, yeniden dispatch edilmedi. **22 protected blob, 26 topic/0pending** korundu; üretim/yayın/silme yok. [12 başlıklı yeni rapor](evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) · [JSON](evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json).

> **Tarihsel Faz4B snapshot’ı:** Kaynak `59e2c79`, CI44301070745 **301+16/35/122/8/11Node**; eski yerel canlı Commons tam zinciri geçti, eski Actions44301095341 stock403 ve generic Commons download/decode failure verdi. Bu eski kayıtlar yeni koşu değildir; [Faz4B raporu](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) ve [JSON](evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json) değiştirilmeden korunur.

> **Tarihsel Faz 4 sonucu (2026-11-18):** Strict storyboard selector/common provider/license/manifest/dedup ve ayrı media history uygulandı. Son kaynak [`e4d1144`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/e4d1144116887b31c459bb6a7e171589d214c687) üzerinde CI [44288761602](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761602) **233 + 16**, ayrı 62 Faz 4/35 Faz 3/5 Node parser başarılı. Live [44288761461](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761461) **partial_provider_evidence**: Commons iki PD still + decode/consumer geçti; stock runtime API key yok, cookie file var, browser 403. **Tam kabul GEÇMEDİ**, PUBLIC hazırlığı iddia edilmez. Metadata relevance ≠ visual verification; provisional duration ≠ TTS alignment. [Kanıt](evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md), [ayrıntılı medya kontratı](PHASE4_MEDIA_ENGINE.md), [baseline](PHASE4_MEDIA_BASELINE.md).


> **Sürüm:** Güncel çalışma durumu (Gemini Web route + mevcut `PUBLIC` üretim hattı)
>
> **Son Güncelleme:** `2026-11-18`

Bu doküman, `youtube_shorts_automation` boru hattındaki modüllerin iç yapısını, dosya sözleşmelerini (data contracts), FFmpeg filtre grafiğini ve Playwright DOM seçicilerini açıklar. Devir teslim ve operasyonel kurallar için kök dizindeki [`AI_HANDOFF.md`](../AI_HANDOFF.md) dosyasına bakın.

---

> **Güncel durum — 2026-11-18:** Bu bölüm, eski faz anlatılarından önce geçerli olan operasyonel özettir. Ayrıntılı kanıt: [Faz 0 baseline](evidence/FAZ0_BASELINE_2026-11-17.md) ve [canlı TODO](GEMINI_AUTONOMOUS_SHORTS_TODO.md).
>
> - Aktif yayın workflow'u `.github/workflows/daily_shorts.yml`; kanal job'ları `max-parallel: 1` ile sıralıdır. Eski 3'lü paralel matris diyagramı güncel değildir.
> - Güncel sıra: `main.py` → `content_engine.py --gemini-web-only` → cookie-only Gemini Web, exact quote + independent deterministic semantic/numeric checks and storyboard → critical rejection/error uses the existing fallback → TTS and `script.json` v2 → media → existing Studio uploader. Daily workflow passes `GEMINI_COOK` only in process env; no paid text endpoint.
> - `quote_match` (exact substring) and `semantic_support` (relation/lexical + number/date/unit checks) are distinct. V2 supports `verified/partial/rejected/unavailable`, preserving legacy enum values. The user-approved path for `partial` drafts is unchanged; `partial` is never relabeled `verified`.
> - `.used_topics.json` retains legacy titles and migrates to v2 `{used_titles, used_records, pending}`. `save_recent_title` reserves via GitHub Contents API SHA-CAS before generation continues; workflow success commits, failure releases; bounded conflict retry and 30m orphan TTL. Unreadable history is fail-closed. Channel ordering/concurrency/uploader/publish semantics are unchanged.
> - Phase 3 CLIs run as modules (`python -m scripts.topic_history`, `python -m scripts.topic_persistence_probe`) so sibling imports resolve on a clean runner. The small probe explicitly installs pinned `requests`. CI unsets `GITHUB_REPOSITORY`, `GH_TOKEN` and `GITHUB_TOKEN` in the unit-test child process via `env -u`; a YAML env override cannot clear reserved GitHub defaults. Production still fails closed on incomplete remote-history configuration. Runtime marker/lock files are ignored.
> - Kapak gömme adımı mevcut davranışta best-effort'tur; hata yayını tek başına durdurmaz. Bu davranış Faz 0'da değiştirilmemiştir.
> - Uploader, Publish tıklamasını tek başına başarı saymaz; video ID'sini Studio Shorts listesindeki PUBLIC durumuyla doğrular.
> - Prior real Gemini Web dry-run [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017), SHA `57166f8`, remains successful: 58 words, 5 scenes, 3 claims, `draft_only=true`, `publish=false`. This is earlier model evidence, not a live-model test of Phase 3. New-code Ubuntu 26 CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) on `0dee88e` succeeded: **171 tests + 16 subtests** and a separate **35-test** targeted suite. The real Wikipedia HTTP probe returned 200 with matching canonical page identity. Two distinct Actions runs [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) (reserve) and [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) (verify) persisted, observed and released the reservation; existing 25 titles were unchanged, with no used probe title. **Phase 3 acceptance passed within this non-publishing scope.** [Actions evidence](evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md); [local-only evidence](evidence/PHASE3_LOCAL_EVIDENCE_2026-11-18.md).
> - `hourly_pruner.yml` gerçek video silebilir; `draft_publisher.yml` taslakları PUBLIC yapabilir. Test amacıyla bu workflow'lar tetiklenmemelidir.
> - Repository Secret değerleri okunmadı/değiştirilmedi. Kullanıcının sağladığı, ignore edilen dosyadaki GitHub credential yalnız bellekte kullanıldı; Git config/URL, log veya artifact’e yazılmadı. Üç yeni başarılı koşunun loglarında supplied credential veya maskelenmemiş GitHub/Google key pattern bulunmadı; bu koşular artifact yüklemedi. Cookie içeriği loglanmadı; başarılı eski Gemini probe yalnız presence boolean kaydetti.

```text
 daily_shorts.yml
   └─ production_gate.sh
       └─ max-parallel: 1 → python main.py --channel_id N
           ├─ content_engine.py --gemini-web-only → fallback on error
           ├─ script.json v2: sources/fact_check/storyboard → pre-media validator
           ├─ media_processor.py → storyboard varsa strict scenes; yoksa legacy
           ├─ post-media validator: manifest kapsamı/credit → durdurma
           ├─ embed_cover_frame.py (best-effort)
           └─ youtube_studio_uploader.js → Studio'da aynı video ID + PUBLIC doğrulaması
```

## 1. Tarihsel Uçtan Uca Boru Hattı (Pipeline) Akışı

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
│   ├── content_generation/        # Ayrı eski writer/export; root content_engine.py sarmalayıcısı değil
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

### `script.json` (içerik → medya → uploader)

Güncel kaynak `schemas/script.schema.json`: legacy v1 + v2. Root producer v2 sources/fact_check/storyboard metadata taşıyabilir; strict media sonrasında opsiyonel `scene_media` + `media_selection` çifti eklenir. Ayrıntı §9–10 ve [producer/consumer envanteri §7](PHASE1_SCRIPT_JSON_INVENTORY.md). **Aşağıdaki duration_seconds/subtitle_file örneği tarihsel temsildir**, bugünkü producer alanları `audio_duration_sec` ve `srt_file` olarak korunur.
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

Aşağıdaki loop/crop/zoompan özeti **storyboard’suz legacy** yoldur. Yeni strict storyboard dosyaları contain/letterbox ile çerçeveyi korur, video loop etmez; minimum ölçülen süre/çözünürlük/oran ve full decode zorunludur. Strict JPEG kaynaklar limited range ve 30 FPS CFR normalize edilir; final yuv420p QC gevşetilmedi. Ses miksajı ve subtitle renderer korunur; gerçek TTS scene hizalaması Faz 5’te açık kalır.

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

---

## 8. Faz 11 — Sıralı Üretim ve Kanal Benzersizlik Katmanı

```
daily_shorts.yml
   │
   ├─ job: channel-map ── scripts/channel_map.sh
   │      ├─ 10 kanalın cookies+state SHA256 hash'i
   │      ├─ aynı hash = aynı hesap  → AYIKLANIR (günlük kota korunur)
   │      ├─ çıktı: distinct_csv=1,3,7   next_channel=1   distinct_count=3
   │      └─ NOT: GitHub "[ ] { }" içeren job output'unu "secret" sanıp ATAR
   │              → matris virgüllü liste olarak taşınır, iş akışında
   │                fromJSON(format('["{0}"]', join(distinct_csv, '","'))) ile çevrilir
   │
   ├─ job: build-and-upload   (max-parallel: 1 → TEK video tamamlanmadan diğeri başlamaz)
   │      video → başlık/açıklama(CTA+hashtag) → AI kapak → tags → görünürlük → YAYIN(PUBLIC)
   │
   └─ job: cron-kick
          ├─ önceki turun kotaya takılıp takılmadığı loglar kontrol edilir
          ├─ kota doluysa  → sonraki deneme 4 saat sonra (boşuna üretim yok)
          ├─ kota yoksa    → sonraki 15 dakikalık dilim
          └─ TEK kanal tetikler (target_channel = sıradaki benzersiz kanal)
```

### 8.1 Neden "10 kanal" yerine "1 kanal" üretim?
GitHub Secrets'taki `COOKIES_JSON_1..10` **aynı hesabın** oturumudur (hash testi ile doğrulandı:
10 kanalın 10'u da `hash a4ae91d03ee1`). 10 paralel job aynı kanala 10 video yüklemeye
çalışır → ilk birkaç video yayınlanır, kalanı günlük kota uyarısıyla atlanır (boşuna CPU/Harita).
Benzersizlik katmanı bunu otomatik olarak engeller: **1 ayrı hesap = 1 kanal üretim**.

### 8.2 Sıralı Tam Döngü garantisi
`max-parallel: 1` sayesinde matris job'ları tek tek çalışır. Bir video için:
`içerik → ses → video → başlık → açıklama (affiliate CTA + CTA + 3 hashtag) → AI kapak →
video tags → çocuk güvenliği → görünürlük(PUBLIC) → YAYIN` tamamlanmadan diğer kanal başlamaz.


---

## 9. Faz 1 — script.json sözleşmesi (2026-11-17)

- Şema: `schemas/script.schema.json` — JSON Schema Draft 2020-12.
- Legacy uyumluluk: `schema_version` içermeyen mevcut payload'lar v1 olarak doğrulanır.
- Güncel üretim: `content_engine.py` yeni payload'lara `schema_version: "2.0"` ve UUID `generation_id` ekler.
- Eski alanlar (`visual_keywords`, `word_timestamps`, medya ve TTS metadata alanları) korunur.
- `sources`, `fact_check` ve `storyboard` alanları schema v2'de opsiyoneldir. Fallback payload'larında legacy uyumluluk sürer; Gemini Web payload'ında bu alanlar üretilip script.json'a taşınır.
- Testler: `tests/test_script_json_schema.py` legacy/v2 ve hatalı veri örneklerini; `tests/test_full_pipeline_fallback.py` ise gerçek üretilen JSON'u doğrular.
- Schema doğrulayıcı `jsonschema` hem test hem runtime bağımlılığıdır (`requirements-test.txt` ve `requirements.txt`). `main.py`, medya işlemeden önce `scripts/validate_script_json.py` ile JSON'u fail-closed doğrular; hata varsa süreç 1 koduyla durur.
- 2026-11-18 Gemini Web/Faz 3 durumu: önceki gerçek cookie dry-run `44262444017` korunur. Yeni kod `0dee88e` için Ubuntu 26 CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) (**171 + 16 subtests**) ve ayrı reserve/verify Actions koşuları [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) → [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) başarılı; Faz 3 yayınsız kabul kapısı geçti. `partial` PUBLIC onayı ve uploader davranışı değişmedi. Gerçek üretim/yayın/finalize uçtan uca koşusu kapsam dışı; [kanıt ve sınırlar](evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md), [TODO](GEMINI_AUTONOMOUS_SHORTS_TODO.md).


---

## 10. Gemini Faz 4 — strict storyboard medya yolu

```text
storyboard anahtarı var (boş/bozuk olsa da legacy’ye düşme)
  → narration + primary query + ≤3 ordered alternatives, bounded plan
  → Pexels API / Pixabay API / Pixabay browser / Pexels browser / Commons
      (query başına hepsi; havuz global score, provider sırası tie-break)
  → metadata relevance + license/attribution + teknik hard gates
  → bounded HTTPS download (≤4/scene) → SHA256 + gerçek ölçüm + tam decode → gates tekrar + measured rerank
  → her scene için farklı identity/URL/hash → tam manifest/credit → ayrı history
  → atomic script JSON → contain/non-looping strict assembly → sert final QC
  → mevcut main post-media validator (tam kapsama/identity/credit)
```

Common candidate: provider/media_id/media_url/source_url/download_url/type/width/height/duration/aspect_ratio/download_status, title/description/tags, license evidence(method/URL/hash/check time)/attribution requirement/text. Eksik değer uydurulmaz. Manifest zorunlu scene alanları: `scene_id`, `selected_provider`, `selected_media_id`, `source_url`, `license`, `attribution`, `duration`, `resolution`, `aspect_ratio`, `selection_score`, `rejection_reason`, `fallback_used`. Görüntü still'inde duration null, `planned_duration` ayrıdır. Rejection/queries/score/probe da tutulur.

Hard ret'ler soft score ile geçilemez: metadata subject kanıtı yok, düşük çözünürlük, extreme oran, yetersiz video süresi, unknown/uygulanmayan lisans, kayıp atıf, same-video tekrar, corrupt/HTML download veya provider error. CC BY atfı kaybolmaz; uploader CTA/hashtag eklediğinde kesilmeyecek konservatif UTF-16 bütçe ayrılır. BY-SA/NC/ND yükümlülükleri uygulanmadan otomatik strict kabul yok; Commons supported PD/CC0/CC BY dosyalarıyla korunur. Stock terms-marker değişir/erişilemezse güvenli ret. Provider reliability skoru ölçülmüş uptime değil, bilinen source-provenance proxy'sidir.

State ikiye ayrıdır: Faz 3 `.used_topics.json` untouched; yeni `.media_history.json` local lock+fsync+atomic veya Contents blob SHA-CAS (6 bounded reread/merge/retry). 200 kayıt/100 recency, −25 penalty; distributed reservation/perceptual dedup değil. Hash-only recent hit dâhil en fazla dört indirilmiş uygun aday ölçümlerle yeniden sıralanır; tüm katalog indirilmiş gibi garanti verilmez. Gerçek iki-Actions media persistence, controlled HTTP409/reread/merge ve cleanup [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963) → [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849) ayrı ref/path’te geçti; production history hedeflenmez.

Mevcut `main.py`, PUBLIC/uploader/partial politikası, channel/concurrency, Gemini cookie-only/fallback ve kapak davranışı değişmedi. Storyboard'suz eski random/diluted query/loop ve daha zayıf lisans kontrolleri bu değişiklikle doğrulanmaz. Strict label `metadata_supported`, `visual_verification=not_performed`; örnek consumer sentetik test tone kullanır ve `timing_verified=false`. Uygulama/test ve canlı kabul aynı şey değildir; [Faz 4 raporu](evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md) kabulü açık tutar.

## 11. Üretici/tüketici sınırları ve güvenli test

[Envanter §7](PHASE1_SCRIPT_JSON_INVENTORY.md) root producer dışında bağımsız eski `src/content_generation/engine.py` writer'ını, media reader+writer'ını, main'in iki validator child'ını, cover reader'ını, Studio description builder ve API backup reader'ını kaydeder. Faz 4B’de explicit scenario/synthetic-tone ile gerçek root JSON writer → aynı run_media_pipeline wrapper → post-validator → gerçek no-AI cover → gerçek saf JS metadata zinciri yerel canlı Commons ve CI offline fixture’da geçti (§12). Canlı Gemini/TTS, Actions canlı Commons tamamlanması ve repo geneli dinamik/caller tamlığı kanıtlanmış değildir. Yeni actual pure-JS metadata testleri gerçek uploader çalıştırılması değildir; Faz 1 otomatik kapanmaz.

`phase4_media_probe.yml` artık `phase4b_media_probe` actual chain’ini çağırır; manuel/yayınsız/contents-read-only, eksik zorunlu provider coverage nonzero verir. Stock key’ler env’e yeniden export edilmez; kendi API constructor’ına gider. Browser child temel env allowlist’i ve yalnız ilgili stock cookie domain’iyle başlar; 403’te durur. Ayrı manual `phase4b_history_probe.yml` yalnız kendi job’unda contents:write alır; repository secret veya actions:write almaz. Upload-öncesi safe artifact audit’i zorunludur.

**Tuzak:** `media_processor.py` `--help` parse etmez; direkt invocation `--help` ile bile montaj başlatır ve root JSON yoksa samples'a yazabilir. Son kontrolde bu legacy-only yan etki geri alındı; kabul kanıtı sayılmadı. Benign syntax kontrolü `py_compile`/izole testtir. Gerçek `phase4_media_probe --help` ve topic-history CLI'ları güvenlidir. `main.py`, prod/pruner/publisher ve YouTube uploader bu doğrulama için çalıştırılmaz. Faz 5 ses/timing, siyah/boş kare/ses/clipping ve bütünleşik yayın gate'i ayrı/açıktır.

## 12. Faz 4B — gerçek dosya tüketimi ve izole history

```text
explicit draft fixture (NOT live Gemini)
 → actual draft_to_script_metadata → actual ROOT run_content_pipeline writer
   (TTS input boundary = synthetic tone; actual v2 generation UUID)
 → actual pre-validator CLI → SAME JSON path
 → actual run_media_pipeline → strict selection/download/probe/render/QC
 → scene_media/selection/credits/description → atomic persist/reload
 → actual post-validator CLI → actual embed_cover_frame.main --no-ai
   (isolated video/cover change; JSON SHA unchanged)
 → actual readScenarioField/buildFinalDescription extracted from unchanged uploader
   (network-free VM, UTF-16≤4900, entrypoint never evaluated)
 → QC + full AV decode + canonical Commons File/deed HTTP + motion samples
```

Bu zincir **aynı final kaynakla yerel canlı Commons** üzerinde geçti. CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745) aynı fonksiyonları offline provider/download fixture’larıyla çalıştırır. Actions canlı [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) pre-validator’dan sonra selection’da bloklandı; render/post-validator/cover/saf metadata’ya ulaşmadı. Bunlar üç ayrı kanıt sınıfıdır. Root writer/strict wrapper/renderer/cover stub edilmez; yalnız scenario/TTS dış girdileri ile provider/history/path ayarları test adaptörüdür. Eski paket writer bağımsızdır ve çalıştırılmadı.

Canonical File HTML’de aynı creator/lisans linki ve resmi CC BY deed’inde Share/Adapt/Attribution gerçek HTTP ile yerelde doğrulandı; üçüncü taraf hakları/visual semantics onayı değildir. Motion iki decoded source-content sample’ın cover dışındaki değişimidir, genel action modeli değildir.

History [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963) üç synthetic sentinel yazar; iki bağımsız client’ın kontrollü stale-SHA interleaving’i **gerçek HTTP409** üretir, core remember reread/merge yapar. Ayrı [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849) aynı blob/entry’yi gerçek Contents GET ile okur, dosya/ref’i temizler. Kaynak [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472); history kodu/probe/workflow blob’ları final [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106) ile aynıdır. Spontane paralel Actions yarışı veya distributed reservation iddiası yok. [Kanıt](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md).
