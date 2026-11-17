# Gemini Tabanlı Otonom Shorts Üretimi — Mimari ve Uygulama Planı

> Durum: **Planlama / henüz uygulanmadı**  
> Kapsam: Mevcut YouTube Shorts otomasyonunu Gemini destekli, sahne bazlı ve kalite kapılı içerik üretimine geçirmek.  
> Kural: Bu belge planı tanımlar. Bir iş ancak kod, test ve gerekli doğrulama kanıtı varsa tamamlandı sayılır.

## 1. Amaç ve başarı ölçütü

Her çalıştırmada insan konu seçmeden yeni bir bilgilendirici konu seçilmeli; güvenilir kaynaklarla araştırılmalı; Türkçe senaryo, yayın metadatası ve sahne storyboard'u hazırlanmalı; her sahneye uygun medya bulunmalı; ses, altyazı ve görüntü senkronize edilerek dikey video üretilmeli; kalite kapılarını geçmeyen video yayınlanmamalıdır.

Başarı yalnızca MP4 üretmek değildir. İçerik yeni ve doğrulanabilir olmalı; kaynaklar gerçek olmalı; sahne görüntüleri anlatımla uyuşmalı; lisans/atıf bilgisi korunmalı; ses ve altyazı senkronu doğru olmalı; video teknik kontrolleri geçmeli; YouTube yükleme sonucu doğru video kimliği üzerinden doğrulanmalıdır.

## 2. Mevcut depoda doğrulanan başlangıç noktası

| Dosya | Şu anki rol | Doğrulanan bulgu |
|---|---|---|
| main.py | Ana orkestrasyon | content_engine.py şu anda --force-fallback argümanıyla çağrılıyor; ana akışta LLM üretimi bu nedenle atlanıyor. |
| content_engine.py | Konu/senaryo, seslendirme ve script.json | Hazır senaryo havuzu, LLM prompt/sağlayıcı yolları ve visual_keywords alanı var. |
| src/media_processing/media_processor.py | Medya bulma, altyazı ve FFmpeg montajı | script.json içindeki genel visual_keywords listesini okuyor; storyboard henüz ana medya sözleşmesi değil. |
| video_fetcher.js | Tarayıcı tabanlı stok medya araması | Pixabay/Pexels arama akışında kullanılıyor. |
| youtube_studio_uploader.js | YouTube Studio yükleme | Mevcut yükleyici korunmalı; yayın sonucu bağımsız doğrulanmalı. |
| tests/ | Birim/entegrasyon testleri | Medya ve fallback testleri var; Gemini JSON sözleşmesi ve sahne eşleştirme testleri eklenmeli. |
| .github/workflows/daily_shorts.yml | CI üretim/yayın akışı | Tetikleyici, kanal, concurrency ve yayın davranışı değişiklik öncesi yeniden denetlenmeli. |

**Önemli:** README, AI_HANDOFF ve eski faz belgelerinde farklı tarihlerden kalmış durum açıklamaları var. Bunların tümü güncel kabul edilmeyecek. Uygulama öncesinde aktif branch, workflow ve son gerçek CI koşusu tek başlangıç kaydında doğrulanacak.

## 3. Hedef mimari

1. GitHub Actions mevcut tetikleyicisi çalışır.
2. main.py üretim kimliği ve kilit/tekrar kontrolünü başlatır.
3. Gemini ücretsiz erişim ve kota doğrulandıysa konu, araştırma, senaryo ve storyboard üretir.
4. JSON şeması, kaynak ve tekrar doğrulaması yapılır.
5. Türkçe TTS seslendirme ve gerçek kelime zamanlarını üretir.
6. Medya motoru her storyboard sahnesi için ayrı medya arar.
7. Sahne-medya uygunluğu, lisans ve atıf kontrol edilir.
8. FFmpeg sahneleri seslendirme ve altyazıyla birleştirir.
9. Teknik ve içerik kalite kapıları çalışır.
10. Yalnız tüm zorunlu kapıları geçen video YouTube yükleyiciye verilir.
11. Studio sonucu video ID'si üzerinden doğrulanır.
12. Sonuç ve performans verisi kalıcı geçmişe yazılır.

## 4. Tasarım kararları

