# Gemini Tabanlı Otonom Shorts — Canlı TODO

> Bu dosya uygulamanın tekil takip listesidir. Bir kutu yalnız ilgili kod/test/CI veya canlı kanıt elde edilince işaretlenir. Mimari: [GEMINI_AUTONOMOUS_SHORTS_PLAN.md](GEMINI_AUTONOMOUS_SHORTS_PLAN.md).

## Durum özeti

- [x] Mimari plan ve TODO GitHub'a dokümantasyon olarak eklendi.
- [x] Kod entegrasyonu başladı: JSON v2 metadata ve üretim öncesi fail-closed doğrulama kapısı eklendi; Faz 1 kabulü henüz tamamlanmadı.
- [x] Faz 0 başlangıç incelemesi, doküman uzlaştırması ve güncel test baseline tamamlandı; secret metadata ad envanteri connector kısıtı ve kullanıcının secret'ları koruma kararı nedeniyle istisna olarak kapatıldı. Hiçbir secret değiştirilmedi.
- [x] `main.py` içerik motorunu `--gemini-web-only` ile çağırır; `daily_shorts.yml` `GEMINI_COOK` secret’ını process env’e verir. Cookie/schema/source kontrolü başarısızsa mevcut yerel fallback kullanılır ve ücretli text API’ye geçilmez. Eski gerçek cookie dry-run ve yeni Faz 3 CI/kalıcılık kanıtları aşağıdadır; yeni kodla canlı üretim/yayın entegrasyonu kapsam dışıdır.
- [x] `script.json` v2’ye Gemini `sources`, `fact_check`, `storyboard`, `claims` ve prompt sürümü taşınır; medya işlemcisi `storyboard[].visual_query` değerlerini tercih eder. Scene timing/media QC açık; Faz 3 claim kontrolü ve iki-run kalıcılık kabulü tamamlandı.
- [ ] Yeni kalite kapısı yayın akışına bağlanmadı.

## Faz 0 — Başlangıç envanteri ve emniyet

- [x] GitHub varsayılan branch ve HEAD commit'i kaydet (yerel çalışma ağacı DNS nedeniyle doğrulanamadı; kanıt belgesinde açıklandı).
- [x] daily_shorts.yml tetikleyicileri, concurrency/lock, matrix ve ana job komutlarını incele.
- [x] Son başarılı workflow koşularını ve test koşusunu karşılaştır; gerçek run kanıtını kaydet. (Güncel production run ve önceki iptal koşuları da not edildi.)
- [x] main.py orkestrasyon adımlarını ve exit-code politikasını kod üzerinden incele; gerçek üretim loguyla karşılaştır. (Yerel çalıştırma yapılmadı.)
- [x] Başlangıç HEAD `d65623d` üzerinde content_engine provider/fallback akışını inceleyip `main.py --force-fallback` durumunu doğrula; 18 Kasım değişikliğiyle bu çağrı Gemini Web-only olarak güncellendi.
- [x] media_processor.py ve video_fetcher.js arama sırası, API/Playwright fallback'leri, lisans ve klip seçimini incele; son gerçek run'daki Wikimedia fallback örneğini kaydet.
- [x] youtube_studio_uploader.js yayın sonucu doğrulamasını ve belirsiz upload davranışını incele; Studio PUBLIC doğrulaması ve publish_unverified hata yolunu doğrula.
- [x] Mevcut test paketinin son güvenli CI baseline'ını kaydet: 108 passed, 8 subtests passed (run 44076814790). Güncel HEAD'de yerel tekrar yapılamadı; sınırlar kanıt belgesinde.
- [~] Secret metadata envanteri: GitHub connector Secrets API'yi desteklemiyor; kullanıcı mevcut Gemini cookie ve API secret'larının aynen kalmasını istedi. Hiçbir secret değeri okunmadı, yazılmadı veya silinmedi. İsim envanteri yapılmadı; mevcut secret'lar korunuyor.
- [x] Pruner, cron/watchdog, kanal ve PUBLIC kurallarını koruma listesine al. (hourly_pruner.yml ve draft_publisher.yml incelendi; gerçek silme/PUBLIC yayın riskleri, concurrency farkı ve tetikleme ilişkileri kanıt raporunda.)
- [x] Başlangıç envanteri ve baseline kanıtını [Faz 0 kanıt raporuna](evidence/FAZ0_BASELINE_2026-11-17.md) ekle.

