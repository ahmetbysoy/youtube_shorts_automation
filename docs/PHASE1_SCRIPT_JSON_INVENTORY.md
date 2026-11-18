# Faz 1 — script.json Sözleşme Envanteri

> **Güncel Faz 4C — 2026-11-18: Faz4B NOT_ACCEPTED, Faz5 başlamadı.** Kaynak [`14f7896`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/14f78962f2444e9d03fe0d0caf9b22efff06d927); yeni CI [44313713933](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313713933) **361 Python + 16 alt test**, hedefli tekrar **35/182/8**, **16 Node** geçti. Kullanıcının yeni cookies’i **API kullanılmadan** [44313751238](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313751238) Actions koşusunda test edildi: preflight **8 Pexels + 7 Pixabay eşleşen cookie kaydı**, iki ayrı browser araması **HTTP403 / blocked_unverified**. Commons iki CC BY videoda source/deed/download **200**, tam byte/SHA256 ve container probe geçti; **full_decode_failed**, render/final QC not_reached. API/ENV_FILE bu run’da okunmadı; API key eksikliği cookie testi için blocker değildir. Yeşil CI/offline fixture veya eski yerel Commons, yeni canlı kabul yerine geçmez. Önceki iki-run history/gerçek409 proof’unun üç blob’u aynı; cleanup dört404 ile salt-okur tekrar doğrulandı, yeniden dispatch edilmedi. **22 protected blob, 26 topic/0pending** korundu; üretim/yayın/silme yok. [12 başlıklı yeni rapor](evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) · [JSON](evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json).

> **Tarihsel Faz4B snapshot’ı:** Kaynak `59e2c79`, CI44301070745 **301+16/35/122/8/11Node**; eski yerel canlı Commons tam zinciri geçti, eski Actions44301095341 stock403 ve generic Commons download/decode failure verdi. Bu eski kayıtlar yeni koşu değildir; [Faz4B raporu](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) ve [JSON](evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json) değiştirilmeden korunur.

> İlk kayıt: 2026-11-17. **1–6. bölümler tarihsel başlangıç snapshot'ıdır**; “şema henüz yok/tek doğrulanmış üretici” ifadeleri bugünkü durumu göstermez. Schema v2/runtime kapısı sonradan eklendi. 2026-11-18 Faz 4 sırasında genişletilen statik okuma/yazma taraması ve açık gerçek tüketici işleri **7. bölümde**; Faz4B gerçek explicit-fixture zinciri **8. bölümde**. Dinamik/external caller tamlığı açık; tam Faz1 kabulü hâlâ açık.

## 1. Üretici

Tek doğrulanmış ana üretici `content_engine.py` içindeki `run_content_pipeline()` fonksiyonudur. Senaryoyu `generate_scenario()` ile alır, TTS seslendirmesini üretir, kelime zaman damgalarını toplar, `script.txt` ve `voiceover.srt` dosyalarını yazar, ardından `script.json` payload'ını oluşturur.

Üretim payload'ında şu alanlar bulunur:

| Alan | Mevcut tür / anlam |
|---|---|
| `generated_at` | UTC ISO-8601 tarih/saat metni |
| `llm_provider` | Senaryo sağlayıcısı / fallback etiketi |
| `tts_engine` | TTS motoru ve ses adı |
| `topic` | Konu/kategori metni |
| `title` | YouTube başlığı |
| `description` | Açıklama metni |
| `affiliate_link` | Affiliate URL veya boş/null değer olasılığı; gerçek senaryo üretiminde doğrulanmalı |
| `affiliate_cta` | Affiliate çağrı metni veya boş/null değer olasılığı |
| `cta_line` | Kapanış çağrı metni |
| `thumbnail_prompt` | Eski kapak prompt metni |
| `viral_hashtags` | Etiket dizisi |
| `hook` | Açılış kancası |
| `script_text` | Tam Türkçe seslendirme metni |
| `word_count` | Kelime sayısı |
| `audio_file` | Ses dosyası yolu |
| `srt_file` | Altyazı dosyası yolu |
| `audio_duration_sec` | Ses süresi, saniye |
| `visual_keywords` | Eski medya motorunun kullandığı arama terimleri dizisi |
| `word_timestamps` | Kelime bazlı zaman damgası nesneleri dizisi |

