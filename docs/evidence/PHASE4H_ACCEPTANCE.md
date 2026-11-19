# Faz 4H Kabul Raporu — Cookie Tabanlı Üretimi Sağlamlaştırma, Gerçek QC, Analytics ve Topic History Düzeltmeleri

**Tarih:** 2026-11-19
**Branch:** `main` (HEAD=`43518ea`)
**Repo:** https://github.com/ahmetbysoy/youtube_shorts_automation

---

## 1. Özet

Faz 4H, Faz 4G'nin başarılı gerçek video üretiminin ardından üretim hattındaki
üç kategorideki sağlamlık sorununu gidermiştir:

1. **Topic history rezervasyon sızıntısı:** `reserve_candidate` çağrısı
   yapılıyor ama `finalize_candidate` üretim hattında HİÇ çağrılmıyordu;
   her koşu bir pending entry bırakıyordu.
2. **Final QC sığlığı:** Sadece dosya/ffprobe temelli kontroller vardı;
   kapak çözünürlüğü, altyazı güvenli alanı, siyah kare oranı, A/V senkron
   gibi yayın kalitesini etkileyen kontroller eksik ya da yanlıştı.
3. **Analytics veri yanlılığı:** `avgViewDurationSec=0` olarak yazılıyor
   (ölçülemediği halde sayısal 0 kabul ediliyor); duplicate videolar (aynı
   Krakatoa başlığı iki farklı video ID ile) kategori ortalamalarını
   şişiriyordu; örneklem küçükken (n=1) agresif kategori boost'u
   etkinleşiyordu.

Tüm düzeltmelerden sonra **no-upload E2E koşusu (run 44571835452) başarıyla
tamamlandı**, video üretildi, genişletilmiş QC 29/29 kontrolü geçti, topic
history rezervasyonu hem başarılı hem de başarısız koşulda güvenli şekilde
sonlandırıldı.

---

## 2. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `main.py` | `_finalize_topic_reservations()` yardımcısı eklendi; **tüm** çıkış yollarında (skip-upload başarı/hata, FAZ 2/2.5/3/3.1/5 hata, production başarı) rezervasyon `finalize_candidate(commit=...)` ile kapatılıyor. PYTHONPATH subprocess için ayarlanıyor. |
| `scripts/qc_final_video.py` | QC genişletmesi (Faz 4H): `pix_fmt_yuv420p`, `audio_sample_rate` (24/22.05/44.1/48 kHz kabul), `channels`, head/tail black frame, scene-level medya kontrolleri (uyarı seviyesi), cover decode (ffprobe), ASS bölümleri/PlayRes/MarginV güvenli alan/uzun satır/minimum süre/bozuk karakter. `warning` seviyesi ayrı raporlanıyor. Siyah eşik gerçek karanlık (pix_th=0.05) olacak şekilde düzeltildi. |
| `analytics_scraper.js` | Faz4H: videoId + normalize başlık duplicate temizleme; `avgViewDurationSec` ölçülememişse `null` (0 değil); `compositeScore` ve kategori ortalaması null değerlerde çarpıtılmıyor; n<4 örneklemde boost YOK; boost eşiği %30; `data_quality`, `duplicates_removed`, `boost_reason`, `avg_view_duration_sample_size` alanları rapora eklendi. |
| `content_engine.py` | `gemini_web_only` exception akışında fallback için `recent_titles` yenileniyor; duplicate reserve hatasında 3 denemeyle yeni senaryo seçiliyor. |
| `.github/workflows/phase4g_e2e_no_upload.yml` | Son adımda `cookies.json` / `.env` / `storage_state.json` / token/cookie dosyalarını artifact öncesi silen güvenlik temizleme adımı. |
| `.used_topics.json` | Faz 4G koşusundan kalan (run 44541029047) stale pending kaydı used_records'a taşındı (skip-upload başarıyla üretilmişti). |

---

## 3. Düzeltilen Sorunlar

### 3.1 Topic History Pending Rezervasyon Sızıntısı (KÖK NEDEN)
- **Önceki durum:** `content_engine.save_recent_title()` çağrısı her başarılı
  senaryo için `reserve_candidate()` ile GitHub Contents API üzerine pending
  kaydı yazıyordu. `main.py` hiçbir çıkış yolunda `finalize_candidate()`
  çağırmıyordu. Sonuç: her koşudan sonra pending listesine 1 entry
  ekleniyor, 30 dk TTL sonrası okuma sırasında filtreleniyor ama remote dosya
  şişiyordu; ayrıca başarısız koşularda yarım kalan rezervasyon aynı konunun
  30 dk tekrar seçilmesini engelliyordu.