**Kabul kapısı:** Mevcut davranış ve test baseline'ı biliniyor; yayın davranışı değiştirilmedi. Secret metadata envanteri erişim kısıtı ve kullanıcının 'mevcut secret'ları koru' kararı nedeniyle kapsam dışı bırakıldı; bu istisna kanıt raporunda kayıtlı.

## Faz 1 — JSON sözleşmesi ve test altyapısı

- [x] İlk script.json üretici/tüketici envanterini çıkar ve gerçek örnekle karşılaştır: [PHASE1_SCRIPT_JSON_INVENTORY.md](PHASE1_SCRIPT_JSON_INVENTORY.md). (content_engine.py üretici; media_processor.py ve embed_cover_frame.py doğrulanmış tüketiciler.)
- [x] Mevcut JSON örneğini ve geriye uyumluluk gereksinimlerini kaydet. (samples/script.json eski örnek; üretici payload'ıyla alan farkları belgelendi.)
- [ ] Repo genelindeki ek script.json okuyucu/yazıcı yollarını taramayı tamamla.
- [x] Versiyonlu JSON Schema tanımla: `schemas/script.schema.json` (legacy v1 + current v2).
- [x] `schema_version`, `generation_id`, `fact_check`, `sources` ve `storyboard` alanlarının tiplerini belirle.
- [x] Legacy örnek, v2 örneği, eksik alan, yanlış tip, bozuk UUID ve timestamp sınır testlerini ekle: `tests/test_script_json_schema.py`.
- [x] Yeni üretim payload'ına `schema_version=2.0` ve UUID `generation_id` ekle; eski medya alanları aynen korundu.
- [x] Uçtan uca fallback testine gerçek üretilen JSON'un schema doğrulamasını ekle.
- [x] `jsonschema` test bağımlılığını test ve runtime gereksinimlerine ekle; CI doğrulaması başarılı.

- [x] `scripts/validate_script_json.py` doğrulayıcısını ekle ve `main.py` içinde medya işlemeden önce zorunlu fail-closed kapı olarak çalıştır.
- [x] Runtime doğrulayıcı testlerini ekle; CI run [44164802326](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44164802326): **123 passed, 8 subtests passed**.

**Kabul kapısı:** Şema ve runtime kapısı uygulanmış durumda; tam Faz 1 kabulü için repo genelindeki okuyucu/yazıcı taraması ve gerçek tüketici entegrasyon testi hâlâ açık.

## Faz 2 — Gemini Web cookie adaptörü ve prompt

- [x] Mevcut GEMINI_COOK cookie kullanımını ve gemini_webapi oturum akışını incele; cookie değerini hiçbir zaman loglama. (Mevcut kapak adaptörüyle uyumluluk kontrol edildi; `__Secure-1PSIDTS` opsiyonel.)
- [x] Dry-run bağımlılığını tekrarlanabilirlik için `gemini_webapi==2.1.1` sürümüne sabitle.
- [x] Yayın yapmayan gerçek cookie dry-run ile metin/JSON üretimini doğrula. [Run 44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017), SHA `57166f8`, başarılı; gerçek `gemini-web-session` üzerinden 58 kelimelik Türkçe taslak, 5 storyboard sahnesi ve 3 claim üretildi; `draft_only=true`, `publish=false`. Önceki run'lar 44222170240/44260607346 secret-missing değildi: Python probe çalıştı ve yalnız genel `ValueError` loglandı. Komut bloğundaki missing-secret yazısı yanlışlıkla gerçek hata sanılmıştı; eski ValueError'ın alt nedeni güvenli loglama nedeniyle belirlenemiyor.
- [~] Timeout, expired-session, 429 etiketli hata ve bozuk JSON fallback/API-isolation davranışları mock testleriyle doğrulandı (30 passed + 4 subtests); canlı timeout/expired-session/rate-limit testi yapılmadı. Gerçek cookie dry-run başarılı.
- [x] Versiyonlu prompt dosyası ve ayrı Gemini Web yanıt şeması ekle; konu/kaynak, senaryo, storyboard, arama ve kapak alanlarını tanımla (`prompts/gemini_web_story_v1.md`, `schemas/gemini_story_response.schema.json`). Yerel/mocked testler ve gerçek run 44262444017'de schema doğrulamalı cookie yanıtı başarılı.
- [x] Son 25 kalıcı başlık ve yerel topic-ledger kimlikleri prompta eklenir; Faz 3 altında kalıcı CAS rezervasyonu uygulandı. Cross-Actions proof [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) → [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) ile başarılı; kullanılan 25 başlık korundu.
- [x] Gerçek run'da ham Gemini yanıtı `validate_grounded_response` içinde `gemini_story_response.schema` ile doğrulandı; artifact'taki model sözleşmesi alanlarının şema projeksiyonu da Draft 2020-12 ile ayrıca doğrulandı.
- [x] Cookie/oturum/draft hatasında mevcut fallback'e dön; `gemini_web_only` dalında Groq/Gemini API sağlayıcılarının çağrılmadığını test et (`tests/test_gemini_web_content_engine.py`). Yeni yerel mock kontrollerinde timeout, expired-session, 429 etiketli hata ve bozuk JSON için fallback/API-isolation doğrulandı (30 passed + 4 subtests seçili suite); bunlar canlı Gemini doğrulaması değildir.
- [x] Yeni metin üretim adaptörünün `GEMINI_API_KEY` istemediğini test et; web-only dalı bu anahtarı okumaz ve testte Gemini/Groq API sağlayıcıları çağrılmadı. Gerçek başarılı run 44262444017 artifact'inde `provider` ve `llm_provider` `gemini-web-session`; workflow yalnız `GEMINI_COOK` geçirir.
- [x] Yayın yapmayan dry-run kanıtını gizli bilgi içermeden kaydet: [run 44262444017 artifact](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017), `text_probe_result.json`; cookie/PAT/API-key pattern taraması temiz. Loglardaki Authorization değerleri maskeli.

**Kabul kapısı:** [Run 44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017) ile cookie-session üzerinden gerçek taslak alındı; schema doğrulandı, artifact tarandı, `publish=false` ve hiçbir yayın workflow'u tetiklenmedi. Önceki run'lardaki hatalar genel `ValueError` idi; missing-secret değildi. Artifact/log taramasında cookie değeri, supplied PAT veya API key izi bulunmadı; Authorization değerleri maskeli. `fact_check.status=partial` bağımsız semantik doğrulama anlamına gelmez ve bu kullanıcı onaylı ayrımı korur. Mevcut legacy kare analiz API yolu kullanıcı onayı olmadan değiştirilmez.

## Faz 3 — Kaynak doğrulama ve tekrar koruması

Durum: **YAYINSIZ KABUL TAMAMLANDI (2026-11-18).** Doğrulanmış kod `0dee88e18e05269e7d4f7360614123eb890f4e80`; gerçek yeni-kod CI ve iki ayrı Actions run kanıtları aşağıdadır. Bu kabul gerçek YouTube üretim/yayın veya yeni canlı Gemini model testi anlamına gelmez.

- [x] Exact `quote_match` kontrolünü koru ve `semantic_support`’tan bağımsız kaydet (`scripts/semantic_fact_check.py`). Bilinen relation/subject terimleri ayrı değerlendirilir; desteklenmeyen/çelişen ilişki `rejected`, tanınmayan/eksik ilişki `partial`; bilinmeyen ilişki `verified` olamaz. LLM self-approval yok.
- [x] Kritik sayı/tarih/yüzde/mesafe/hız ve birimleri deterministik karşılaştır; km/mile, km/h/m/s/mph, süre, yüzde, kütle ve sıcaklık dönüşümleri test edildi. Numeric contradiction kritik claim’i reddeder.
- [x] Wikipedia REST summary + canonical article URL HTTP erişimi, redirect host/path, canonical sayfa kimliği/title ve boş/bozuk payload kontrolü. Gerçek HTTP probe: `Venus`, HTTP 200 + canonical identity match. Eski Gemini run 44262444017 yeni kodun canlı model kanıtı değildir.
- [x] V2 schema `verified`, `partial`, `rejected`, `unavailable` durumlarını ekler; eski v1/v2 değerleri geriye uyumlu. Kullanıcı onaylı `partial` yayın davranışı değişmedi; `partial` asla `verified` diye etiketlenmez.
- [x] Desteklenmeyen kritik claim üretimi durdurur / mevcut fallback-reselection’a döner; source unavailable durumunda `verified` üretilmez.
- [x] `.used_topics.json` legacy title array’ini v2 store’a yükselt; normalized topic, category, entities, core claims, scenario tokens, previous titles ve pending reservations tutulur. Okunamayan/bozuk geçmiş fail-closed. Gerçek iki-run testinde eski 25 başlık byte-düzeyi title-list hash’iyle korundu.
- [x] Contents API `sha` CAS rezervasyonu; conflict sonrası bounded reread/retry, success commit / failure release ve 30 dk orphan TTL. Daily workflow’a entegrasyon ve module entrypoint düzeltmesi yapıldı; kanal sırası/concurrency/uploader/yayın politikası korunur. Gerçek daily uçtan uca finalize yolu bu kabulde çalıştırılmadı.
- [x] Mock coverage: semantic yes/no, sayı/tarih/birim çelişkisi, inaccessible/empty/broken/foreign-canonical source, farklı başlıkta aynı konu, paraphrased core claim, eşzamanlı reservation, SHA conflict, unreadable history ve failure release. CI’da **35 hedefli Faz 3 testi** geçti; mock testler gerçek HTTP veya canlı yarışma kanıtı değildir.
- [x] Actions CLI/package import, probe bağımlılığı ve reserved `GITHUB_*` değişkenlerini test child process’ten temizleme için **6 regresyon testi** eklendi; production fail-closed korunur. Temiz venv’de yalnız pinned `requests` ile iki CLI `--help` smoke başarılı.
- [x] Push sonrası yayınsız Ubuntu 26 CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329), SHA `0dee88e`: **171 passed + 16 subtests passed**. FFmpeg/font/Xvfb, Python/Node bağımlılıkları, Playwright Chromium kurulumu, uploader syntax ve FFmpeg bindirme smoke adımları başarılı.
- [x] Cross-run persistence: reserve [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395), ayrı verify [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635), aynı `probe_id=phase3-20261118`. İlk run pending entry’yi kalıcı yazdı; ikinci run okuyup release etti. `pending` **0 → 1 → 0**, `used_titles` **25 → 25 → 25**, test başlığı used history’ye eklenmedi. Verify ve CI kodları aynı; aradaki tek dosya farkı `.used_topics.json`.
- [x] Yerel full suite **171 passed + 16 subtests**, Node **7 passed**, Node syntax/YAML/bash syntax/diff kontrolleri başarılı. Üç başarılı Actions run logunda supplied credential veya maskelenmemiş GitHub/Google key pattern yok; artifact sayısı 0. Credential ignore edilmiş/untracked durumda, Git config’e yazılmadı; Repository Secret’lar değiştirilmedi.