Her `word_timestamps[]` nesnesinde `word` metin, `start_ms` ve `end_ms` sayısal milisaniye değerleridir. Bu zamanlar gerçek Edge-TTS WordBoundary çıktısından gelebilir; gTTS yedeğinde süreye göre yaklaşık dağıtılır. Dolayısıyla yeni şemada zaman kaynağı/kalitesi ayrıca belirtilebilir; mevcut alanların anlamı değiştirilmemelidir.

## 2. Doğrulanmış tüketiciler

1. `src/media_processing/media_processor.py` dosyası `script.json` okur. Şu an ana medya sözleşmesi `visual_keywords` alanıdır; alan yoksa genel varsayılan anahtar kelimelere düşer. Wikimedia lisans atıfları eksikse `description` alanını güncelleyip JSON dosyasını tekrar yazar.
2. `scripts/embed_cover_frame.py` dosyası `script.json` okur ve `title` ile `topic` alanlarını kullanır. Kod açıklaması `thumbnail_prompt` alanının artık varsayılan kapak promptunda kullanılmadığını açıkça belirtir.
3. `tests/test_full_pipeline_fallback.py` uçtan uca üretim testinde `script.json` dosyasının oluşmasını ve temel alanların varlığını kontrol eder. Henüz JSON Schema doğrulaması yoktur.

Bu envanterde doğrulanmamış olası tüketiciler tamamlanmış sayılmaz. Kod araması ve çalışma akışı incelemesi Faz 1'in devamında genişletilecektir.

## 3. Örnek dosya uyumsuzluğu

`samples/script.json` mevcut bir örnektir; üreticinin güncel payload'ıyla birebir aynı değildir. Örnekte `affiliate_link`, `affiliate_cta` ve `cta_line` alanları bulunmaz. Örnek dosyanın `generated_at` tarihi 2026-11-02'dir. Bu nedenle örnek, tek başına güncel ve zorunlu alanların kesin kaynağı kabul edilmemelidir.

## 4. Storyboard durumu

Mevcut üretici payload'ında `storyboard`, `schema_version`, `generation_id`, `fact_check`, kaynak kayıtları veya sahne bazlı medya alanları yoktur. Medya işlemcisi tek bir `visual_keywords` dizisi tüketir. Bu yüzden storyboard yeni şemada geriye uyumlu ve ayrı bir alan olarak eklenmeli; eski `visual_keywords` tüketicisi geçiş süresince çalışmaya devam etmelidir.

## 5. Faz 1 tasarım kuralları

- Önce mevcut payload ve örnekler testlerle sabitlenmeli; ardından versiyonlu JSON Schema eklenmeli.
- `schema_version` olmayan eski JSON geçiş dönemi sürümü olarak tanınmalı; sessizce yanlış alanlara dönüştürülmemeli.
- Yeni `storyboard`, `fact_check`, `sources` ve `generation_id` alanları eklenirken eski tüketiciler kırılmamalı.
- `visual_keywords` mevcut medya işlemcisi tamamen taşınana kadar korunmalı.
- `description` alanının Wikimedia atıf güncellemesi nedeniyle JSON tüketicisi salt-okunur varsayılmamalı.
- Hatalı JSON, yanlış tip, eksik zorunlu alan, negatif/ters zaman damgası ve geçersiz URL gibi durumlar test edilmelidir.
- Faz 1 yalnız JSON sözleşmesi ve test altyapısını kapsar; üretim workflow'u, yayın davranışı, cookie'ler ve secret'lar değiştirilmez.

## 6. Kanıt kaynakları

- `content_engine.py` — `run_content_pipeline()` payload üretimi.
- `samples/script.json` — 2026-11-02 tarihli gerçek örnek.
- `src/media_processing/media_processor.py` — `visual_keywords` tüketimi ve açıklama güncellemesi.
- `scripts/embed_cover_frame.py` — `title` / `topic` tüketimi.
- `tests/test_full_pipeline_fallback.py` — mevcut çıktı sözleşmesi için test.
- `tests/test_content_engine_fallback.py` — senaryo alanları için test.


