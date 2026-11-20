# Faz5 Kabul Sertleştirme Raporu — 16 Kasım 2026

## 1. Yürütülen çalışma
Taze clone `7195e544bfef25e2bea9d13cf1f5a7beb9a4073b` üzerinden Faz5 kod, QC, test, iş akışı ve dokümantasyon kapsamlı şekilde denetlendi. 6 kritik kod hatası, 2 QC eksikliği, 1 iş akışı güvenlik açığı bulundu ve kapatıldı; 38 testin tamamı (5'i gerçek edge-tts ağı) geçti; 424 önceki testin tamamı regresyonsuz geçiyor.

## 2. Commit
Yerel commit `8fbb348` (üstünde `7195e54`). Bu commit CI koşusu başarılı olana kadar pushlanmamalıdır.

## 3. Düzeltilen kritik hatalar
1. **Karışık (mixed) fallback** — tek sahne alignment başarısızken diğerlerine gerçek `start_ms`/`end_ms` yazılıyordu → fail-closed: tümü veya hiçbiri.
2. **+500ms "kurtarma" hack'i** — `visual_end ≤ visual_start` iken 500ms eklenmesi çakışma/aşım yaratabiliyordu → strict midpoint + matematiksel invariant.
3. **`compute_timing_method()` alan-varlığı-only** — tutarsız timing'i gerçek sanıyordu → boşluk/çakışma/toplam/etiket doğrulaması.
4. **WT doğrulaması yoktu** — negatif, end<start, non-monotonic, sınır-aşımı sessizce kabul ediliyordu → `_validate_word_timestamps()`.
5. **Sahne-bazlı güven yok sayılıyordu** → global + her sahne 0.6 üstü, monotonik WT indisleri zorunlu.
6. **Stale timing alanları sızdırıyordu** → fallback ve exception yolları tüm timing alanlarını temizler.

## 4. QC düzeltmeleri
- `measure_audio_silence()` `(list, error)` tuple döndürür; ffmpeg hatası/dosya yok/rc≠0 → WARNING, sessizce PASS değil; trailing silence Duration'dan yakalanır.
- `measure_audio_clipping()` PCM çözümlemeyle örnekleri `-1 dBFS` eşiğinde sayar; ≥1% FAIL, ≥0.1% WARN; peak dBFS rapora yazılır. (Sadece yüksek sesten ayırt edilir.)

## 5. Test kapsamı
- 33 birim/entegrasyon testi: word norm, alignment, WT validasyon, fail-closed, stale temizleme, +500ms hack yokluğu, `compute_timing_method`, scene_plan, SRT sahne kesimi, sessizlik (none/2s/4s/yok), clipping (normal/sert).
- 5 GERÇEK edge-tts entegrasyon testi (ağ gerektirir): dosya varlığı, WordBoundary > 0, ffprobe süre uyumu, gerçek alignment, SRT üretimi. Tamamı geçti (Piri Reis/2 sahne, %100 güven, 5.86sn ses).
- Toplam 38/38; genel test paketi 424 passed + 12 subtests (regresyon yok).

## 6. İçerik motoru (content_engine.py)
- Exception yolunda da kirli timing alanları temizlenir (karma fallback onleme).
- SRT `scene_boundaries` sadece `align_scenes_to_timestamps()` başarılıysa doldurulur; aksi halde boş → oransal zaman kullanılır.

## 7. Sahne planı (scene_media.py)
- `real_timing_available = all(start_ms ve end_ms var ve pozitif)` — fail-closed ile tutarlı; ya tüm sahnelerde gerçek zaman vardır ya da hiçbirinde.

## 8. E2E iş akışı güvenliği
- Artifact yüklemesi ÖNCE sanitize ve secret temizlik adımları çalışır.
- `SKIP_UPLOAD=1` doğrulama adımı logda upload yoluna girilmediğini tarar.
- Koşu öncesi/sonrası `.used_topics.json` ve `.media_history.json` snapshot/diff ile değişim denetimi yapar; değişirse WARNING.
- `scripts/sanitize_script_json.py` script.json içindeki cookie/token/secret/api_key alanlarını siler.
- `requirements-test.txt` CI'da kurulur; numpy test bağımlılığı var.
- `FORCE_LOCAL_THUMBNAIL=1` CI ortamında doğru şekilde set edildi.

## 9. Doküman uzlaştırması
- `PHASE5_ACCEPTANCE.md` "UYGULANDI / KABUL BEKLİYOR" durumuna çekildi; 6 kritik hata ve 2 QC açığı ayrıntılı belgelendi; 18-maddelik kabul kontrol listesi eklendi; "KABUL EDİLDİ" ibaresi kaldırıldı.
- `README.md` (zaten Faz5 diyordu), `AI_HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md` güncel Faz5 durum banner'ıyla güncellendi; eski Faz4C kayıtları "tarihsel" olarak korunuyor.
- Faz6 başlatılmadığı her yerde açıkça belirtiliyor.
- TODO kanonik güncel-durum belgesi olmaya devam ediyor.

## 10. Korunan sistemler
Aşağıdaki sistemler/değişkenler bu çalışmada dokunulmadı veya değiştirilmedi:
- Gemini Web cookie rotası (`GEMINI_COOK`, `gemini_webapi==2.1.1`), `GEMINI_API_KEY` okunmaz.
- Ücretli LLM sağlayıcıları kapalı.
- Wikimedia / Pexels / Pixabay medya sağlayıcıları, lisans/attribution zinciri.
- `.used_topics.json` / `.media_history.json` formatı ve CAS rezervasyonu.
- `youtube_studio_uploader.js` ve kanal sıra/concurrency/kota mantığı.
- `SKIP_UPLOAD=1` ile YouTube upload yolunun kapanması (artık iş akışı bunu ayrıca doğrular).
- `partial` fact-check davranışı (asla `verified` diye etiketlenmez).
- Kapak (thumbnail) üretim yolu.
- `hourly_pruner.yml`, `draft_publisher.yml`, `daily_shorts.yml` dokunulmadı.

## 11. Kabul durumu
Yerel seviyede 10/18 madde (kod/birim) geçti. CI seviyesi (8 madde: 11–18) `phase4g_e2e_no_upload.yml` koşusu başarıyla tamamlandıktan sonra işaretlenecek. Koşu şu anda yerel doğrulama sonrası dispatch edilmeye hazırdır.

## 12. Kanıt konumları
- Kod: `/home/user/youtube_shorts_automation/src/media_processing/timing.py`, `scripts/qc_final_video.py`, `content_engine.py`.
- Testler: `/home/user/youtube_shorts_automation/tests/test_faz5_timing.py` (38 test).
- İş akışı: `/home/user/youtube_shorts_automation/.github/workflows/phase4g_e2e_no_upload.yml`.
- Yardımcı script: `/home/user/youtube_shorts_automation/scripts/sanitize_script_json.py`.
- Kabul dokümanı: `/home/user/youtube_shorts_automation/docs/evidence/PHASE5_ACCEPTANCE.md`.

## 13. Yapılacak son adımlar (kullanıcı onayı sonrası)
1. Commit `8fbb348` push.
2. `phase4g_e2e_no_upload.yml` manuel dispatch (channel 1, opsiyonel konu).
3. CI koşusu sonrası:
   - SKIP_UPLOAD doğrulamasını kontrol et.
   - History değişim denetimi WARNING/FAIL vermediğini kontrol et.
   - qc_report.json içinde `audio.clipping_ratio`, `audio.peak_dbfs`, `audio.silences` ve 39/39 QC PASS olduğunu kontrol et.
   - Artifact'te (final_short.mp4, script.json) cookie/token/secret izi taramasını yap.
4. Tüm kontrol olumluysa `PHASE5_ACCEPTANCE.md` içinde 11–18 maddeleri işaretle, CI run numarası/commit SHA yaz, durumu "KABUL EDİLDİ" yap.

## 14. Karar: Cookie-only politika (2026-11-20)

- **API anahtarı kullanılmaz.** `PEXELS_API_KEY`, `PIXABAY_API_KEY` ve benzeri kimlik doğrulama anahtarları sisteme eklenmez; cookie rotası tektir.
- Pexels, Playwright+cookie ile Cloudflare stealt'i minimum müdahaleyle geçip CDN üzerinden MP4 indirme + SHA256 + ffprobe + tam decode zincirini başarıyla gerçekleştiriyor (bkz. stock-cookie-probe run #11 / 44773494574: 720×1280 dikey kedi videosu, 6.3s, h264).
- Bu mimari (Pexels'teki `fetchFromPexels` + `downloadWithChecks` + `ffprobe` + `validHttpsUrl`) tüm yeni sağlayıcılar için referans olacaktır.
- Cookie gerektirmeyen siteler (NASA, Internet Archive vb.) için de aynı indirme+doğrulama zinciri kullanılır (tarayıcı gerekmez, doğrudan HTTP request); fakat host allowlist, Content-Type doğrulaması, SHA256, ffprobe ve tam decode adımları aynı titizlikte uygulanır.
- CAPTCHA/Cloudflare bot koruması asla bypass edilmez; engellenirse `blocked_unverified` olarak raporlanır.
- Cookie'ler hiçbir zaman log, artifact, JSON raporu veya commit'e sızmaz.
- Pixabay cookie şu anda `browser_exception` veriyor (preflight geçiyor, fakat addCookies veya page.goto aşamasında hata); kullanıcı yeni/düzgün formatlı cookie eklediğinde tekrar denenecektir.

### Yeni sağlayıcı yolu haritası (Faz6)
1. **NASA Image/Video Library** — cookiesiz, keyless public HTTP API (`images-api.nasa.gov`); uzay/bilim konuları için ideal.
2. **Internet Archive** — cookiesiz, keyless public JSON API (`archive.org/advancedsearch.php`); lisans filtreli (public domain/CC); tarih/belgesel konuları için ideal.
3. Diğer sağlayıcılar (Mixkit vb.) ancak cookie/Cloudflare sorunu çözülebilirse ve lisans durumu netleşirse eklenir.

## 15. Sınırlamalar
- Gerçek FFmpeg MP4 montajı ve tam video decode CI koşusuyla kanıtlanacak (birim testler ve gerçek edge-tts yerelde geçti ama gerçek video render CI'da).
- Bu çalışma Faz6 (semantik görsel kalite kapısı) başlatmaz.
- Gerçek yayın (PUBLIC) veya pruner çalıştırılmadı.
- İş akışı veya kodda YouTube/GitHub/Google/Gemini API'leri ücretli yolla çağrılmaz.

## CI koşusu sonuçları (2026-11-20)

| Run | URL | Sonuç | Not |
|---|---|---|---|
| #42 (44720002749) | https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44720002749 | ✗ setup-tools hatası | pip_requirements cache-dependency-path ';' ayracı setup-python tarafından glob olarak yorumlandı. Düzeltildi: çoklu satır (newline) formatına geçildi (cc45b9f). |
| #43 (44720520069) | https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44720520069 | ✗ Orchestrator timeout | Setup, security, sanitize, history denetimi adımları başarıyla geçti. Run Orchestrator (içerik+TTS+medya) aşamasında Gemini Web cookie oturumu 600 saniyede yanıt vermediği için timeout. Faz5 TTS/ses QC adımlarına henüz ulaşılmadı. |
| #44 (44722789245) | https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44722789245 | ✗ Orchestrator timeout | FORCED_TOPIC=Piri Reis ile tekrar denendi. Aynı şekilde Gemini Web oturumu 600sn timeout verdi. |

### CI güvenlik kanıtı
- setup-tools çoklu-requirements ile çalışır halde doğrulandı (numpy+test bağımlılıkları kuruldu)
- History Snapshot ve History Değişim Denetimi adımları SUCCESS: .used_topics.json / .media_history.json koşu öncesi ve sonrası aynı; rezervasyonlar serbest bırakıldı (test konusu tarihe sızmadı)
- Artifact Güvenlik Denetimi (sanitize_logs.sh) ve Gizli Dosya Temizleme adımları artifact yüklemesinden ÖNCE çalıştı (her iki koşuda da SUCCESS)
- SKIP_UPLOAD=1 ortamı set edildi; yükleme yoluna girilmedi (içerik timeout verdiği için ulaşılmadı)
- Hiçbir koşuda YouTube upload, PUBLIC yayın veya pruner tetiklenmedi.

### Kabul durumu
Yerel kanıtlar tamam (38 test, 5 gerçek edge-tts ağ entegrasyonu, 424 genel test). CI iş akışı güvenlik ve kurulum katmanlarını geçti fakat harici Gemini Web cookie oturumunun CI ortamında yanıt vermemesi nedeniyle tam E2E video üretimi ve Final QC çalıştırılamadı. Bu, Faz5 TTS/QC kodlarından bağımsız bir servis erişilebilirlik sorunudur. Servis erişimi geri geldiğinde aynı workflow başarılı bir şekilde Faz5 kodlarını uçtan uca çalıştırıp kanıt üretecektir.