**Kabul kapısı: GEÇTİ.** İki zorunlu koşulun da yeni kod üzerinde gerçek Actions kanıtı var. [Actions raporu](evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md), [JSON kayıt](evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.json), [ayrı yerel kanıt](evidence/PHASE3_LOCAL_EVIDENCE_2026-11-18.md). Üretim/publisher/pruner tarafımızdan tetiklenmedi; canlı CAS yarışması, gerçek daily finalize/publication ve genel amaçlı semantik doğruluk kanıtlanmış değildir.

## Faz 4 — Sahne bazlı medya motoru

- [x] Medya işlemcisinde storyboard sahnelerinin `visual_query` değerlerini, varsa legacy `visual_keywords` alanına tercih et; storyboard yoksa eski arama ve güvenli varsayılan davranışı koru. Birim testleri geçti. Bu henüz sahne-süre eşleme veya alternatif sorgu retry değildir.
- [ ] Pixabay/Pexels/Wikimedia adaptörlerinin gerçek davranışını ve lisans alanlarını belgele.
- [ ] Ortak medya sağlayıcı arayüzü oluştur.
- [ ] Her storyboard sahnesi için ayrı sorgu ve alternatif sorgu üret.
- [ ] Adayları konu uyumu, süre, çözünürlük, oran, kalite ve lisansa göre puanla.
- [ ] Medya kaynağı/URL/lisans/atıf verisini sahne kaydında sakla.
- [ ] Aynı video içindeki klip tekrarını ve yakın dönem tekrarını azalt.
- [ ] Alakasız medya örneklerini reddeden testler ekle.
- [ ] Uygun medya yoksa sınırlı sorgu yenile; rastgele klibe düşme.
- [ ] Onaylı temsili canlandırma veya güvenli durdurma davranışını test et.

