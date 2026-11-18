# Faz 4 — Sahne bazlı medya motoru: kod, CI ve canlı kanıt

> **Tarihsel kapsam:** Aşağıdaki §1–7 e4d1144 Faz4 snapshot’ıdır; o tarihteki başarısız/kısmi sonuçlar korunur. Faz4B güncellemesi §8 ve [ayrı rapordadır](PHASE4B_ACCEPTANCE_2026-11-18.md); eski JSON değiştirilmedi.

**Tarih:** 2026-11-18 · **Karar: FAZ 4 TAM KABULÜ GEÇMEDİ — kısmi canlı sağlayıcı kanıtı.**

Kod uygulanıp main'e push edildi; yeni kod CI'da geçti ve Commons üzerinde gerçek iki-sahne dosya/consumer kanıtı alındı. Ancak Pexels/Pixabay'dan kabul edilmiş canlı asset yok. Yeşil workflow'u tüm sağlayıcıların veya sahne-anlatım görsel anlamının doğrulandığı şeklinde yorumlamıyoruz. **Otomatik PUBLIC yayına hazır olunduğu sonucu kesinlikle çıkarılmaz.** Faz 5 gerçek TTS zamanlaması ve bütünleşik yayın kalite kapısı ayrı/açık kalır.

Makine okunur ham sağlayıcı manifestleri, run/job/step kimlikleri, dosya hash'leri ve güvenlik denetimi: [JSON kayıt](PHASE4_ACTIONS_EVIDENCE_2026-11-18.json). Tasarım/sınırlar: [medya motoru](../PHASE4_MEDIA_ENGINE.md); değişiklik öncesi davranış: [baseline](../PHASE4_MEDIA_BASELINE.md); genişletilmiş tüketici taraması: [Faz 1 envanteri §7](../PHASE1_SCRIPT_JSON_INVENTORY.md#7-2026-11-18-faz-4--genişletilmiş-statik-üreticitüketici-taraması).

## 1. Kaynak commit'leri ve aynı-kod koşuları

| Kod | Amaç / sonuç |
|---|---|
| [`eb99109`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/eb9910914dfff018e202d9ce467dbe15ce2e0c5a) | Ortak provider/license sözleşmesi, strict sahne selector, IO, ayrı medya history, schema/validator, testler ve güvenli canlı probe |
| [`c2ad1c9`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/c2ad1c98a941907db199e41f8c1c9c283bb09c98) | İlk Actions'ta yakalanan FFmpeg 8 full-range JPEG hatası: yalnız strict yolda limited range + 30 FPS CFR. Sert yuv420p QC gevşetilmedi. Güvenli provider HTTP/katalog teşhisi |
| [`c29f7e7`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/c29f7e7c888681bedf2a2a9f384ba3e30350075f) | Değiştirilmemiş uploader'ın CTA/hashtag eklemesi ve UTF-16 kesmesi için zorunlu atıf bütçesi + gerçek saf JS tüketici fonksiyon testleri. Önceki credit-budget revizyonu |
| [`e4d1144`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/e4d1144116887b31c459bb6a7e171589d214c687) | Çelişkili/sürümsüz/restricted CC BY beyanları, sürüm/jurisdiction uyuşmazlığı ve credential/standart dışı portlu lisans URL'leri izin varsayılarak uzlaştırılmaz; 6 ek regresyon. **Son doğrulanan uygulama kodu** |

Son iki koşunun `head_sha` değeri birebir **`e4d1144116887b31c459bb6a7e171589d214c687`**:

- Ubuntu 26 CI **[44288761602](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761602): success**.
- Ayrı, manuel ve **yayınsız** live source probe **[44288761461](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761461): success**, fakat kendi sonucu **`partial_provider_evidence`**, `all_requested_providers_verified=false`.
- Artifact: **`phase4-media-evidence-44288761461`**, ID **14420900886**, arşiv 858416 byte. Runtime retention 14 gün; önemli JSON içeriği bu repodaki kanıt kaydına alındı. Ham stock dosyaları artifact'e konmadı.
- Bu raporu ekleyen sonraki commit yalnız dokümandır; çalıştırılmamış bir kaynak SHA için CI/live başarısı iddia edilmez.

### Tarihsel denemeler — saklandı, final kanıtla karıştırılmadı