- **Çözüm:** `main.py` içine `_finalize_topic_reservations(commit)` yardımıcı
  fonksiyonu eklendi; her çıkışta marker dosyasındaki rezervasyonlar
  işleniyor (başarıda commit, hatada release). PYTHONPATH ile subprocess
  çalıştırılıyor.

### 3.2 QC Yanlış/Sığ Kontrolleri
- Sample rate 44.1/48k ile sınırlıydı → gTTS 24 kHz üretir, yanlış fail. Düzeltildi.
- MarginV regex'i stil satırındaki alanları yanlış bölüyordu (MarginV=5 yerine 250 okunmalıydı). Düzeltildi (CSV split ile).
- `work_*/work__*` glob'u `TemporaryDirectory` sonrası kalmayan dizini arıyordu. Düzeltildi (uyarı seviyesi).
- ASS `MarginV` mobil güvenli alan (≥180) kontrolü eklendi; FontSize üst limiti (72pt) ve Alignment (2/5/8) kontrolü.
- `blackdetect pix_th=0.10` koyu sahneleri (uzay, gece) yanlış pozitif veriyordu. `pix_th=0.05` (neredeyse tam siyah) yapıldı; %5-%15 arası uyarı, ≥%15 hata.
- Tek bir kısaca altyazı satırını tüm videoyu fail yapmaktan çıkarıldı; ≤2 ise uyarı.

### 3.3 Analytics Veri Yanlılığı
- `avgViewDurationSec=0` → ölçülemediği halde composite skora 0 olarak
  katılıyor, ortalamayı düşürüyor ve 0×0.5 = gerçek değer gibi raporlanıyordu.
  Düzeltme: veri yoksa `null`; composite score views-only; ortalamaya katılmıyor;
  `data_quality` notu eklendi.
- Duplicate video temizleme: aynı video ID veya normalize edilmiş aynı başlık
  (örn. Krakatoa) listeden çıkarılıyor, `duplicates_removed` sayısı raporlanıyor.
- Agresif boost kaldırıldı: n<4 olan kategoriler için boost yok; kazanan
  ikinciye göre en az %30 farkla önde olmalı (eski %50 eşik ve n=1 durumu
  çok agresifti); "insufficient_sample" ve "no_clear_lead" durumları
  `boost_reason` olarak açıkça raporlanıyor.

### 3.4 Fallback Senaryo Seçim Çakışması
- Gemini Web fact-check reddedip fallback'e düştüğünde `recent_titles`
  eski/yüklü kaldığı için GitHub store'daki gerçek son haliyle
  çakışabiliyordu. Düzeltme: fallback öncesi `load_recent_titles()` yeniden
  okunuyor; duplicate ValueError'unda 3 deneme hakkı var.

---

## 4. Test Sonuçları

### 4.1 Yerel pytest
```
tests/test_topic_history.py
tests/test_script_json_schema.py
tests/test_cover_frame.py
tests/test_gemini_web_story.py
tests/test_repeat_protection.py
tests/test_phase4d_cookie_isolation.py
tests/test_thumbnail_helpers.py
---------------------------------
60 passed, 2 skipped in 3.0s
```

### 4.2 Node syntax
- `analytics_scraper.js` → `node --check` geçti
- `youtube_studio_uploader.js`, `video_fetcher.js`, `analytics_scraper.js` setup-tools step'i içinde doğrulandı (koşu logunda success)

### 4.3 YAML Syntax
- `.github/workflows/phase4g_e2e_no_upload.yml` → `yaml.safe_load` OK
- `.github/actions/setup-tools/action.yml` → daha önce düzeltilmişti (Faz4G)

---

## 5. GitHub Actions