**Kabul kapısı:** Her sahnenin kabul edilmiş medya kaynağı ve lisans kaydı var; başarısız sahne rastgele kliple doldurulmuyor.

## Faz 5 — Ses, zamanlama ve FFmpeg montajı

- [ ] TTS word timestamp biçimini ve ses dosyası sözleşmesini sabitle.
- [ ] Storyboard sahne sınırlarını gerçek ses zamanlarına bağla.
- [ ] Sahne başına trim/scale/crop/concat montajını uygula.
- [ ] 1080x1920, 9:16, FPS, codec, pixel format ve ses akışını doğrula.
- [ ] Altyazı senkronu, okunabilirlik, güvenli alan ve taşma kontrollerini ekle.
- [ ] Siyah/boş kare, eksik sahne, sessizlik ve clipping kontrollerini ekle.
- [ ] Gerçek örnek MP4 üzerinde ffprobe ve otomatik test kanıtı al.
- [ ] Mevcut FFmpeg montajıyla süre/bellek/kalite karşılaştırması yap.

**Kabul kapısı:** Sahne, ses, altyazı ve süre uyumlu; teknik video testleri geçiyor.

## Faz 6 — Semantik kalite kapısı ve karantina

- [ ] Sahne görseli ile anlatımın eşleşmesini kontrol eden ilk sürüm kurallarını uygula.
- [ ] Görüntü analiz modeli gerekirse yalnız ücretsizliği/erişimi doğrulanmışsa değerlendir.
- [ ] İçerik doğruluğu, medya alaka, tekrar, lisans, ses, altyazı ve video testlerini tek raporda birleştir.
- [ ] Kritik hata kodları ve sınırlı retry tanımla.
- [ ] Başarısız MP4'ü yayın kuyruğundan ayır.
- [ ] Bilerek bozuk/alakasız örneklerle fail-closed testleri yap.