| Kaynak | CI | Canlı probe | Yorum |
|---|---|---|---|
| `eb99109` | [44284971550](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44284971550) success, 218 + 16 / 47 hedefli | [44285033824](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44285033824) **failure** | Commons source/download geçti; consumer `yuvj420p` nedeniyle doğru biçimde reddedildi. [İlk hata raporu](PHASE4_FIRST_ACTIONS_ATTEMPT_2026-11-18.md) |
| `c2ad1c9` | [44285743243](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44285743243) success, 222 + 16 / 51 hedefli | [44285746809](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44285746809) success, **partial** | Teknik render düzeldi; stock hâlâ blocked. Sonraki atıf bütçesi düzeltmesi için kanıt yerine kullanılmadı |
| `c29f7e7` | [44286729473](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44286729473) success, 227 + 16 / 56 hedefli | [44286729732](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44286729732) success, **partial** | Atıf bütçesi düzeltmesi geçti; son Commons lisans-tutarlılık kapısı için ayrı kaynak CI/live alındı |

İlk yerel Commons denemesi daha eski selection politikasıyla `Apollo_11_Plaque.webm` karşılaştırma/arşiv klibini seçmişti. İnceleme bunu istenmeyen örnek olarak ortaya çıkardı; comparison/slideshow bloklama, iki subject-anchor ve gerçek thumbnail-host düzeltmeleri eklendi. Bu eski yerel deneme **son kaynak kodunun canlı kabul kanıtı değildir**.

## 2. Uygulama ve değişen dosyalar

| Dosya grubu | Değişiklik |
|---|---|
| `src/media_processing/media_providers.py` | Pexels/Pixabay API, metadata Playwright ve Commons ortak dondurulmuş candidate/license sözleşmesi; gerçek source identity, lisans evidence/hash, atıf ve sanitized URL'ler. Commons korundu |
| `media_io.py` | Allowlisted HTTPS/bounded redirects, 64 MiB sınır, partial cleanup, SHA-256; gerçek image decode veya ffprobe + tam video decode |
| `scene_media.py` | Her scene'in primary + sıralı bounded alternatives ve narration'ı ayrı; ilgisiz/eksik/bozuk/uygunsuz/lisanssız dosya ret; skor bileşenleri, sorgular/ret nedenleri, 1:1 manifest ve tam atıf. Arama sorgusu aday metadata'sına kanıt gibi eklenmez |
| `media_history.py`, `.gitignore` | Topic history'den ayrı `.media_history.json`: local lock/atomic replace; opsiyonel GitHub Contents SHA-CAS merge/retry. Son 200 kayıt, son 100'e recency penalty; distributed reservation değil |
| `media_processor.py` | Storyboard **anahtarı mevcutsa** strict route; bozuk/boş board legacy'ye düşmez. Başarısız sahne montajı durdurur. Strict dosyalar contain/pad, videolar loop edilmez. JPEG limited-range/CFR düzeltmesi yalnız strict yolu etkiler |
| `scripts/stock_media_catalog.cjs`, `video_fetcher.js` | Yeni `--metadata` source-page JSON-LD modu; eski downloader korunur. Bilinmeyen boyut/süre uydurulmaz, çıplak CDN linki yeterli değildir |
| `schemas/script.schema.json`, `scripts/validate_script_json.py` | Geriye uyumlu opsiyonel manifest + selection kaydı; varsa tam sıralı scene coverage, benzersiz identity ve zorunlu tam atıf |
| `scripts/phase4_media_probe.py`, `.github/workflows/phase4_media_probe.yml` | Fixed probe input, gerçek provider arama/lisans/download/decode, ayrı izole history ve sentetik tonlu consumer smoke. YouTube/uploader adımı yok, `contents: read` |
| `tests/test_phase4_media.py`, `tests/stock_media_catalog.test.cjs`, `ubuntu_26_test.yml` | 62 hedefli Python ve 5 Node parser testi; gerçek offline IO regresyonları; CI path ve süreç-env izolasyonu |
| İstenen beş belge + baseline/design/inventory/evidence | Mevcut davranış, sözleşme, gerçek/mock ayrımı, riskler ve **geçmeyen kabul kararı** işlendi |

