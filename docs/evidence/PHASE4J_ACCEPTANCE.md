# Faz 4J Kabul Raporu — Cookie-first Medya Entegrasyonu, Sahne Uyumu, Üretim Kalitesi

**Tarih:** 2026-11-19 (revize)
**Kapsam:** Sahne medyası entegrasyonu (cookie-first), sahne-narration uyumu, içerik QC
**Commit:** fbca2e3 + devam (bu rapordaki düzeltmeler)

## Özet

Tüm yerel testler geçti:
- ✅ **Python unit testleri: 383 passed, 0 failed**
- ✅ **Node.js testleri: 4/4 dosya, 17/17 test geçti**
- ✅ **126/126 fallback senaryosu** `scene_plan()`'dan query-narration overlap çakışmasız geçiyor (1 senaryo kelime sayısı aralığı dışı, beklenen)
- ✅ **Schema validation** `script.json` şemaya uygun (schema_version: "2.0" string)
- ✅ **Content QC** eklendi (tekrar medya, lisans, attribution, relevance, metadata-only disclaimarı)
- ✅ **video_fetcher.js** syntax kontrolü geçti
- ✅ **ALIASES TR→EN sözlüğü** 76→1092 benzersiz girdiye genişletildi (vücut/hayvan/bilim/tarih/coğrafya/renk/sayı vb.)

## Kabul Kriterleri Durumu

| # | Kriter | Durum | Kanıt |
|---|--------|-------|-------|
| 1 | Cookie-first strateji | ✅ Kodla korundu | video_fetcher.js, media_providers.py (mevcut) |
| 2 | Mevcut sistemleri koru | ✅ Tüm 383 test geçti | pytest çıktısı |
| 3 | Sahne medyası entegrasyonu | ✅ Kod hazır; canlı CI kanıtı gerekiyor | scene_media.py, media_processor.py |
| 4 | Sahne-uyum (query↔narration↔metadata) | ✅ terms() ALIASES + compound splitting + greedy keyword ataması + overlap garanti | 126/126 senaryo |
| 5 | Medya seçimi puanlama | ✅ Scoring korundu; kabul/red sebepleri manifest'te | scene_media.py evaluate() |
| 6 | Cookie diagnostics | ⏳ CI canlı run gerekiyor | video_fetcher.js exit code JSON fix |
| 7 | Fallback zinciri (hata gizleme yok) | ✅ Kodla korundu | — |
| 8 | Gerçek pipeline test | ⏳ CI no-upload run gerekiyor | — |
| 9 | Teknik + İçerik QC | ✅ İçerik QC eklendi (7 kontrol + disclaimer) | scripts/qc_final_video.py |
| 10 | Test/güvenlik | ✅ Secret leak testleri kodda; canlı CI kanıtı gerekiyor | test_phase4d_cookie_isolation |
| 11 | Kanıt | ✅ Tüm yerel kanıtlar bu raporda | — |
| 12 | Dokümantasyon | ✅ Bu rapor | docs/evidence/PHASE4J_ACCEPTANCE.md |

## Yapılan Düzeltmeler