**Kabul kapısı:** Kalite kontrolünü geçmeyen video uploader'a ulaşamıyor.

## Faz 7 — Kapak ve metadata

- [ ] Kapak kaynağı ve maliyet koşulunu doğrula; ücretli görsel üretimi çağırma.
- [ ] Kapak metninin Türkçe, okunaklı ve konuyla ilgili olduğunu test et.
- [ ] Kapak ile video ana konusunun eşleşmesini doğrula.
- [ ] Başlık, açıklama, kaynak, CTA ve hashtag tutarlılığını test et.
- [ ] Gerçekçi canlandırmalarda sentetik içerik beyanı gerekliliğini değerlendir.
- [ ] Kapak yükleme sonucunu doğru video ID'si üzerinden Studio'da doğrula.

**Kabul kapısı:** Metadata/kapak doğru video ile eşleşiyor; yükleme kanıtı var.

## Faz 8 — Gölge mod ve taslak pilotu

- [ ] Yeni üretim hattını PUBLIC yayın kapalı olarak workflow'a bağla.
- [ ] Gerçek CI artifact'ı ve logları incele; secret sanitizasyonunu kontrol et.
- [ ] Tek video pilotunda doğru video ID, görünürlük, başlık, kapak ve tekrar upload korumasını uygula.
- [ ] Upload belirsizliğinde aynı video ID'sini araştırmadan yeniden yükleme yapma.
- [ ] Pilot hatalarını ve düzeltmeleri kaydet.
- [ ] PUBLIC yayın için gereken kullanıcı kararını ve repo kurallarını teyit et.