## 7. 2026-11-18 Faz 4 — genişletilmiş statik üretici/tüketici taraması

> Bu bölüm c29f7e7/e4d1144 tarihsel snapshot’ıdır. Fixture consumer/cover boşluğu Faz4B §8’de yerel canlı ve CI offline kapsamıyla daraltıldı; canlı Gemini/TTS ve dinamik runtime tamlığı hâlâ açık.

İnceleme kaynak kodu `c29f7e7` (medya kodu; tabloyu etkileyen diğer dosyalar Faz 4 öncesiyle aynı). Yöntem: Git'in izlediği Python/JS/CJS/shell/YAML dosyalarında `script.json`, `DEFAULT_JSON_OUT`, `SCRIPT_PATH`, `script_data`, JSON read/write ve metadata/storyboard alanları arandı; aşağıdaki gerçek çağrı/alan noktaları okundu. Bu, dinamik yol aktarımı ve tüm import/caller kombinasyonlarının kanıtı değildir. Cookie/ENV_FILE/credential dosyası okunması bu envanterin parçası değildir.

| Yol | Rol / doğrulanan alanlar | Kanıt / kalan sınır |
|---|---|---|
| `content_engine.py:3351–3421` | Üretim ana writer: v2 + UUID, audio/srt/duration, legacy visual_keywords ve word_timestamps; Gemini sources/fact_check/storyboard/claims/prompt sürümünü korur | `main.py` bu dosyayı `--gemini-web-only` ile çağırır. `generate_gemini_web_scenario:3051` normalizasyon sonrası narration/claim span kontrol eder. Gerçek yeni-code Gemini+TTS+media zinciri bu görevde çalıştırılmadı |
| `scripts/gemini_web_story.py:413–434` | Ara dict dönüştürücü; doğrulanmış storyboard/alternatives nesnelerini korur, legacy keywords listesine query'leri de taşır | Disk `script.json` writer'ı değil; raw cookie taslak yanıtı ayrı sözleşmedir |
| `src/content_generation/engine.py:610–660`, `src/content_generation/__init__.py` | **İkinci, eski bağımsız writer**; paket public exports'u buraya gider. v2/storyboard alanlarını yazmaz; legacy payload üretir | Root `content_engine.py` sarmalayıcısı değildir. Mevcut `main.py` yolu bunu çağırmaz; başka dış caller'lar için sözleşme/runtime doğrulama çalışması açık. Bu Faz 4 işinde değiştirilmedi |
| `src/media_processing/media_processor.py:628–747` | Reader + writer: storyboard anahtarı strict route; selector başarılıysa scene_media/media_selection/media_credits/description atomik yazılır. Storyboard yoksa legacy query/duration ve eski Commons attribution yazımı | Başarısız strict scene montage'a geçmez. Legacy random/loop/atıf kesme sınırlamaları korunur, strict doğrulanmış sayılmaz |
| `src/media_processing/scene_media.py` | Mutating helper: her scene'in metadata/license/ölçüm/provenance kaydı ve tam attribution; ayrı history | Kendi başına public uploader değildir. Manifest ayrı kanıt dosyasıdır; script dosyasını processor atomik kaydeder |
| `scripts/validate_script_json.py:17–48`, `main.py:165–201` | JSON reader/validator, medya öncesi ve sonrası fail-closed orchestration. Optional manifest varsa birebir sıralı scene coverage, identity dedup ve mandatory description credit | Main'in kendisi script JSON içeriğini okuyup dönüştürmez; child validator çağırır. Uploader'ın doğrudan çalıştırılması bu orchestration kapısını atlar; bu görevde kullanılmadı |
| `scripts/embed_cover_frame.py:169–189` | JSON salt-okur; `title` ve `topic`; eski thumbnail_prompt'u varsayılan prompt için okumaz | Video/kapak dosyası değiştirebilir; script JSON yazmaz. Tam storyboard+atıf+kapak entegrasyon testi açık; kapak kodu değiştirilmedi |
| `youtube_studio_uploader.js:458–501,823–831` | Production reader: title (100), description, affiliate_hook/CTA/link, cta_line, ilk 3 viral_hashtags, thumbnail_prompt; sonra ayrı topic tüketimi | `buildFinalDescription` ek bloklardan sonra **JS UTF-16 `.slice(0,4900)`** uygular; sadece script.description uzunluğunu kontrol etmek tam atıf garantisi değildir. Faz 4 strict selector, mevcut builder için konservatif UTF-16 üst bütçe kontrolü ekler. Üç affiliate dalı gerçek **saf fonksiyonlarla**, ağsız VM'de test edilir; gerçek uploader entrypoint'i çalıştırılmaz/değiştirilmez. Studio formuna kalıcı atıf aktarımı hâlâ canlı kanıt değildir |
| `src/youtube_upload/youtube_uploader.py:182–198,89` | Ayrı API yedek reader: title/description, upload snippet'te description[:5000]; PRIVATE queue ve approve CLI | Güncel main Studio yolunda değil. JSON Schema/scene_media'ya doğrudan bağlı değil; gerçek API tüketici entegrasyonu açık. Çalıştırılmadı |
| `scripts/phase4_media_probe.py` | Test-only writer: fixed iki-scene input → selector → schema validation → izole output script/manifest | Gerçek provider HTTP/download ve consumer smoke içerir; Gemini/TTS çıktısı değildir. Production `script.json`/history'yi değiştirmez |
| `.github/workflows/daily_shorts.yml:319` / `phase4_media_probe.yml` | JSON'u artifact listesine koyar; kendi başına alan reader/writer değil | Güvenli probe yalnız sanitized output seçer; production workflow tetiklenmedi |
| `samples/script.json`, `tests/test_*` | Fixture ve test-only writers/readers | Üretim çağrısı/YouTube consumer kanıtı değildir |