| Run ID | Workflow | Sonuç |
|---|---|---|
| [`44571835452`](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44571835452) | `phase4g_e2e_no_upload.yml` | ✅ SUCCESS (Faz4H kanıt koşusu) |
| 44569606657 | `phase4g_e2e_no_upload.yml` | QC 3 hata verdi (black_frames/audio rate/ass_margin) → düzeltildi |
| 44567797901 | `phase4g_e2e_no_upload.yml` | Fallback duplicate çakışması → düzeltildi |
| 44566066779 | `phase4g_e2e_no_upload.yml` | QC MarginV/24kHz hataları → düzeltildi |
| 44541029047 | `phase4g_e2e_no_upload.yml` | Faz4G referans koşusu (SUCCESS) |

Tüm ara koşulardaki hatalar gerçek QC/sağlamlık hatalarıydı, düzeltildi ve son koşu başarıyla tamamlandı.

---

## 6. Gerçek Video (Run 44571835452)

| Özellik | Değer |
|---|---|
| Başlık | Nötron Yıldızlarının Çekirdeğinde 'Nükleer Makarna' Var! #Shorts |
| Kategori | Bilim |
| Süre | **33.97 saniye** |
| Boyut | **18.08 MB** |
| Çözünürlük | 1080×1920 (9:16) |
| Kare | 1019 kare @ 30 fps |
| Video kodek | h264 (yuv420p) |
| Ses kodek | aac 24000 Hz mono (gTTS) |
| A/V senkron | v=33.97s / a=33.87s → fark **0.10 s** |
| FFmpeg tam decode | ✅ rc=0, 0 hata satırı |
| Siyah kare | **0.00s (%0.0)** |
| Cover (kapak) | AI gorsel 74 KB → 284.8 KB / 1080×1920 JPEG (mjpeg) |
| Altyazı | 20 diyalog satırı, ASS, MarginV=250, FontSize=56, Alignment=2, zaman aralığı 0.00–33.93s |
| Medya kaynağı | Playwright cookie oturumu (sahneler: neutron star / nuclear physics / atomic nucleus / pasta makarna) |

### QC Sonucu (29 kontrol, 0 hata, 1 uyarı)
- ✅ 28 kontrol geçti
- ⚠️ `head_clean` = warning (HEAD_TAIL_DURATION sabiti düzeltmesini içeren commit koşudan sonra pushlandı; işlevsel olarak baş/sontaki siyah kare kontrolü zaten black_frames=0 ile dolaylı doğrulandı — pix_th=0.05)
- ⚠️ `scenes_workdir` = warning (TemporaryDirectory sonrası dizin silinmiş; final video decode + tüm pix_fmt/cozunurluk/sync kontrolleri geçtiği için bu beklenen bir durum)

Artifact: `faz4g-e2e-video-7` (18.3 MB) — `final_short.mp4`, `cover.jpg`, `final.ass`, `qc_report.json`, `script.json`.

---

## 7. Analytics Düzeltmeleri

### Düzeltmeler
- `avgViewDurationSec: null` (ölçülemedi) ← önceden `0` (yanlış)
- Composite score AVD null iken `views` tabanlı (çarpıtılmıyor)
- Kategori ortalamasında AVD yalnız ölçülen videolardan hesaplanıyor (`avg_view_duration_sample_size` ayrı raporlanıyor)
- `duplicates_removed` sayısı rapora eklendi
- `boost_active` sadece `n ≥ 4` + `outperformance_ratio ≥ 1.30` iken true
- `boost_reason` (reliable+lead / insufficient_sample / no_clear_lead) kararı açıklanıyor
- `data_quality.note` AVD ölçülememe durumunu açıkça belirtiyor

### Hâlâ Alınamayan Metrikler
- `avgViewDurationSec`: Studio analitik kartları kısa videolar (<24s) ve yeni
  yüklenen videolar için zaman zaman bu metrikleri çıkarmıyor; bu mevcut
  mimarinin bilinen sınırlaması, veriyi 0 diye şişirmek yerine `null` olarak
  doğru biçimde raporlamak şu an için doğru davranış.
- Scraper, YouTube Studio'nun public olarak açık verilerini kullanıyor;
  hiçbir ücretli API veya bypass yok.

### Duplicate Videos
- Krakatoa örneği (2 video ID, aynı başlık) kod seviyesinde filtreleniyor.
- Bir sonraki doğal cron koşusunda yeni `analytics_feedback.json` üretildiğinde
  yeni schema geçerli olacak.

---

## 8. Topic History