### 4.1 Sağlayıcı ve maliyet
- Kullanıcının tercih ettiği birincil yol Gemini Web oturumudur; mevcut `GEMINI_COOK` cookie secret'ı korunur ve değeri hiçbir zaman loglanmaz/çıktılanmaz.
- Depoda doğrulanan mevcut cookie kullanımı `scripts/gemini_cover.py` üzerinden `gemini_webapi` ile kapak görseli üretimidir; `backfill_short_thumbnails.yml` bu secret'ı `jeton/gemini_cookies.json` dosyasına aktarır. Bu, metin/storyboard üretiminin cookie ile çalıştığını henüz kanıtlamaz.
- Faz 2, önce aynı cookie oturumuyla metin/JSON üretiminin mümkün olup olmadığını yayın yapmayan testte doğrular. Çalışmazsa ücretli API'ye otomatik geçiş yapılmaz; kullanıcıya seçenek sunulur.
- `GEMINI_API_KEY` mevcut secret olarak kullanıcı kararıyla olduğu gibi bırakılır; yeni metin/storyboard tasarımı bu anahtara bağımlı olmayacaktır.
- **Mevcut legacy istisna:** `daily_shorts.yml` `GEMINI_API_KEY` ve `GEMINI_FREE_VISION_ENABLED` değerlerini `generate_fallback_thumbnail.py` / `gemini_frame_selector.py` yoluna aktarır. Bu, yalnız mevcut kareleri analiz eden ayrı bir API yoludur; repository variable'ın anlık değeri bu bağlantıyla doğrulanamadı. Kullanıcı onayı olmadan mevcut üretim davranışı değiştirilmez.
- Ücretli API, ücretli görsel/video üretimi veya billing açılması yeni mimarinin parçası değildir. Cookie oturumu bozulursa sistem ücretli API'ye sessizce düşmez; güvenli yedek veya durdurma uygulanır.

### 4.2 Araştırma ve doğruluk
- Gemini'nin ürettiği kaynak adı/URL'si tek başına kanıt değildir.
- Kaynak erişilebilirliği ve içerikle ilişkisi kontrol edilir; kritik tarih/sayı/ölçü iddiaları kaynak metniyle karşılaştırılır.
- Doğrulanamayan iddia çıkarılır veya konu değiştirilir.
- Kaynak doğrulama başarısızsa video yayın kuyruğuna ilerlemez.
- Bilimsel belirsizlik, tahmin ve canlandırma açıkça belirtilir.

### 4.3 Tekrar önleme ve kalıcı durum
- GitHub Actions çalışma alanındaki geçici JSON dosyası kalıcı geçmiş sayılmaz.
- SQLite tek başına CI koşuları arasında kalıcı değildir; kullanılacaksa güvenli kalıcı depolama/restore yöntemi ayrıca tasarlanır.
- Artifact/cache tek başına transaction garantili veritabanı değildir. Depolama seçimi çakışma ve eşzamanlı çalışma testleriyle yapılır.
- Tekrar kontrolü yalnız başlığa değil; normalize konuya, ana iddialara, varlıklara ve içerik özetine bakar.
- Geçmiş okunamazsa veya tekrar kararı belirsizse sistem durur.
- Paralel workflow'ların aynı konuyu seçmesini önlemek için atomik rezervasyon/lock ve idempotency gerekir.

### 4.4 Sahne bazlı medya
- Her sahnenin ayrı arama terimleri, medya türü, hedef süresi ve anlatım bölümü olur.
- Pixabay/Pexels/Wikimedia adaptörleri ortak bir medya sağlayıcı arayüzü arkasında birleştirilir.
- Adaylar konu uyumu, lisans, süre, çözünürlük, oran ve indirme başarısına göre değerlendirilir.
- Önce alternatif arama terimleri denenir; uygun görüntü yoksa alakasız klip kullanılmaz.
- Temsili canlandırma gerçek arşiv görüntüsü gibi sunulmaz. Yedek sahne üretilemiyorsa iş durur.
- Aynı klibin video içinde ve yakın dönem videolarda tekrarı azaltılır.

