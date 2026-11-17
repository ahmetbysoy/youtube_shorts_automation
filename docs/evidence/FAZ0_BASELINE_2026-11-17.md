# Faz 0 — Başlangıç Envanteri ve Baseline Kanıtı

**Tarih:** 2026-11-17  
**İnceleme hedefi:** GitHub `main` branch  
**İncelenen HEAD:** `f8ec3aa0dc3e04f87fd6f0e5f3bc62acf3d69478`  
**Sonuç:** Faz 0 kısmen tamamlandı. Bu incelemede uygulama kodu ve workflow değiştirilmedi; yalnızca bu kanıt belgesi ve TODO/README kayıtları güncellendi.

## 1. Depo ve branch

- Depo: `ahmetbysoy/youtube_shorts_automation`
- Varsayılan branch: `main`
- HEAD: `f8ec3aa0dc3e04f87fd6f0e5f3bc62acf3d69478`
- Branch protection: GitHub API yanıtında `protected=false`.
- GitHub depo durumu: public, archived değil.
- Yerel çalışma ağacı durumu doğrulanamadı: bu çalışma ortamından GitHub'a `git clone` DNS çözümlemesi başarısız oldu. Bu nedenle yerel `git status` veya yerel test tekrarı yapılmadı.

## 2. Workflow envanteri

### `.github/workflows/daily_shorts.yml`

Bu workflow test workflow'u değildir; canlı yayın yapabilir.

- Schedule: `13 */2 * * *`.
- `workflow_dispatch` girdileri: `target_channel`, `slot_epoch`, `chain`, `force_local_thumbnail`, `skip_thumbnail`.
- Genel concurrency grubu chain değerine göre ayrılır ve `cancel-in-progress: true`.
- Yayın job'unda ayrıca `studio-upload-lock` concurrency kilidi vardır; `cancel-in-progress: false`.
- Kanal matrisi `max-parallel: 1`; bir kanalın akışı tamamlanmadan sonraki kanal başlamaz.
- Üretim kapısı `scripts/production_gate.sh` ile kontrol edilir.
- Ana komut `xvfb-run ... python main.py --channel_id ...`.
- Workflow içinde PUBLIC yayın, oturum çerezlerinin yenilenmesi, kanal hijyeni, artifact yükleme ve konu geçmişini repoya yazma adımları bulunur.
- `cron-kick` job'u ayrıca `hourly_pruner.yml`, `draft_publisher.yml` ve koşullara göre kendisini yeniden tetikleyebilir.

**Güvenlik kararı:** Bu workflow baseline/test amacıyla elle tetiklenmedi. Yanlışlıkla gerçek video yayınlayabilir ve başka otomasyonları tetikleyebilir.

### Test workflow'u: `.github/workflows/ubuntu_26_test.yml`

- Yalnız ortam/bağımlılık, JavaScript syntax, FFmpeg ve Python testlerini çalıştırır; YouTube kanal/yayın adımı yoktur.
- `permissions: contents: read`.
- `workflow_dispatch` mevcut; ancak bu oturumda GitHub connector yalnızca okuma ve dosya/commit işlemleri sağladığından manuel workflow dispatch yapılamadı.
- Mevcut başarılı koşu kullanılarak baseline alındı (aşağıda).

## 3. Orkestrasyon ve veri akışı bulguları

### `main.py`

Akış sırası:

1. `content_engine.py --force-fallback --channel_id <id>`
2. `src/media_processing/media_processor.py`
3. `scripts/embed_cover_frame.py`
4. `youtube_studio_uploader.js`

Kritik davranışlar:

- İçerik motoruna `--force-fallback` veriliyor; bu ana workflow'da normal LLM üretimini devre dışı bırakıyor.
- Kapak karesi gömme adımının dönüş değeri kontrol edilmeden devam ediliyor; bu adımın başarısızlığı yayını durdurmuyor.
- Uploader adımı başarılı olursa `logs/auth_status.json` ve video ID dosyasından durum raporlanıyor.
- Exit code 42 kota dolumu, 43 taslak bırakılması olarak planlı kabul ediliyor; diğer başarısızlıklar orkestrasyonu durduruyor.

### Medya ve yükleme