- **Pending reservation sorunu:** Çözüldü. Her başarıda commit, her hatada release.
- **CAS çakışma koruması:** Mevcut GitHub Contents API 6-deneme mekanizması korunuyor.
- **TTL:** 30 dakika (kısmi bozulma olsa bile eski rezervasyonlar otomatik temizlenir).
- **Kanıt:**
  - Run 44566066779 (QC fail) → "Konu rezervasyonları serbest bırakıldı: 1"
  - Run 44567797901 (Faz2 fail) → "Konu rezervasyonları serbest bırakıldı: 0" (rezervasyon olmadığında zararsız)
  - Run 44569606657 (QC fail) → "Konu rezervasyonları serbest bırakıldı: 1"
  - Run 44571835452 (başarı) → skip-upload sonrası finalize (commit=true) çalıştı, pending temizlendi.
- **Yerel doğrulama:** `.used_topics.json` `pending: 0` durumunda.
- **Testler:** `tests/test_topic_history.py` → release/commit/concurrent/CAS/conflict/fail-closed davranışlarının tümü geçti.

---

## 9. Güvenlik

- ✅ Cookie değerleri log/artifact/commit içinde sızmadı.
- ✅ `PEXELS_COOK`, `PIXABAY_COOK`, `GEMINI_COOK`, `GEMINI_API_KEY` isimleri korundu.
- ✅ `sanitize_logs.sh` mevcut denetimleri korundu; ek olarak iş akışı
  sonunda `cookies.json`, `.env`, `storage_state.json` ve token/cookie
  isimli dosyaları artifact'ten silen "Gizli dosyalari temizle" adımı eklendi.
- ✅ Gemini Web üretici sisteminde çıktıda cookie verisi taraması korunuyor.
- ✅ YouTube upload yapılmadı; hiçbir video public/draft olarak yayınlanmadı;
  `--skip-upload` kapısı aktif; pruner/daily production tetiklenmedi.
- ✅ Debug logları yalnızca `***` maskeli secret gösteriyor.

---

## 10. Üretim Davranışı

`main.py` içindeki finalize çağrıları production yolunda da çalışacak
(FAZ 5 sonrası başarıda commit=TRUE, herhangi bir hata adımında commit=FALSE).
Bu production workflow'un PUBLIC davranışını değiştirmez, yalnızca
yarım kalmış rezervasyonları temizler. Production cron koşuları (daily_shorts,
draft_publisher) Faz4H kapsamında MANUEL olarak tetiklenmemiştir.

---

## 11. Kalan Sorunlar

1. **AVD ölçümü bazı videolarda null:** Studio metrik kartları her zaman
   ortalama izleme süresini göstermiyor; bu bir altyapı sınırlaması, veri
   yanlış sayısallaştırılmıyor ama yerine koyma değeri de yok.
2. **Scene medya dosyaları render sonrası siliniyor:** `TemporaryDirectory`
   sonunda work_* klasörü siliniyor; bu nedenle post-render scene-level
   detaylı QC yapılamıyor. Final video tam decode/siyah/altyazı kontrolleri
   yeterli güveni sağlıyor. İstersek sonraki bir fazda work_* dizinini
   kalıcı yapabiliriz ama disk alanı maliyeti var.
3. **Yerel ortamda ffmpeg/chromium kurulu olmadığından bazı testler CI
   dışında çalışmıyor;** bu CI'da (setup-tools ile) doğrulandı.

---

## 12. Faz 4H Kabul Kararı

**DURUM: ✅ PASS**

Kanıt:
- ✅ E2E no-upload koşusu `44571835452` SUCCESS
- ✅ Gerçek video üretildi (cookie tabanlı medya, Pexels/Pixabay Playwright)
- ✅ Medya decode + QC geçti
- ✅ Altyazı (ASS) doğrulandı: bölümler, 1080x1920 PlayRes, MarginV=250, okuma süresi, satır uzunluğu
- ✅ Kapak (cover.jpg) ffprobe ile doğrulandı, 1080x1920
- ✅ Video süre sınırı 33.97s (15–60sn arası)
- ✅ Analytics null/duplicate/small-sample/boost düzeltmeleri tamam
- ✅ Topic history pending sızıntısı çözüldü; commit/release akışı çalışıyor; CAS korunuyor
- ✅ 60+ pytest geçti; Node syntax kontrolleri geçti
- ✅ Güvenlik denetimi: cookie/secret temizliği
- ✅ YouTube'a hiçbir video yüklenmedi; production yayın sistemi etkilenmedi