**Kabul kapısı:** Pilot güvenli ve doğrulanabilir; yayın otomatik açılmaz.

## Faz 9 — Kontrollü otomatik yayın

- [ ] Yalnız tüm zorunlu kalite kapılarını geçen üretimleri yayın kuyruğuna al.
- [ ] Günlük kota, kanal/hesap, concurrency ve idempotency kontrollerini bağla.
- [ ] Uploader sonucunu Studio'da doğrula.
- [ ] Belirsiz upload sonucunda ikinci upload'ı engelle.
- [ ] Video ID, URL, tarih, görünürlük ve generation_id'yi kalıcı kaydet.
- [ ] Gerçek kontrollü CI/Studio yayın kanıtını ekle.

**Kabul kapısı:** Uçtan uca yayın bir kez gerçekleşiyor ve doğru durum doğrulanıyor.

## Faz 10 — Analytics ve öğrenme

- [ ] Kullanılabilir Analytics veri alanlarını ve erişim yolunu doğrula.
- [ ] İzleyici tutma, izlenme süresi ve etkileşim verilerini toplulaştır.
- [ ] Az örneklemden aşırı çıkarımı önle.
- [ ] Kategori çeşitliliği ve tekrar korumasını öğrenme döngüsünde koru.
- [ ] Analitik geri beslemesini kapatılabilir ve denetlenebilir yap.
- [ ] Önce/sonra performans raporu üret.

**Kabul kapısı:** Geri besleme kontrollü; veri kaynağı ve etkisi izlenebilir.

## Her faz için zorunlu teslim kontrolü

- [ ] Değişen dosyalar ve gerekçeleri kaydedildi.
- [ ] İlgili birim testleri geçti.
- [ ] Entegrasyon/CI sonucu kaydedildi.
- [ ] Canlı doğrulama gerekiyorsa gerçek kanıt eklendi.
- [ ] README, ARCHITECTURE, AI_HANDOFF ve bu TODO güncellendi.
- [ ] Secret taraması ve artifact sanitizasyonu yapıldı.
- [ ] Commit SHA ve GitHub bağlantısı eklendi.
- [ ] Açık riskler ve sonraki adım yazıldı.

## İlerleme kaydı