- `src/media_processing/media_processor.py` genel `visual_keywords` üzerinden medya arıyor; sahne storyboard sözleşmesi henüz ana veri kaynağı değil.
- `video_fetcher.js` Playwright ile Pixabay/Pexels araması yapıyor.
- Medya işlem hattında Pexels/Pixabay/Playwright başarısız olursa Wikimedia Commons fallback'i mevcut.
- `youtube_studio_uploader.js` yalnız Publish düğmesine basılmasını başarı saymıyor. Video ID'sini çıkarıyor, Studio'daki Shorts listesinde aynı ID'li satırı bulup PUBLIC ikonunu/etiketini kontrol ediyor. Doğrulama olmazsa `publish_unverified` yazar ve hata fırlatır; başarı halinde `upload_completed` yazar.

## 4. Son gerçek üretim koşusu

- Workflow run: [44119590041](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44119590041)
- Workflow: `daily_shorts.yml`
- Event: `schedule`
- Başlangıç: `2026-11-17T15:54:02Z`
- Sonuç: `success`
- Kanal: `1`
- Uploader logunda Studio PUBLIC doğrulaması: başarılı.
- Video ID: `mTomLSj8__k`
- Video: [İskender'in Feneri Geceleri 50 Kilometre Öteden Görülüyordu!](https://youtube.com/shorts/mTomLSj8__k)
- Görünürlük: `PUBLIC`.

### Bu koşudan çıkan riskler

1. Dört sahne aramasında Playwright/Pexels kaynaklarından video URL bulunamadığı loglandı; Wikimedia fallback devreye girdi. Bir arama terimi `ocean waves beacon` iken indirilen dosyanın adı `Chemical_Pollution_of_the_Ocean` olarak görünüyor. Bu tek başına klibin kesinlikle yanlış olduğunu kanıtlamaz; ancak sahne-görsel semantik eşleşmesi için ayrıca denetlenmesi gerektiğini gösterir.
2. Cookie/Storage State güncelleme adımı `REPO_PAT` ile GitHub Secrets public-key isteğinde HTTP 401 `Bad credentials` aldı. Adım `continue-on-error: true` olduğu için workflow yeşil kaldı; oturum secret'larının güncellendiği doğrulanmadı.
3. Workflow'un genel sonucu `success` olması, her alt sistemin kusursuz olduğu anlamına gelmiyor. Özellikle medya uygunluğu ve secret yenileme sonuçları ayrı kalite sinyalleri olmalı.

## 5. Test baseline kanıtı

- Workflow run: [44076814790](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44076814790)
- Workflow: `ubuntu_26_test.yml`
- Event: `schedule`
- Başlangıç: `2026-11-17T11:45:06Z`
- Sonuç: `success`
- Job: `ubuntu-26-probe`, başarılı.
- Logda `python -m pytest -q tests`: **108 passed, 8 subtests passed** (14.88 saniye).
- Ayrıca `node --check youtube_studio_uploader.js`, bağımlılık kurulumu, Playwright/Chromium açılış kurulumu ve 1080x1920/30 FPS H.264 FFmpeg probe adımları başarılı.

Test run'ın HEAD'i `aaa89b1bf4777c61077ac18e44406d3d0bcede69`; güncel HEAD'e göre 17 commit geride. GitHub compare sonucunda `main.py`, `content_engine.py`, `media_processor.py`, `video_fetcher.js`, `youtube_studio_uploader.js`, test dosyaları, requirements ve `ubuntu_26_test.yml` bu 17 committe değişmemiş. Değişen dosyalar arasında dokümantasyon, çalışma verileri ve thumbnail yardımcı scriptleri var. Dolayısıyla 108 test sonucu mevcut ana pipeline/test dosyaları için güçlü bir baseline kanıtıdır; ancak değişen thumbnail yardımcı scriptleri için güncel HEAD üzerinde ayrıca test gerekebilir.

### Test kapsamındaki açık eksikler

- `package.json` içindeki `npm test` komutu hâlâ `Error: no test specified` döndüren placeholder.
- `tests/pruner_logic.test.js` dosyası mevcut; `ubuntu_26_test.yml` içinde bu Node testinin çalıştırıldığına dair adım yok.
- Test workflow'u uploader için `node --check` yapıyor; tüm JavaScript dosyaları için syntax/test kapsamı olduğu varsayılmamalı.
- Yerel test tekrarı yapılamadı: çalışma konteynerinden GitHub'a clone girişimi DNS çözümleme hatasıyla başarısız oldu. 108 test sonucu doğrudan GitHub Actions logundan alındı.

## 6. Dokümantasyon tutarsızlıkları

- `docs/ARCHITECTURE.md` son güncelleme tarihi 2026-11-03 ve eski paralel 3 job/matrix tasvirini içeriyor; güncel `daily_shorts.yml` ise `max-parallel: 1` kullanıyor.
- `ARCHITECTURE.md` `AI_HANDOFF.md` dosyasına yönlendiriyor; dosyanın varlığı bu incelemede henüz doğrulanmadı.
- `docs/setup/INSTALLATION_REPORT.md` içindeki 7/7 test sonucu eski bir kurulum raporuna ait; güncel Actions test sonucu 108 testtir.
- Bu belgeler bu aşamada yeniden yazılmadı; Faz 0'ın kalan dokümantasyon temizliği kapsamında ele alınmalı.

## 7. Faz 0 kalan işler

- [ ] `AI_HANDOFF.md` dosyasının varlığını ve güncelliğini doğrula.
- [ ] `hourly_pruner.yml`, `draft_publisher.yml` ve ilgili cron/watchdog akışlarının kapsamını ayrı ayrı incele.
- [ ] GitHub Secrets değerlerini okumadan, yalnız gerekli secret adlarının varlığını güvenli şekilde kontrol edebilecek yöntem belirle. Bu oturumda secrets API erişimi kullanılmadı.
- [ ] Node testlerini ve `npm test` komutunu gerçek bir test komutuna dönüştürme ihtiyacını Faz 1'e aktar.
- [ ] Değişen thumbnail yardımcı scriptleri için güncel HEAD üzerinde test ekle/çalıştır.
- [ ] ARCHITECTURE ve kurulum raporundaki eski bilgiler için güncelleme listesi çıkar.
- [ ] Faz 0'ın kalan maddelerini tamamla ve kabul kapısını yeniden değerlendir.

## 8. Değişiklik ve yayın güvenliği

Bu inceleme sırasında `main.py`, `content_engine.py`, medya motoru, uploader veya workflow değiştirilmedi. Üretim workflow'u tetiklenmedi. Hiçbir YouTube videosu bu Faz 0 çalışması nedeniyle yüklenmedi. Bu dosya yalnızca GitHub'dan okunan kod ve Actions kayıtlarının kanıt özetidir.


## 9. Bağlantılı otomasyonlar ve devir teslim belgesi

### `.github/workflows/hourly_pruner.yml`

- Schedule: `7 * * * *` ve `37 * * * *`.
- Kanal/Studio oturumu için ayrı bir workflow concurrency grubu var; içeride `youtube-studio-browser-session` kilidi kullanılıyor.
- `prune_low_performers.js` çalıştırılıyor.
- Varsayılan eşikler: en az 60 dakika yaş, 100'den az görüntülenme; çalışma başına en fazla 25 silme ve en az 1 videoyu koruma.
- `PRUNE_DRY_RUN` varsayılanı `false`; yani ayar ayrıca değiştirilmediyse bu akış gerçek silme yapabilecek şekilde tasarlanmış.
- Bu workflow ayrıca günlük Shorts akışı gecikirse `daily_shorts.yml`'i yeniden tetikleyebilir.

### `.github/workflows/draft_publisher.yml`

- Schedule: her 20 dakikada bir.
- Varsayılan `max_per_run=2`, `dry_run=0`.
- Studio'da taslakları seçip küçük resim/metadata ayarladıktan sonra PUBLIC yayınlamayı hedefliyor.
- Kendi concurrency grubu `draft-publisher-lock`; günlük yükleyicinin `studio-upload-lock` grubu ile aynı değil. Aynı Studio oturumuna eşzamanlı erişim ihtimali operasyonel risk olarak not edildi.
- Oturum secret'ı güncellemesi `REPO_PAT` ile yapılır ve `continue-on-error` kullanır; 401 gibi hatalar workflow genelini yeşil bırakabilir.

**Sonuç:** Pruner ve taslak yayınlayıcı yalnızca yardımcı test işleri değildir; gerçek videoları silebilir veya taslakları PUBLIC yapabilir. Faz 0/sonraki testlerde bu workflow'lar elle tetiklenmemelidir.

### `AI_HANDOFF.md`

- Dosya mevcuttur; 359 satır.
- Üst kısımda 2026-11-03 tarihli eski bir güncelleme satırı ve 2026-11-05 tarihli operasyon notları birlikte bulunuyor.
- İçerikte eski test sayısı (22/22), eski cron/matrix ve secret envanteri iddiaları bulunuyor. Bunlar güncel GitHub API/Actions kanıtı olarak kabul edilmemeli.
- Yeni Gemini planı ve Faz 0 baseline raporu, güncel geliştirme başlangıç noktası olarak kullanılmalı. AI_HANDOFF içindeki tarihsel operasyon notları silinmeden, sonraki dokümantasyon fazında güncel durumla uzlaştırılmalı.


## 10. 2026-11-17 devam çalışması — doküman ve thumbnail testleri

### Dokümantasyon uzlaştırması

- `docs/ARCHITECTURE.md` başına güncel doğrulanmış akış eklendi: `daily_shorts.yml` → production gate → sıralı kanal job'u → `main.py --force-fallback` → medya → best-effort kapak gömme → Studio PUBLIC doğrulaması. Eski 3'lü paralel matris diyagramı tarihsel olarak etiketlendi.
- `docs/setup/INSTALLATION_REPORT.md` içindeki 7/7 yerel test sonucu tarihsel ortam raporu olarak etiketlendi; güncel CI baseline bağlantısı eklendi.
- `AI_HANDOFF.md` başına 2026-11-17 doğrulanmış durum notu eklendi. Eski 22/22 ve 3'lü matris iddialarının güncel durum olmadığı açıklandı; tarihsel notlar silinmedi.
- İlgili doküman commitleri: `fc7ea77698eeced6c7159205d71fba755ac707ac`, `8ca1fb9d24accaf9aa864f851d2e0d46aae17e4b`, `b693e809de70cf48ce8bc0e43ab0ef0a3465c710`.

### Thumbnail yardımcı testleri

- Yeni offline test dosyası: `tests/test_thumbnail_helpers.py`.
- Kapsam: fallback kapak üretiminin JPEG/1080×1920 çıktısı, crop boyutu, kontrast kare seçimi ve bozuk dosya toleransı, Studio kare eşleşme aracı, Gemini kare seçicinin kapalı/çok fazla kare durumunda ağ çağrısı yapmadan güvenli fallback vermesi.
- Testler Gemini, Pollinations veya YouTube Studio'ya istek göndermez; fake API key ile ağ çağrısı yapılmaz.
- Test dosyası commit'i: `25b7ac86bd7bb0efeb7a0c31ee112c6ebe345865`.
- Güncel test workflow'u otomatik tetiklendi: [run 44160916391](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44160916391). Bu rapor güncellenirken koşu henüz tamamlanmamıştı; sonuç ve test sayısı tamamlanınca eklenmelidir.

### Secret metadata kontrolü

- GitHub connector açıklaması, Secrets API uçlarının hassas endpoint ailesi olarak desteklenmediğini açıkça belirtiyor. Bu nedenle secret adlarının varlığı bu oturumdaki bağlantıyla doğrulanamadı.
- Secret değerlerini alma veya loglama girişimi yapılmadı. Secret kontrolü Faz 0 kabul kapısında açık kalıyor.
- Alternatif olarak kullanıcının GitHub arayüzünde Settings → Secrets and variables → Actions bölümünden yalnız adları kontrol etmesi veya uygun salt-metadata izinli bağlantı sağlaması gerekir; değerler açılmamalıdır.

### Güncel doküman durumu

- TODO güncelleme commit'i: `a348b1fdd5caded8063b0f4da17e1c0ca9787959`.
- Faz 0 henüz kapatılmadı. CI kanıtı ve secret metadata kısıtı çözülmeden Faz 1'e geçiş yapılmamalıdır.