`main.py`, `content_engine.py`, `scripts/gemini_web_story.py`, Studio/API uploader, üretim/pruner/publisher workflow'ları ve `.used_topics.json`, Faz 4 başlangıç commit'i `98392fa` ile byte-level Git diff'te **değişmedi**. Cookie-only Gemini, `GEMINI_COOK`, `GEMINI_API_KEY`, mevcut fallback, Faz 3 source/fact/topic reservation, kanal sırası/concurrency, kapak ve kullanıcı onaylı `partial` PUBLIC politikası korunur. Storyboard'suz yolun eski random/loop/zayıf lisans kontrolleri bilerek korunmuştur; yeni strict garantiler legacy için iddia edilmez.

## 3. Test sonucu — mock ile gerçek IO/provider ayrımı

| Kontrol | Yerel | Son kaynak CI |
|---|---|---|
| Tam Python suite | **233 passed + 16 subtests**, 15.23 sn | **233 passed + 16 subtests**, 11.72 sn |
| Hedefli Faz 4 | **62 passed** | **62 passed** |
| Önceki Faz 3 hedefli suite | Tam suite içinde korunur | **35 passed** ayrıca |
| Node katalog parser | **5 passed** | **5 passed** |
| Mevcut Node pruner mantık | **7 passed** | Bu raporda yalnız yerel tekrar için sayıldı |
| Syntax | Python compile, Node `--check`, mevcut npm syntax; workflow YAML/bash syntax ve diff whitespace | Kurulum/Chromium/syntax ve mevcut FFmpeg smoke adımları başarılı; tam step listesi JSON'da |

Yerel full suite'de tek mevcut `content_engine.py:3329` asyncio deprecation warning'i var. Unit-test child process'inden `GITHUB_REPOSITORY/GH_TOKEN/GITHUB_TOKEN` temizlenir; production history konfigürasyonu gevşetilmez. Test yan etkileri sonrası tracked topic history aslına geri alınıp hash karşılaştırılmıştır.

62 testin çoğunda provider/catalog/download/history cevapları **mock/stub**. Bunlar bağımsız sahne sorgusu, alternative sırası, konu/çözünürlük/oran/süre/lisans retleri, atıf, ID/URL/hash dedup, provider failover/Commons, all-fail ve legacy sınırı gibi deterministik davranışları kanıtlar; canlı sağlayıcı başarısı değildir.

Gerçek, ağsız dosya testleri ayrıca: Pillow decode/ölçüm, bozuk byte/HTML ret, geçerli ve truncated MP4 tam decode, JPEG + sentetik tone ile FFmpeg consumer/sert yuv420p/30 FPS QC. Üç affiliate dalında uploader'ın **yalnız iki mevcut saf metadata fonksiyonu** izole VM'ye alınarak tam atıf korunması test edilir; uploader dosyası import/require edilmez ve entrypoint/YouTube çağrısı çalışmaz. 4900 UTF-16 üst bütçesi aşılırsa render ve history yazımı öncesi strict ret vardır. Gerçek source-provider atıf gerektiren asset'in yayınlandığı sonucu çıkarılmaz.

## 4. Son gerçek sağlayıcı kanıtı

### Pexels ve Pixabay: blocked/unverified

Her ikisinde bu **koşunun** env'inde `api_key_present=false`, `media_cookie_file_present=true`. Bu, hesap/depo genelinde hiçbir anahtar olmadığı veya cookie'nin kesin süresinin dolduğu anlamına gelmez; yalnız probe'a ulaşan konfigürasyon/erişim gözlemidir. Mevcut secret değerleri getirilmedi/değiştirilmedi.

Her biri için sahne 1'de sırasıyla `ocean sea waves` → `ocean waves` → `sea waves water` denendi. API adaptörü anahtar yok/placeholder nedeniyle aramayı atladı. Gerçek Playwright arama sayfaları **403,403,403**; source links/pages/license links **0**. Hiç dosya seçilmedi; sahne fail-closed durdu, genel doğa görüntüsüyle doldurulmadı. İkinci sahneye geçilmemesi güvenli erken durdurmadır; o provider için iki sahne doğrulandı denmez.

Bu nedenle **API download/terms-marker/source-page JSON-LD/stock license/required permissions entegrasyonu başarılı sayılmıyor**. Cloud/browser erişimi ve izinli API konfigürasyonu ayrı çözülmeden aynı probe'u tekrar tekrar tetiklemek kabul kanıtını artırmaz. Erişim kontrolünü aşma veya lisans kapısını gevşetme yapılmadı.