### 4.5 Ses, storyboard ve zamanlama
- TTS'nin gerçek kelime zamanları esas alınır; sahne sınırları bu zaman çizelgesine hizalanır.
- Storyboard tahmini süreleri sesin gerçek süresinin yerine geçmez.
- Metin hedef süreye sığmıyorsa metin kısaltılır veya yapılandırılmış süre kullanılır.
- Altyazı okunabilirliği, güvenli alan, taşma, karakter kodlaması ve senkron ayrı test edilir.

### 4.6 Yayın öncesi kalite kapısı
Zorunlu kontroller:
1. JSON ve veri sözleşmesi geçerli.
2. Temel iddialar ve kaynaklar doğrulanmış.
3. Tekrar kontrolü geçmiş.
4. Her sahne için kabul edilebilir medya veya açıkça işaretlenmiş onaylı temsili sahne var.
5. Lisans/atıf metaverisi saklanmış.
6. Ses dosyası okunabilir ve süresi uygun.
7. MP4 ffprobe ile doğrulanmış; 9:16, çözünürlük, FPS, codec ve ses akışı doğru.
8. Siyah/boş kare, eksik sahne, aşırı sessizlik, ses-görüntü senkronu ve altyazı kontrolleri geçmiş.
9. Başlık, açıklama, kapak ve sentetik içerik beyanı tutarlı.
10. Günlük kota, kanal ve yayın kilidi uygun.

Kritik kontrol başarısızsa yayın yapılmaz. Upload zaman aşımında önce Studio'da aynı üretimin sonucu aranır; körlemesine ikinci upload yapılmaz.

## 5. Önerilen veri sözleşmesi

Yeni alanlar eklenirken mevcut tüketiciler kırılmamalı. Önce geriye uyumlu schema_version eklenmeli, ardından tüketiciler kademeli geçirilmelidir.

| Alan | Tür | Açıklama |
|---|---|---|
| schema_version | string | Örn. 2.0; sözleşme sürümü |
| topic, category | string | Konu ve kategori |
| title, description | string | YouTube metadata |
| hook, script_text, cta_line | string | Türkçe anlatım |
| thumbnail_prompt, thumbnail_text | string | Kapak talimatı ve metni |
| viral_hashtags | string[] | Konuyla ilgili etiketler |
| fact_check | object | İddialar, kaynaklar, durum ve belirsizlik |
| storyboard | object[] | Sahne bazlı zaman, anlatım, görsel ve arama talimatları |
| visual_keywords | string[] | Eski medya motoru için geçici geriye uyum alanı |
| provider, model | string | Gerçekte kullanılan sağlayıcı/model; sır içermez |
| generation_id | string | Tek üretim için idempotency kimliği |

Storyboard sahnesi için hedef alanlar: scene_number, voiceover_segment, visual_description, search_queries, media_type, target_duration_seconds, on_screen_text, animation, camera ve sound_effect. Zorunlu alanlar JSON Schema ile tanımlanmalıdır.

Bu tablo hedef sözleşmedir; mevcut script.json şeması değildir. Nihai şema, gerçek TTS zaman damgaları ve medya tüketicileri incelendikten sonra sabitlenir.

## 6. Fazlara ayrılmış uygulama planı

### Faz 0 — Başlangıç envanteri ve emniyet
- Aktif branch, commit, workflow tetikleyicileri, secret isimleri (değerleri değil), test komutları ve son CI sonuçlarını kaydet.
- README, AI_HANDOFF, ARCHITECTURE ve eski TODO belgelerindeki çelişkileri işaretle; tarihsel kayıtları silmeden güncel bağlantılar ekle.
- Mevcut üretim/yayın hattını değiştirmeden baseline test ve örnek artifact kanıtı al.
- Pruner, cron/watchdog, kanal, günlük kota ve PUBLIC davranışını koruma listesine al.

**Kabul:** Başlangıç commit'i ve test sonuçları kaydedilmiş; yayın yapmayan doğrulama koşusu çalıştırılabilir.

### Faz 1 — Sözleşme ve test temeli
- script.json alanlarını ve tüm okuyucuları çıkar.
- JSON Schema ve versiyonlama ekle.
- Bozuk/eksik JSON, yanlış tip, eksik sahne ve geçersiz kaynak testleri yaz.
- Fallback'in hangi koşulda çalışabileceğini tanımla.