| Tarih | Faz | Commit / CI kanıtı | Sonuç | Açık konu |
|---|---|---|---|---|
| 2026-11-17 | Dokümantasyon | dd0a8f1 / 956a03b / f8ec3aa | Plan, TODO ve README bağlantıları eklendi | Faz 0 |
| 2026-11-17 | Faz 0 baseline | 0e2ecc9 / b4a9b29; test run 44076814790 + 44160916391 (114 passed, 8 subtests); production run 44119590041 | GitHub HEAD, daily/pruner/draft workflow'ları, AI_HANDOFF ve ana akış incelendi; CI'da 108 test geçti; gerçek PUBLIC üretim logu kaydedildi | Secret isimleri connector üzerinden doğrulanamıyor; yeni thumbnail CI sonucu bekleniyor |
| 2026-11-17 | Faz 0 doküman ve test takviyesi | fc7ea77 / 8ca1fb9 / b693e80 / 25b7ac8 / 3794cac | Mimari/kurulum/devir belgeleri uzlaştırıldı; thumbnail yardımcı testleri CI'da 114 passed + 8 subtests; kullanıcı mevcut secret'ları korumayı seçti, hiçbir secret değiştirilmedi | Faz 1 JSON envanteri ve şema; cookie/API legacy ayrımı ayrıca doğrulanacak |
| 2026-11-17 | Faz 1 sözleşme envanteri | 9f34cea | script.json üretici, doğrulanmış tüketiciler, örnek farkları ve geriye uyumluluk alanları belgelendi | Ek tüketici taraması, JSON Schema ve CI testleri |
| 2026-11-17 | Faz 1 JSON Schema v2 + runtime kapısı | 4de73ba / 306fab3 / 408d561 / 4ae59a6 / 94369e2 / 68b4a9c; CI 44164802326 | Legacy v1 + current v2, generation_id, runtime validator; 123 passed + 8 subtests | Ek JSON tüketicileri taraması ve gerçek media tüketici entegrasyon testi |
| 2026-11-17 | Faz 2 Gemini Web dry-run altyapısı | eb960af / a0a6353 / 03418ed; CI 44171572008 | Cookie parser uyumluluğu düzeltildi; `__Secure-1PSIDTS` opsiyonel; 131 passed + 8 subtests; dry-run bağımlılığı 2.1.1'e sabitlendi | Gerçek cookie oturumuyla metin/JSON üretimi hâlâ manuel workflow çalıştırmasına bağlı; PUBLIC yayın yok |
| 2026-11-18 | Gemini Web main pipeline entegrasyonu | Feature `075183d`, docs `0cbe608`/`8fb0856` push edildi; Ubuntu 26 CI [44200069203](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44200069203) **success** (önceki test seti). Seçili yeni suite **30 passed + 4 subtests**; geniş pytest collection `edge_tts`/`google` eksikliğiyle durdu | main route, workflow cookie env, schema-v2 kaynak/fact_check/storyboard ve fallback; kullanıcı `partial` taslağa PUBLIC hattı onayı verdi | İlk iki probe Python `ValueError` (secret-missing değildi); alt neden güvenli loglamada saklı. Sonraki probe 44262444017 başarılı; live artifact/schema/secret taraması aşağıda |
| 2026-11-18 | Faz 2 live cookie dry-run + secret-context teşhisi | Diagnostic workflow commit `57166f8`; Actions [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017) **success** | `GEMINI_COOK_CONTEXT_PRESENT=true`; provider `gemini-web-session`; 58 kelimelik Türkçe taslak, 1 Wikipedia source, 3 claim, 5 scene; ham model yanıtı response schema'dan geçti; `text_probe_result.json` artifact taraması temiz; `draft_only=true`, `publish=false` | Bu tarih kaydında semantic entailment ve kalıcı ledger açık durumdaydı; 2026-11-18 Faz 3 implementation satırı için aşağıya bakın. Canlı timeout/expired/rate-limit ayrıca test edilmedi |
| 2026-11-18 | Gemini Faz 3 ilk yerel snapshot (tarihsel) | Targeted Phase 3 tests 35 passed; content-engine fallback + Phase 3 selection 40 passed; real Wikipedia HTTP `Venus` 200 + canonical identity match | Deterministic semantic relation and number/unit checks, v2 state enum compatibility, source HTTP/page identity validation, legacy `.used_topics.json` migration, topic/claim/scenario fingerprint CAS reservation, 30m TTL, failure release, SHA retry; added publish-free Ubuntu CI path and two-run persistence probe workflow | Bu ilk yerel snapshot sırasında CI ve iki-run proof bekleniyordu; kod henüz push edilmemişti. Tarihsel kayıt: güncel kabul bir sonraki satırdadır; production/pruner/publisher tetiklenmedi |
| 2026-11-18 | Gemini Faz 3 yayınsız kabul | Feature `c2729cc`; ortam düzeltmeleri `28e1d6e` / `0dee88e`; CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329); reserve [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395); verify [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) | Yeni kodda 171 test + 16 subtest, ayrı 35 hedefli test; gerçek iki-run SHA-CAS reservation/read/release, legacy 25 başlık korundu; credential/log taraması temiz | Faz 3 kabul geçti. Daily canlı finalize/yayın ve CAS race yapılmadı; Faz 4 medya uyumu/lisans/zamanlama ile açık Faz 1 entegrasyon işleri korunur |
