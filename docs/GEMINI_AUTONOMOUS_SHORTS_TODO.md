# Gemini Tabanlı Otonom Shorts — Canlı TODO

> Bu dosya uygulamanın tekil takip listesidir. Bir kutu yalnız ilgili kod/test/CI veya canlı kanıt elde edilince işaretlenir. Mimari: [GEMINI_AUTONOMOUS_SHORTS_PLAN.md](GEMINI_AUTONOMOUS_SHORTS_PLAN.md).

## Durum özeti

- [x] Mimari plan ve TODO GitHub'a dokümantasyon olarak eklendi.
- [x] Kod entegrasyonu başladı: JSON v2 metadata ve üretim öncesi fail-closed doğrulama kapısı eklendi; Faz 1 kabulü henüz tamamlanmadı.
- [x] Faz 0 başlangıç incelemesi, doküman uzlaştırması ve güncel test baseline tamamlandı; secret metadata ad envanteri connector kısıtı ve kullanıcının secret'ları koruma kararı nedeniyle istisna olarak kapatıldı. Hiçbir secret değiştirilmedi.
- [x] `main.py` içerik motorunu `--gemini-web-only` ile çağırır; `daily_shorts.yml` `GEMINI_COOK` secret'ını process env'e verir. Cookie/schema/source kontrolü başarısızsa mevcut yerel fallback kullanılır ve ücretli text API'ye geçilmez. Gerçek oturum/CI kanıtı açık.
- [x] `script.json` v2'ye Gemini `sources`, `fact_check`, `storyboard`, `claims` ve prompt sürümü taşınır; medya işlemcisi `storyboard[].visual_query` değerlerini tercih eder. Sahne-süre hizası/QC ve semantik doğrulama açık.
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
- [ ] Önce yayın yapmayan dry-run ile cookie oturumunun metin/JSON üretebildiğini doğrula; mevcut kanıt yalnız kapak görseli üretimini kapsıyor.
- [ ] Cookie oturumunun geçerlilik, timeout, rate limit ve oturum yenileme davranışlarını test et.
- [x] Versiyonlu prompt dosyası ve ayrı Gemini Web yanıt şeması ekle; konu/kaynak, senaryo, storyboard, arama ve kapak alanlarını tanımla (`prompts/gemini_web_story_v1.md`, `schemas/gemini_story_response.schema.json`). Yerel/mocked testler geçti; gerçek cookie yanıtı alınmadı.
- [x] Son 25 kalıcı başlığı (`.used_topics.json`) ve yerel topic-ledger kimliklerini prompta ekle; başlıkta seed konusu eşleşirse konuyu dışla. Atomik ledger rezervasyonu aynı paylaşılan filesystem içindeki işleri korur; ayrı Actions run'ları arası ledger kalıcılığı yoktur. Daily workflow'un mevcut `.used_topics.json` commit adımı başlık geçmişini kalıcılaştırır.
- [ ] JSON Schema doğrulamasını gerçek cookie yanıtına uygula.
- [x] Cookie/oturum/draft hatasında mevcut fallback'e dön; `gemini_web_only` dalında Groq/Gemini API sağlayıcılarının çağrılmadığını test et (`tests/test_gemini_web_content_engine.py`).
- [x] Yeni metin üretim adaptörünün `GEMINI_API_KEY` istemediğini test et; web-only dalı bu anahtarı okumaz ve testte API sağlayıcıları çağrılmadı.
- [ ] Yayın yapmayan dry-run kanıtını gizli bilgi içermeden kaydet.

**Kabul kapısı:** Cookie ile gerçek ve geçerli JSON yanıtı; API key kullanılmıyor; PUBLIC yayın yok. Mevcut legacy kare analiz API yolu kullanıcı onayı olmadan değiştirilmez.

## Faz 3 — Kaynak doğrulama ve tekrar koruması

- [x] Dry-run sözleşmesinde Wikipedia HTTP yanıtından alınacak sayfanın adı/URL/erişim zamanı ile kaynak metninden birebir alıntı ve senaryo alıntısı alanlarını bağla; validator alıntıların tam eşleşmesini şart koşuyor (`scripts/gemini_web_story.py`). Adapter yalnız mock ağ testleriyle doğrulandı; bu oturumda gerçek HTTP isteği yapılmadı. Bu yalnızca alıntı-eşleşme kontrolüdür, semantik entailment doğrulaması değildir.
- [x] Paylaşılan aynı dosya sistemindeki eşzamanlı işler için `flock` + atomik dosya değiştirme ile konu rezervasyonu/commit/release ekle; çok-thread testinde aynı konunun çift rezervasyonu engelleniyor. GitHub Actions koşuları arası kalıcı state entegrasyonu ayrıca açık.
- [x] `script.json` v2'de Gemini kaynak adı/URL/erişim zamanı, fact-check iddiaları/kaynak ID'leri ve storyboard taşınır; lokal runtime-schema testinde doğrulandı. Bu paket `partial` semantik statüsünü açıkça taşır; bağımsız entailment doğrulaması hâlâ açık.
- [ ] Kaynak erişilebilirliğini ve iddiayla ilişkisini doğrula.
- [ ] Tarih/sayı/ölçü gibi kritik iddiaları kaynak metniyle karşılaştır.
- [ ] Doğrulanamayan iddiayı çıkar veya konuyu yeniden seç.
- [x] Başlık geçmişi yöntemi `.used_topics.json` + daily workflow GitHub Contents API commit adımıdır; Gemini promptuna son 25 başlık ekleniyor. Yalnızca başlık-temelli yaklaşım ana iddia/varlık benzerliği için yeterli değil.
- [ ] Konu, ana iddia, varlık ve normalize metin üzerinden tekrar kontrolü oluştur.
- [ ] Paralel koşular için atomik rezervasyon/lock/idempotency uygula.
- [ ] Geçmiş okunamıyor veya benzerlik belirsizse güvenli durdurmayı test et.

**Kabul kapısı:** Kaynaksız iddia ve tekrar konu yayın kapısından geçemiyor; paralel üretim aynı konuyu rezerve edemiyor.

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
| 2026-11-18 | Gemini Web main pipeline entegrasyonu | Yerel değişiklikler; push öncesi. pytest **140 passed, 3 skipped, 12 subtests**; npm **7 passed**; Python compile, CLI, JSON/YAML parse ve diff-check başarılı | `main.py --gemini-web-only`, günlük workflow `GEMINI_COOK` aktarımı, v2 kaynak/fact_check/storyboard payload'u, storyboard query tüketimi ve cookie hata fallback'i eklendi. Kullanıcı `partial` fact-check taslağının mevcut PUBLIC hattında devam etmesine izin verdi. | Gerçek cookie/CI/HTTP/PUBLIC koşusu yok; semantik entailment, Actions koşuları arası topic ledger ve tam scene-media QC açık |
