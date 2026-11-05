# Faz 14 — Ücretsiz Gemini ile kapak karesi ve güvenli yedek

Kullanıcı ücretli API kullanımını reddetti. AI Studio projesi gözlemde Free tier; `GEMINI_API_KEY` GitHub Actions secret'ı mevcut. Anahtarın değeri repo, log, artifact veya Drive'a yazılmaz.

## TODO

- [x] AI Studio aynı hesapla açıldı; kullanıcı Google koşullarını onayladı ve projeyi kendisi oluşturdu. Google görsel üretim modelleri resmi fiyat listesinde ücretsiz değil; ücretli üretim yapılmayacak.
- [x] Yayın yapmayan gerçek CI #4 (`41988709577`): `gemini-3.1-flash-lite` text ve görsel-anlama yanıtı başarılı. Gerçek Zanzibar video kapağını konu dışı görüp reddetti; `LOCAL_FALLBACK_OK`. Ücretli image-generation çağrılmadı.
- [x] Aday kare incelemesi `scripts/gemini_frame_selector.py` (text/vision endpoint, bir istek, güven eşiği) eklendi. Gerçek Gemini yanıtı bir örnekte doğrulandı; genelleştirilmiş doğruluk garantisi değildir.
- [x] Hata/kota/zaman aşımı/düşük güvende yerel temsili kapak yolu eklendi; Zanzibar gerçek videosunda anahtar kapalıyken 1080×1920 JPEG doğrulandı. Temsili ikon tarihsel doğrulama veya gerçek görsel değildir. Modelin konu uygunluğu ve Studio kapağı ayrıca doğrulanmalıdır.
- [x] Secret, yayın işine enjekte edildi; `GEMINI_FREE_VISION_ENABLED` repo variable varsayılanı 0; gerçek API testi sonrasında bu repo için 1 olarak açıldı. Kare değerlendirmesi bir istekle sınırlıdır; ücretli görsel üretim endpointine istek göndermez. Ücretli billing bağlanırsa bu anahtarın text API kullanımı da ücretlenebilir: değişkeni 0 yapın.
- [ ] Otomatik workflow, pruner ve PUBLIC görünürlük kuralları korunmalı; kullanıcı istemeden mevcut yayınlar düzenlenmemeli ve AI video tüm sisteme bağlanmamalı.
- [ ] Gözlemleri/tüm sınırlamaları belgeleyip GitHub ve Drive'a yedekle; gerçek canlı yayın denemesi ayrıca izin ve kanıt gerektirir.

## Doğrulanmış sınırlamalar

Google fiyat sayfasında Gemini 3.1 Flash Lite Image ve Nano Banana 2.1 için ücretsiz API katmanı yoktur. Gemini'nin ücretsiz metin/görsel-anlama modeli, görsel dosyası ÜRETMEZ. Google projesine sonradan faturalandırma bağlanırsa model kullanım ücretleri değişebilir; her koşuda yalnız API anahtarıyla proje fatura durumunu bağımsız doğrulamak mümkün değildir. Mevcut projenin Free tier durumu 5 Kasım 2026'da AI Studio'da gözlemlenmiştir.

## Uygulama sınırı

Yerel yedek `--strict-subject` ile rastgele kontrast karesi yerine uygunluk doğrulanamazsa açıkça **temsili görsel** içeren metin kartına düşer; eski standalone kullanımda `--strict-subject` yoksa kontrastlı kare seçimi geriye dönük korunur. Dış servis HTTP 402 ise beklemeden yedeğe geçilir. Bu yöntem Google ile sıfırdan görsel üretmez; uygunluk, tıklanma ve yayınlanan Studio kapağı garantisi vermez. Gerçek Gemini testi [yayın yapmayan manuel workflow](../.github/workflows/free_gemini_probe.yml) ile yapıldı.

İlk gerçek test #1 (run `41988326325`, commit `f007d7a`): gerçek herkese açık video görseli alındı; Gemini text/vision çağrısı HTTP 404 döndürdü. Bu nedenle üretimde Gemini değişkeni aktif edilmedi. Hesabın model listesi gerçek API ile ayrıca kontrol ediliyor; HTTP 404 nedeni henüz doğrulanmadı.

İkinci canlı CI (`41988450201`): anahtar ile model listesi başarıyla okundu ve `gemini-2.5-flash-lite` listede var; generateContent yine HTTP 404. Ücretli görsel API denenmedi. Yerel yedek CI içinde 1080x1920 doğrulandı. HTTP 404 nedeni belirsiz; farklı ücretsiz text modelleri ile teşhis eklendi.

Üçüncü gerçek CI (`41988589391`): 2.5 Flash metin HTTP 404, `gemini-3.1-flash-lite` text isteği HTTP 200 ve gerçek aday döndürdü. Görsel-anlama uygulaması bu ücretsiz text modeline taşındı; dördüncü işte görsel-anlama testi yapıldı.

Ücretsiz görsel-anlama etkinse yayın kodu önce mevcut video karelerini Gemini ile değerlendirir; uygun kare yoksa temsili yerel kapak üretir. Gemini kapalıysa eski harici üretici denenir, hata/HTTP 402 durumunda yerel yedeğe geçilir. `FORCE_LOCAL_THUMBNAIL=1` Gemini dahil AI çağrılarını devre dışı bırakır. Bir görsel kaynağının DOM varlığı Studio kapak yükleme başarısı sayılmıyor; görünür önizleme farkı gerekir. **Yeni bir video için Studio üzerinde kapak yükleme ve görüntülenme henüz test edilmedi.**

## Etkinleştirme, 5 Kasım 2026

GitHub Actions repository variable `GEMINI_FREE_VISION_ENABLED=1` olarak ayarlandı ve API ile okundu; workflow varsayılanı yokluğunda 0 olarak kalır. Dayanak: kullanıcı tarafından oluşturulan anahtarın Free tier projesine ait olduğu beyanı ve AI Studio proje gözlemi. API key ile faturalandırma durumu her koşu bağımsız doğrulanamaz. Projeye ücretli faturalandırma bağlanırsa veya ücretli modele geçilirse bu model çağrıları ücretlenebilir. Ücretli kullanım istemeyen kullanıcı değişkeni 0 yapmalı ve projeyi Free tier tutmalıdır; anahtara otomatik maliyet kilidi iddia edilmez. Değişiklikten sonraki otomatik Studio uçtan uca denemesi ve kapak kalıcı kaydı henüz kanıtlanmadı.