### 7.1 Açık Faz 1 kabul işleri (kapatılmadı)

- İkinci eski producer ve paket caller'ları, dinamik/CLI JSON path aktarımı, bütün external API tüketicilerinin sözleşmesi/geriye uyumluluğu tamamlanmış sayılmaz; genişletilmiş statik tarama tam runtime inventory değildir.
- Gerçek root content-engine JSON + gerçek TTS dosyaları → **aynı production media CLI** → post-media validator → kapak → gerçek uploader'ın **yayınsız** veri tüketimi uçtan uca doğrulanmadı. `main.py`/YouTube uploader/production workflow'ları bu görevde çalıştırılmadı; aşağıdaki standalone legacy CLI yan etkisi bundan ayrıdır.
- Faz 4 canlı probe selector + gerçek download/decode + assemble/QC'yi doğrular, fakat `run_media_pipeline` strict wrapper entegrasyon testinde provider/download/montaj kısımları stub/mock'ludur. **Media CLI `--help` parse etmez:** son kontrolde benign yardım varsayımıyla yapılan çağrı gerçekte legacy samples montajını çalıştırdı. `samples/script.json` HEAD içeriğine geri alındı, ignored MP4/ASS ayrıldı; topic/media production history ve uploader etkilenmedi. Bu yanlış çağrı gerçek strict producer→consumer kabulü değildir. Yardım smoke'u diye tekrarlama; yalnız Python compile/izole test veya gerçek argparse probe/topic CLI'larını kullan. Ayrıntı [kanıt raporu §6](evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md#6-güvenlik-ve-test-komutu-düzeltmesi).
- Yeni zorunlu-atıf bütçesi ve gerçek saf JS builder testleri belirli bir tüketici kontrat boşluğunu daraltır; Studio'nun kaydettiği açıklamanın tamlığına veya genel yayın kalite kapısına kanıt oluşturmaz.
- Başarılı güncel schema/CI, eski Faz 1 kutularını ya da Faz 5 ses-sahne zamanlamasını kendiliğinden kapatmaz.

## 8. 2026-11-18 Faz4B — aynı JSON gerçek tüketici entegrasyonu

Kaynak [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106), CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745). **Aşağıdaki bütün zincir aynı kaynakla yerel canlı Commons’ta geçti; CI provider/download offline fixture kullanır. Actions canlı [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) selection’da bloklandı.** Fixture ≠ canlı Gemini/TTS. [Kanıt](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md).