**Kabul:** Eski örnekler geriye uyum testinden geçer; hatalı veri yayın aşamasından önce reddedilir.

### Faz 2 — Gemini Web cookie adaptörü ve prompt
- `GEMINI_COOK` secret'ının yalnız adı/varlığı kullanıcı tarafından doğrulanır; değer hiçbir loga veya artifact'e yazılmaz.
- Mevcut `gemini_webapi` istemcisi ve cookie yenileme/sona erme davranışı incelenir.
- Yayın yapmayan dry-run ile cookie oturumunun metin ve JSON yanıtı üretebildiği doğrulanır; şu an doğrulanmış kullanım yalnız kapak görselidir.
- Yanıt JSON Schema ile doğrulanır; bozuk yanıt, oturum düşmesi, rate limit ve timeout için sınırlı retry/backoff uygulanır.
- Cookie geçersizse ücretli API'ye geçiş yapılmaz; iş güvenli biçimde durur veya onaylı fallback kullanılır.
- Mevcut `GEMINI_API_KEY` kare analiz yoluna kullanıcı onayı olmadan müdahale edilmez; yeni içerik üretim adaptörü API key istemez.

**Kabul:** Cookie oturumuyla gerçek metin/storyboard yanıtı geçerli şemada doğrulanır; API key kullanılmaz; PUBLIC yayın yapılmaz.

### Faz 3 — Araştırma ve tekrar koruması
- Kaynak fetch/parse/iddia eşleştirme katmanı.
- Kalıcı geçmiş ve eşzamanlı üretim rezervasyonu.
- Konu/iddia/varlık benzerliği ve güvenli durdurma.

**Kabul:** Tekrar, kaynak bozulması, geçmiş erişim hatası ve paralel workflow testleri geçer.

### Faz 4 — Sahne bazlı medya adaptörü
- Mevcut sağlayıcı fonksiyonlarını ortak arayüze al.
- Sahne başına sorgu ve aday değerlendirmesi.
- Lisans/atıf metaverisini sahneyle birlikte sakla.
- Uygun medya bulunmadığında retry ve fail-closed davranışı.

**Kabul:** Sahne-medya eşleşmesi, lisans kaydı ve durdurma davranışı doğrulanır.

### Faz 5 — TTS ve montaj
- Sahne sınırlarını gerçek TTS word timestamps ile hizala.
- Sahne başına FFmpeg trim/scale/concat uygula.
- Altyazı, ses, müzik, güvenli alan ve toplam süre doğrulaması.
- Mevcut montajla performans/bellek karşılaştırması.

**Kabul:** Örnek videoda sahne sırası, ses/altyazı senkronu ve teknik video kontrolleri geçer.

### Faz 6 — Görsel/işitsel kalite denetimi
- İlk sürümde metadata/arama terimi tabanlı görsel alaka kontrolleri; daha sonra yalnız maliyetsizliği doğrulanmış analiz seçeneği.
- Siyah kare, boş medya, tekrar, çözünürlük, ses clipping/sessizlik ve altyazı taşması kontrolleri.
- Her kontrol için kanıt ve hata kodu.

**Kabul:** Bilerek bozuk/alakasız örnekler yayın kapısında reddedilir.

### Faz 7 — Kapak ve metadata
- Yalnız ücretsizliği ve lisansı uygun mevcut kapak yolu kullanılabilir.
- Türkçe kapak metni, konu uyumu, okunabilirlik ve oran kontrolü.
- Başlık/açıklama/hashtag/CTA/kaynak tutarlılığı.
- Sentetik/temsili sahne için YouTube beyanı kontrolü.

**Kabul:** Kapak ve metadata içerikle tutarlı; ücretli servis çağrısı yok.

### Faz 8 — Gölge mod ve taslak pilotu
- Yeni üretim hattı PUBLIC yayın kapalı olarak workflow'a bağlanır.
- Gerçek CI artifact'ı incelenir.
- Tek video pilotunda doğru video ID, görünürlük, başlık, kapak ve tekrar upload koruması doğrulanır.
- Hata halinde güvenli durdurma.

**Kabul:** Kontrollü pilot doğrulanır; kullanıcı kararı olmadan yayın politikası değiştirilmez.

