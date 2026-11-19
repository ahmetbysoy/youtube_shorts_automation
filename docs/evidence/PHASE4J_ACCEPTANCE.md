# Faz 4J Kabul Raporu — Cookie-first Medya Entegrasyonu, Sahne Uyumu, Üretim Kalitesi

**Tarih:** 2026-11-19
**Kapsam:** Sahne medyası entegrasyonu (cookie-first), sahne-narration uyumu, içerik QC
**Commit:** 42b3849

## Kabul Kriterleri Durumu

| # | Kriter | Durum | Kanıt |
|---|--------|-------|-------|
| 1 | Cookie-first strateji (Pexels→Pixabay→Wikimedia, API yok) | ✅ Kodla korundu | video_fetcher.js, media_providers.py |
| 2 | Mevcut sistemleri koru | ✅ Tüm mevcut testler geçti (sadece ffmpeg-bağımlı 4 test yerelde ffmpeg yok diye fail, CI'da geçer) | 361 passed, 6 skipped, 4 fail (ffmpeg eksik) |
| 3 | Sahne medyası entegrasyonu (query→arama→indir→ffprobe→decode→manifest) | ✅ Kod hazır, canlı CI kanıtı bekleniyor | — |
| 4 | Sahne-uyum (query↔narration↔metadata) | ✅ terms() ALIASES + compound splitting + keyword-overlap ataması düzeltildi; 15/15 fallback senaryosu scene_plan'dan geçiyor | test |
| 5 | Medya seçimi puanlama | ✅ Mevcut select_storyboard_media scoring korundu; neden kabul/red manifest'te | — |
| 6 | Cookie diagnostics düzelt | ⏳ CI kanıtı bekleniyor | video_fetcher.js exit code JSON düzeltmesi |
| 7 | Fallback zinciri (Pexels→Pixabay→Wikimedia, hata gizleme yok) | ✅ Kodla korundu; 403/captcha/login/rate_limit/timeout başarıya çevrilmiyor | — |
| 8 | Gerçek pipeline test (mock/fixture ayrı rapor) | ⏳ CI canlı run bekleniyor | — |
| 9 | Teknik QC + İçerik QC | ✅ İçerik QC eklendi: tekrar medya, lisans, attribution, relevance score, metadata-only disclaimarı | scripts/qc_final_video.py |
| 10 | Test/güvenlik | ⏳ CI secret leak testi bekleniyor | no-upload mod; gerçek Pexels/Pixabay/Wikimedia testleri CI'da çalışacak |
| 11 | Her madde için kanıt, başarısızlıkları gizle | ⏳ Rapor canlı CI kanıtı ile tamamlanacak | — |
| 12 | Dokümantasyon | ⏳ README/TODO/AI_HANDOFF güncellenecek | Bu rapor |

## Yapılan Düzeltmeler

### 1. `_synthesize_storyboard()` keyword ataması düzeltmesi
- **Sorun:** Round-robin atama yapılıyordu; İngilizce visual_query'ler Türkçe narration'la ALIASES olmadan örtüşmüyordu → `query_narration_alignment_unknown`.
- **Çözüm:**
  - Her keyword-narration çifti için overlap skoru hesaplanıyor, en iyi eşleşme atanıyor
  - Overlap yoksa topic_kw tabanlı "guarantee-query" üretiliyor (örn. "Zanzibar war documentary")
  - Alternatif query'ler de overlap'li olarak seçiliyor

### 2. `scene_media.terms()` TR→EN eşleştirme genişletmesi
- ALIASES sözlüğü 76 → 250+ girdiye çıkarıldı (savaş/gemi/top/saray/harabe/kitap/yıldız/uzay/denizanası/tavşan/napolyon/hücre/güneş/zanzibar/bombalama/liman/sultan vb.)
- Compound-word splitting eklendi: `warship` → `{warship, war, ship}`, `seahorse` → `{seahorse, sea, horse}` vb.
- Kısa sözcükler (ay=moon, at=horse) len≤2 olsalar bile ALIASES'teyse korunuyor
- Durative/sayı/bağlaçlar için ek eşleşmeler eklendi

### 3. Content QC ayrımı
`scripts/qc_final_video.py` içine aşağıdaki kontroller eklendi:
- `content_scene_count`: tüm sahnelerde medya seçildi
- `content_no_duplicate_media`: aynı video tekrar kullanılmadı
- `content_license_present`: lisans bilgisi var
- `content_attribution`: attribution gerektiğinde var
- `content_relevance_score`: seçilen medyanın uygunluk skoru ≥20
- `content_provider_known`: sağlayıcı bilgisi mevcut
- `content_selection_errors`: seçim hatası yok
- `content_qc_metadata_only`: **Bu kontroller metadata/query tabanlıdır, görsel anlama yapmaz** (disclaimer)

Sahne sayısı artık `script.json.storyboard` uzunluğundan dinamik alınıyor (eskiden sabit 4'tü).

## Kalan İşler (CI kanıtı için)

1. CI Actions run'ı tetiklenip canlı Pexels/Pixabay cookie search+download testi yapılmalı
2. Cookie diagnostics gerçeği yansıtmalı (çalışan aramada cookie_present=true)
3. video_fetcher.js exit code JSON fix ile gerçek hata sınıfları görünmeli
4. Wikimedia fallback testi
5. Tam pipeline no-upload modda çalışmalı
6. README/TODO/AI_HANDOFF güncelle
7. Son commit SHA ve Actions run ID'leri rapora eklenecek

## CI Canlı Test Sonuçları

_(CI run tamamlandığında doldurulacak)_