| Aşama | Gerçek çağrı/veri | Fixture veya açık sınır |
|---|---|---|
| Ara dönüşüm | Gerçek scripts.gemini_web_story.draft_to_script_metadata storyboard/legacy keywords/fact metadata taşır | Girdi explicit sabit taslak; Gemini Web çağrılmadı |
| Ana üretici | ROOT content_engine.run_content_pipeline gerçek v2 UUID ve JSON/TXT/SRT yazar | Yalnız generate_scenario/synthesize_voiceover sınırları fixture/synthetic tone; model/TTS/normalizasyon başarısı iddiası yok |
| Eski üretici | src/content_generation.engine.run_content_pipeline bağımsız legacy writer; paket export’u ona gider | Root wrapper değil; bu zincirde çalışmadı/değiştirilmedi; dış caller tamlığı açık |
| Ön kapı | validate_payload + gerçek validate_script_json --input SAME_PATH; 0 schema hata | main.py çalıştırılmadı; başarısız Actions’ta da bu kapı geçti |
| Medya | Gerçek run_media_pipeline → strict selector → download/probe/ASS/FFmpeg/QC → aynı JSON atomic persist | İzole path/provider/history factory; yerel canlı gerçek HTTP, CI offline fixture; Actions selection fail |
| Son kapı | Reload aynı UUID/storyboard/narration; scene_media/selection/media_credits/description ve gerçek post-validator | Fact status unavailable kalır; Actions’ta ulaşılmadı |
| Kapak | Gerçek embed_cover_frame.main --no-ai, cover üretilir/izole MP4 değişir, JSON SHA aynı | Best-effort exit0 tek başına yeterli sayılmaz; AI/network/semantic onay yok; Actions’ta ulaşılmadı |
| Uploader metadata | Unchanged source’tan gerçek readScenarioField/buildFinalDescription, ağsız kısıtlı VM | Uploader require/import/entrypoint/Studio/UI kalıcılığı yok; Actions’ta ulaşılmadı |
| Credit budget | İki mandatory CC BY atfı description+media_credits+actual builder’da tam; 858 UTF16≤4900 | Affiliate üç dal/emoji4900 sınırı Node fixture’da ayrıca testli; gerçek yayın yok |

Pre-media snapshot gerçek root writer çıktısının exact bytes kopyasıdır. Post-media JSON SHA cover ve saf JS’den sonra değişmez; gerçek full AV decode uygulanır. Ayrı iki-Actions history proof bu local selection-history dosyasından çıkarılmaz; kendi remote ref/path/409/read/cleanup kanıtıdır.

**Kapanan alt boşluk:** izin verilen explicit fixture ile actual writer→same JSON strict wrapper→post validator→cover→saf metadata. **Açık kalan:** dinamik/external caller’lar, eski writer’ın tüm kullanımları, backup API/Studio consumer, canlı Gemini/TTS ve Faz5 timing/audio; ayrıca Actions canlı Commons seçimi. Tam Faz1 veya PUBLIC hazırlığı işaretlenmez.

## 9. 2026-11-18 Faz4C yeniden doğrulaması ve failure sınırı

Kaynak14f7896 / CI44313713933,182media ve8actual-consumer altküme tekrarı dahil361+16Python/16Node ile geçti. §8’deki gerçek bileşenler CI’da offline provider/download fixture ve synthetic tone ile yeniden çalıştı; uploader entrypoint’i veya canlı Gemini/TTS/Studio yoktur. Eski yerel59e2c79 kanıtı yeni Actions pass diye kullanılmaz.

Yeni cookie-only canlı Actions44313751238’de üç provider için root writer/ara dönüşüm/pre-validator gerçekten geçti; SAME JSON strict wrapper selection’da durdu. Her provider’da pre_media_script.json/script.json exact bytes aynı, schema0error, aynı UUID/storyboard/narration/fact-unavailable. Stock403; Commons metadata/File/deed/download200 ve probe sonrası full_decode_failed. Post-validator/cover/pure metadata/finalMP4QC’ye ulaşılmadı, script’e scene_media atanmadı. Bunlar [Faz4C raporunda](evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) ve [makine kanıtında](evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json) ayrı kayıtlardır. Tam Faz1 runtime inventory, mandatory live media/Faz4B ve Faz5 timing/audio kapanmaz.