### Faz 9 — Kontrollü otomatik yayın
- Yalnız tüm kalite kapılarını geçen üretimler yayın kuyruğuna girer.
- Günlük kota, kanal kilidi, idempotency ve yükleme sonucu kontrol edilir.
- Belirsiz upload sonucunda önce Studio kontrol edilir; ikinci upload yapılmaz.
- Sonuç video ID'siyle kalıcı kayda yazılır.

**Kabul:** Gerçek yayın ve Studio görünürlük doğrulaması; yinelenen upload yok.

### Faz 10 — Analitik geri besleme
- Analytics alanları ve veri kaynağı doğrulanır.
- İzleyici tutma, izlenme süresi ve etkileşimden toplu sinyal çıkarılır.
- Tek videodan aşırı öğrenme yapılmaz; kategori dengesi korunur.

**Kabul:** Analitik verisi konu seçimine kontrollü ve kapatılabilir biçimde girer.

## 7. Hata politikası

| Hata | Davranış |
|---|---|
| Gemini timeout / 429 / 5xx | Sınırlı exponential backoff; limit aşılırsa durdur |
| JSON bozuk / şema dışı | Sınırlı düzeltme isteği; hâlâ hatalıysa durdur |
| Kaynak erişilemiyor / iddia doğrulanamıyor | Alternatif kaynak/konu; kanıt yoksa yayın yok |
| Tekrar şüphesi | Geçmişi yenile; belirsizlikte durdur |
| Medya bulunamadı | Sorgu varyasyonu; onaylı temsilî sahne yoksa durdur |
| Lisans/atıf eksik | Medyayı reddet |
| TTS/FFmpeg başarısız | Sınırlı retry; video yayın yok |
| Kalite kapısı başarısız | Çıktıyı karantinaya al |
| Upload timeout / belirsiz sonuç | Studio'da aynı üretimi ara; körlemesine tekrar yükleme yok |
| Günlük kota dolu | Güvenli beklet; kotayı aşmaya çalışma |

## 8. Güvenlik, telif ve operasyon

- Public repo'ya token, cookie, storage state, HAR, .env veya özel Studio/Analytics verisi eklenmez.
- Log/artifact sanitizasyonu ve secret taraması korunur.
- Pixabay/Pexels/Wikimedia kullanım koşulları ve atıf zorunlulukları uygulanır; indirilebilir olmak telifsiz olduğu anlamına gelmez.
- Gerçekçi canlandırmalar arşiv görüntüsü gibi sunulmaz; YouTube sentetik içerik açıklaması değerlendirilir.
- Pruner/silme, kanal temizliği veya mevcut videolara toplu müdahale bu yeni üretim kapsamına dahil değildir.
- Cron/watchdog, kanal/matrix, PUBLIC ve pruner davranışı inceleme/test olmadan değiştirilmez.
- Her faz küçük commit'lerle ilerler; değişen dosyalar, test sonucu, CI run ve açık riskler kaydedilir.

## 9. Her fazın teslim standardı

Her faz kaydı: tarih, başlangıç commit'i, değişen dosyalar, tasarım kararı, test komutları/sonuçları, CI run bağlantısı, canlı doğrulama kanıtı, açık riskler ve sonraki faz.

Bir özellik yalnızca kodlandı diye tamamlandı sayılmaz. Test ve gerekli canlı kanıt olmadan TODO'da tamamlandı işaretlenmez.

## 10. Resmî başvuru noktaları

- Gemini API: https://ai.google.dev/gemini-api/docs
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- YouTube API: https://developers.google.com/youtube/v3
- YouTube sentetik/değiştirilmiş içerik: https://support.google.com/youtube/answer/14328491
- Pixabay lisans: https://pixabay.com/service/license-summary/
- Pexels API şartları: https://www.pexels.com/api/terms-of-service/
- Wikimedia Commons reuse: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia

---

**Güncel uygulama durumu:** Gemini → storyboard → sahne bazlı medya → kalite kapısı entegrasyonu henüz uygulanmış kabul edilmez. İlerleme [uygulama TODO'su](GEMINI_AUTONOMOUS_SHORTS_TODO.md) üzerinden izlenir.