### Wikimedia Commons: gerçek iki sahne seçimi, lisans ve dosya kontrolü geçti

| Sahne | Birincil sorgu / narration | Gerçek source / ölçüm / skor |
|---|---|---|
| 1 | `Moon Apollo astronaut` · “Apollo astronot Ay yüzeyinde duruyor.” | [NASA Apollo 17 Lunar Roving Vehicle.jpg](https://commons.wikimedia.org/wiki/File:NASA_Apollo_17_Lunar_Roving_Vehicle.jpg), ID **12872**, **1920×1920**, image, duration **null**, plan 3.333 sn, **96/100** |
| 2 | `Eiffel Tower Paris` · “Paris Eyfel kulesi görülüyor.” | [Louis-Emile Durandelle, The Eiffel Tower — State of the Construction, 1888.jpg](https://commons.wikimedia.org/wiki/File:Louis-Emile_Durandelle,_The_Eiffel_Tower_-_State_of_the_Construction,_1888.jpg), ID **30184966**, **1920×2443**, image, duration **null**, plan 2.667 sn, **100/100** |

İki sahne farklı ID/source/SHA-256; alternatif query gerekmedi. Dosyalar HTTPS üzerinden gerçekten indirildi, tam Pillow load/decode geçti. Lisanslar per-file **Public domain**, `commons_per_file_extmetadata`; `AttributionRequired=false`. `LicenseUrl` boştu ve **boş korundu**, CC0 URL'si uydurulmadı. Creator ve file-page evidence/hash manifestte saklandı; third-party rights kontrolü `not_verified` kalır.

- Sahne 1'de iki düşük çözünürlüklü aday (birinde ayrıca uygunsuz oran) reddedildi.
- Sahne 2'de üç BY-SA adayı downstream policy uygulanmadığı için, bir aday eksik/desteklenmeyen lisans nedeniyle reddedildi; lisans sessizce standart YouTube lisansına çevrilmedi. Son kod ayrıca lisans adı/sürümü/jurisdiction ile URL tutarlılığını zorunlu kılar; bu ek çelişki fixture'ları mock metadata regresyonudur, final canlı PD kaydında çelişki görüldüğü iddia edilmez.
- Scoring: query 30, narration 20, resolution 15, aspect 6/10, duration 10, provider-provenance proxy 5, license 10; recent-use penalty bu izole run'da 0. Teknik kalite gerçek boyut/süre ve full-decode kapısıyla sınırlıdır; estetik/semantik kalite puanı değildir.

**Görsel inceleme sınırı:** İki inspection karesi açılıp incelendi. İlkinde Ay'da astronot ve rover var, fakat “ayakta durma” eylemi doğrulanmış değildir. İkincisi 1888 inşaat dönemi Eyfel fotoğrafıdır; günümüz/tamamlanmış kule görüntüsü diye sunulamaz. Konu nesnelerinin varlığı gerçek sahneye özgü kanıttır; hareket/çağ/ilişkiyi kusursuz eşleştirme değildir. Runtime etiketleri doğru biçimde **`metadata_supported` / `visual_verification=not_performed`** kaldı; metadata 100 puanı “görsel olarak yüzde yüz doğru” demek değildir.

### Gerçek consumer çıktısı ve bağımsız yeniden kontrol

- `media_probe.mp4`: **6.000 sn, 1080×1920, H.264, yuv420p, limited/tv range, 30/1 FPS, 180 kare; AAC, 48 kHz, mono**. 822155 byte.
- MP4 SHA-256: `d6a1d9757cfcaa775bb62d5df55a88fc4ad55eeb07fe7ee5603414ed7d64f02c`.
- Actions'ta mevcut `validate_output` geçti; artifact indirilip aynı sert QC yeniden çalıştırıldı. Ayrı ffprobe ve **tam ses+görüntü FFmpeg decode** geçti; script validator **0 hata** verdi. Hash/stream ayrıntısı JSON'da.
- Ses **sentetik test tonu**, TTS değil; fixed input Gemini üretimi değil. SRT zamanları sentetik, scene timing narration-word-weighted provisional. **`timing_verified=false`**. Faz 5 gerçek audio-scene hizalaması kabulü değildir.
- Yerel inceleme kopyası `output/phase4_actions_44288761461/`; Git'e MP4/ham medya eklenmedi, örnek YouTube'a yüklenmedi.

## 5. Tekrar geçmişi ve korunan Faz 3

Video içi provider ID, kaynak/download URL ve gerçek byte-hash tekrarları hard-block. Yakın dönem kullanım ayrı local atomik / optional Contents CAS medya history üzerinden **−25 penalty**; son 100 seçim okunur, en çok 200 saklanır. Hash-only recent hit download sonrası puanı değiştirir ama global yeniden sıralama yapmaz; transcode/crop near-duplicate algılama ve dağıtık reservation yoktur.

CAS conflict/reread/merge ve permission failure mock testleri geçti. **Medya history için iki ayrı gerçek Actions persistence run kanıtı yoktur.** Probe yalnız kendi output altındaki history'yi kullanır; production `.media_history.json` oluşturmadı (remote path 404, yerelde yok). Bu özellik canlı concurrency/lost-update kabulü diye sunulmaz.

Faz 3 `.used_topics.json` **25 title / 0 pending** kaldı; title-list SHA-256 `7eca291fbb7b1f462b92210afce9c0c328971d78ef98413a45a3e0644184176d`, local/remote blob **`e5a987fccba23d6d37f1aed76e560cd0647e8f26`** aynı. Önceden kabul edilen Faz 3 CI/reserve/verify yeniden çalıştırılmadı ve o kabul geri açılmadı: [Faz 3 kanıtı](PHASE3_ACTIONS_EVIDENCE_2026-11-18.md).

## 6. Güvenlik ve test komutu düzeltmesi

- `daily_shorts.yml`, `hourly_pruner.yml`, `draft_publisher.yml` **tarafımızdan test-dispatch edilmedi**. `main.py`, gerçek YouTube uploader, silme veya taslak yayınlama çalıştırılmadı. Otomatik cron'un bağımsız faaliyetleri bu raporun eylemleri değildir.
- Dört kaynak revizyonunun yalnız ayrı güvenli live probe'u birer kez dispatch edildi; push CI'ları otomatik oluştu. İlk hata gizlenmedi, düzeltmeden aynı kod körlemesine tekrar tetiklenmedi.
- Probe `contents: read`; stock-domain cookie filtresi var, Google/YouTube session taşımıyor. `ENV_FILE` shell source/eval edilmez, yalnız iki stock key adı veri olarak bellekte parse edilir. Secret değerlerini API'den getirme/yazma/silme yok. Yeni paid API veya görsel üretim yok.
- Sekiz CI/live run'ın bütün job logları supplied GitHub credential ve maskesiz GitHub/Google-key pattern için denetlendi: **0 eşleşme**. İndirilen JSON'lar da tarandı; workflow kendi upload öncesi ENV_FILE/API-key taramasını geçti. Bu, değeri erişilemeyen bütün olası secret'ların matematiksel yokluk ispatı değildir; cookie dosyaları/env/ham stock asset hiçbir artifact listesinde yoktur.
- Credential ignore edilmiş dosyada kaldı; staged/committed değil, origin URL'si credential-free.
- **Önemli yerel komut yan etkisi:** `media_processor.py` argparse/help CLI'si değildir; `python .../media_processor.py --help` yardım göstermek yerine montajı başlatır. Son kontrol sırasında bu komut yanlışlıkla legacy `samples/` yolunu çalıştırdı (YouTube/uploader yok). Etkilenen `samples/script.json` HEAD içeriğine geri alındı; ignored MP4/ASS `output/phase4_legacy_help_side_effect/` altına ayrıldı; topic/media production history değişmedi. Bu çalışma strict storyboard/canlı tüketici kabulü diye sayılmadı. **Bu komutu benign smoke olarak tekrarlama**; güvenli kontrol Python compile veya izole/mock testtir. `phase4_media_probe --help` ve topic-history CLI yardım komutları gerçekten parse edilir. CI workflow'unda tehlikeli media `--help` çağrısı yoktur.

## 7. Kabul matrisi ve sonraki adım

| Ölçüt | Durum |
|---|---|
| Üç sağlayıcının korunması, common contract, kaynak/lisans/atıf alanları | Kod/test var; canlı Commons kanıtı var, stock kanıtı eksik |
| Her scene ayrı query/ordered alternatives/narration; generic/random olmadan all-fail durdurma | Deterministik test + stock gerçek blocked manifest; Commons gerçek iki ayrı source |
| Çözünürlük/oran/süre/decode/license hard gates ve açıklanabilir skor | Test ve Commons gerçek dosya kanıtı; final canlı kaynaklar iki still, hareketli provider video kanıtı yok |
| Zorunlu tam credit ve unchanged uploader tüketimi | Mock provider + gerçek saf JS builder testleri; final canlı PD dosyalarında zorunlu credit yok, gerçek CC BY zinciri ayrıca açık |
| Within-video ID/URL/hash dedup, yakın dönem recency ve atomic history | Kod/mocks; ayrı medya history cross-Actions canlı proof açık |
| Sahne-anlatım gerçek uygunluğu | Konu nesneleri inspection'da var; action/era/relationship otomatik görsel doğrulaması yok, unverified sınırı korunuyor |
| Legacy/Faz 3/secret/yayın davranışının korunması | Kod diff ve tarihsel kabul/hash kanıtı; üretim workflow'u tetiklenmedi |
| Faz 4 tam kabul | **GEÇMEDİ / kısmi provider evidence** |
| Otomatik PUBLIC yayın hazırlığı | **DOĞRULANMADI / hazır denemez** |

**Sıradaki güvenli iş:** Pexels/Pixabay erişimini ve mevcut konfigürasyonun probe'a güvenli aktarımını izinli yoldan doğrulamak; ardından ayrı provider bazında source/license/download/decode ve hareketli/atıf-gerektiren asset tüketici kanıtını almak. Mevcut key/cookie'yi loga/mesaja isteme veya 403'ü aşmaya çalışma; güvenli erişim sağlanamıyorsa blokajı koru. Ayrı medya-history cross-run persistence ve açık Faz 1 gerçek producer→consumer zincirini tamamlamak gerekir; [TODO](../GEMINI_AUTONOMOUS_SHORTS_TODO.md). Faz 5 ses/timing ve son yayın kapısı bunlardan ayrı yürütülür. Ortak sınıf + yeşil mock/CI tek başına Faz 4'ü tamamlamaz.

## 8. Faz4B ek kanıtı — eski ve yeni başarısızlıklar korunur

Başlangıç [`316ae2e`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/316ae2e3e1aff89483d367a5d7ea2e82f0f68665), ana kod [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472), yalnız dependency-workflow düzeltmesiyle final test edilmiş kaynak [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106). CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745) **301+16**, hedefli tekrar altkümeleri35/122/8 ve11 Node başarılı. Önceki core CI [44297771082](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297771082) de successful; farklı source’lar aynı head diye sunulmaz.

İlk media [44297831876](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297831876) 996 saniyelik yavaş Ubuntu apt indirmesinde, provider’a ulaşmadan iptal edildi. Tek gerekçeli dependency-fix sonrası media [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) **failure/partial_provider_evidence_full_acceptance_failed**: Pexels/Pixabay exact-name nonempty allowed API key gözlenmedi; cookie file vardı, browser403. Commons katalog gerçek adaylar buldu; video174336538/83680173 generic download/decode RuntimeError ile reddedildi. Remote render/post-validator/cover/saf metadata’ya ulaşılmadı; HTTP/download/full-decode nedeni ayrışmıyor.

**Aynı final kaynakla ayrı yerel canlı** Commons gerçek hareketli CC BY4.0 video174336538 + CC BY3.0 still83667454, canonical File/creator/deed HTTP200, download/full decode ve actual root writer→same-JSON strict wrapper→cover→saf metadata geçti. Yerel başarı Actions başarısı değildir; explicit fixture/synthetic tone canlı Gemini/TTS veya visual semantic onay değildir.

History [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963) → [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849) kaynak [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472) üzerinde ayrı ref/path: üç synthetic sentinel, gerçek controlled HTTP409/reread/merge, distinct-run aynı blob/entry read, fileDELETE200/refDELETE204/404 cleanup geçti. History bileşenleri final source’la aynı blob’dur. Spontane cross-Actions race/distributed reservation iddiası yoktur.

Altı yeni job logu/üç Actions artifact’i + 11 dosyalı yerel staging audit0; önceki sekiz audit korunur. Production history/main/uploader/kapak/production-pruner-publisher değişmedi. **Faz4B TAM KABUL GEÇMEDİ**: zorunlu stock ve Actions Commons açık. Faz5 başlamadı. [Tam rapor](PHASE4B_ACCEPTANCE_2026-11-18.md) · [Yeni JSON](PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json).