### 1. `_synthesize_storyboard()` keyword ataması (content_engine.py)
- **Round-robin yerine öncelikli greedy atama**: zor eşleşen sahnelere (birkaç keyword overlap'i olan) öncelik veriliyor; bu sayede kolay sahneler tüm uygun keyword'leri alıp zor sahnelere 0-overlap bırakmıyor
- **Rebalancing pass**: atama sonrası 0 overlap kalan sahne varsa, donor bir sahneden keyword çalıp swap yapıyor (donor'da halen ≥1 overlap kalıyorsa)
- **Guarantee-query**: primary query overlap=0 ise topic_kw+EN-word'den üretim; İngilizce kelime yoksa generic concept kullanılıyor
- **Keyword padding**: senaryo 4'ten az keyword verirse default keyword'ler (cinematic history, nature documentary, vb.) ile dolduruluyor
- **Topic_kw çıkarımı**: ASCII-folded Turkish lookup, birden fazla kelime için parçalama
- **Alternatif query'ler**: kalan keyword'ler + topic_alt ekleniyor

### 2. `scene_media.terms()` TR→EN eşleştirme (src/media_processing/scene_media.py)
- **ALIASES sözlüğü 76→1092 benzersiz girdi**: vücut parçaları, hayvanlar, bitki, bilim, doğa, tarih, coğrafya, sayılar, zaman, renk, meslek, bina, silah, uzay, gemicilik, yaygın fiiller/sıfatlar
- **Compound-word splitting**: warship→{warship,war,ship}, seahorse→{seahorse,sea,horse} vb.
- **Kısa kök koruması**: len≤2 olsa bile ALIASES'te varsa (ay→moon, at→horse) korunuyor
- **STOP words düzeltmesi**: "science", "nature", "space", "history", "city", "planet" gibi topic kelimeleri STOP listesinden çıkarıldı (bunlar overlap için gerekli)
- **Duplicate key temizleme**: 266 duplicate key temizlendi (son değer kazanıyor, conflict'lerde görsel anlam tercih ediliyor: "ay"→moon)
- **scene_plan overlap kontrolü**: sadece primary query değil, primary+alternatiflerinden en az birinin overlap'i olmalı

### 3. Content QC (scripts/qc_final_video.py)
Eklenen kontroller:
- `content_scene_count`: tüm sahnelerde medya seçildi
- `content_no_duplicate_media`: aynı video tekrar kullanılmadı
- `content_license_present`: lisans bilgisi var
- `content_attribution`: attribution gerektiğinde var
- `content_relevance_score`: seçilen medyanın uygunluk skoru ≥20
- `content_provider_known`: sağlayıcı bilgisi mevcut
- `content_selection_errors`: seçim hatası yok
- `content_qc_metadata_only`: **Bu kontroller metadata/query tabanlıdır, görsel anlama yapmaz** (disclaimer)
- Sahne sayısı artık `script.json.storyboard` uzunluğundan dinamik alınıyor (eskiden sabit 4'tü)

## Test Sonuçları

### Python Testleri
```
383 passed, 1 warning, 16 subtests passed in 18.91s
```
Tüm test modülleri:
- Faz1-Faz12 testleri
- Phase4 medya/tüketici/tanılama testleri
- Content engine, şema, topic history, kapak, TTS testleri
- Cookie isolation, thumbnail, repeat koruma testleri

### Node.js Testleri
```
phase4c_catalog.test.cjs:     pass=5 fail=0
stock_media_catalog.test.cjs: pass=5 fail=0
uploader_metadata_probe.test.cjs: pass=6 fail=0
pruner_logic.test.js:          pass=1 fail=0
```

### Fallback Senaryo Testi
```
ok=126 bad=0 skipped(word count)=1 total_fallback=127
```
126 geçerli senaryonun hepsinde scene_plan() overlap hatasız üretiliyor.

### Canlı End-to-End (force_fallback)
- `run_content_pipeline()` başarılı
- TTS (edge-tts) üretimi başarılı
- script.json schema validation: 0 hata
- scene_plan 4 sahne, toplam süre audio_duration_sec ile eşleşiyor
- Queries İngilizce ve anlamlı (örn. "suleymaniye mosque istanbul", "history cannon", "historic chandelier mosque")

## Kalan İşler (GitHub Actions CI)

GitHub remote ve push erişimi bu ortamda yapılandırılmadığı için CI Actions tetiklenemedi. CI'da doğrulanması gerekenler:

1. **Canlı Pexels/Pixabay cookie search + download** (PEXELS_COOK/PIXABAY_COOK secret'ları ile)
2. **Wikimedia fallback** testi
3. **Cookie diagnostics** gerçek çalışan aramada `cookie_present=true` görünmesi
4. **video_fetcher.js** exit code JSON sonrası gerçek hata sınıflarının doğru raporlanması
5. **Tam no-upload pipeline** (konu→senaryo→storyboard→medya→indir→ffprobe→decode→montaj→QC)
6. **Secret leak testi** (cookie'ler log/artifact/git/chat'e sızmıyor)

Bu CI koşuları tamamlandığında bu rapor güncellenmelidir.

## Yerel Kanıt Dosyaları
- `content_engine.py` — greedy keyword ataması, guarantee-query, topic_kw düzeltmesi
- `src/media_processing/scene_media.py` — ALIASES genişletmesi, terms() düzeltmeleri, overlap koşulu genişletmesi
- `scripts/qc_final_video.py` — içerik QC kontrolleri

## NOT_ACCEPTED Durumu
Kriter 1, 3, 6, 7, 8, 10'un canlı CI kanıtları bu ortamda (GitHub erişimi yok) üretilemedi. Bu nedenle Faz 4J **yerel olarak hazır ama canlı doğrulama bekliyor** durumundadır. Kod seviyesinde tüm korumalar ve düzeltmeler tamamdır; gerçek cookie ve ağ erişimi olan bir CI ortamında Faz4G no-upload workflow'u (`phase4g_e2e_no_upload.yml`) çalıştırılarak kabul kriterlerinin kalan bölümü doğrulanmalıdır.
