# Faz 14 — Ücretsiz Gemini ile kapak karesi ve güvenli yedek

Kullanıcı ücretli API kullanımını reddetti. AI Studio projesi gözlemde Free tier; `GEMINI_API_KEY` GitHub Actions secret'ı mevcut. Anahtarın değeri repo, log, artifact veya Drive'a yazılmaz.

## TODO

- [x] AI Studio aynı hesapla açıldı; kullanıcı Google koşullarını onayladı ve projeyi kendisi oluşturdu. Google görsel üretim modelleri resmi fiyat listesinde ücretsiz değil; ücretli üretim yapılmayacak.
- [ ] Ayrı, elle başlatılan ve yayın yapmayan gerçek CI testinde ücretsiz Gemini görsel-anlama/text model erişimini ve anahtarın kullanılabilirliğini doğrula; ücretli image-generation endpointine istek gönderme.
- [x] Aday kare incelemesi `scripts/gemini_frame_selector.py` (text/vision endpoint, bir istek, güven eşiği) eklendi. Gerçek Gemini yanıtı henüz doğrulanmadı; doğruluk garantisi değildir.
- [x] Hata/kota/zaman aşımı/düşük güvende yerel temsili kapak yolu eklendi; Zanzibar gerçek videosunda anahtar kapalıyken 1080×1920 JPEG doğrulandı. Temsili ikon tarihsel doğrulama veya gerçek görsel değildir. Modelin konu uygunluğu ve Studio kapağı ayrıca doğrulanmalıdır.
- [x] Secret, yayın işine enjekte edildi; `GEMINI_FREE_VISION_ENABLED` repo variable varsayılan 0, gerçek test geçmeden aktif değil. Kare değerlendirmesi bir istekle sınırlıdır; ücretli görsel üretim endpointine istek göndermez. Ücretli billing bağlanırsa bu anahtarın text API kullanımı da ücretlenebilir: değişkeni 0 yapın.
- [ ] Otomatik workflow, pruner ve PUBLIC görünürlük kuralları korunmalı; kullanıcı istemeden mevcut yayınlar düzenlenmemeli ve AI video tüm sisteme bağlanmamalı.
- [ ] Gözlemleri/tüm sınırlamaları belgeleyip GitHub ve Drive'a yedekle; gerçek canlı yayın denemesi ayrıca izin ve kanıt gerektirir.

## Doğrulanmış sınırlamalar

Google fiyat sayfasında Gemini 3.1 Flash Lite Image ve Nano Banana 2.1 için ücretsiz API katmanı yoktur. Gemini'nin ücretsiz metin/görsel-anlama modeli, görsel dosyası ÜRETMEZ. Google projesine sonradan faturalandırma bağlanırsa model kullanım ücretleri değişebilir; her koşuda yalnız API anahtarıyla proje fatura durumunu bağımsız doğrulamak mümkün değildir. Mevcut projenin Free tier durumu 5 Kasım 2026'da AI Studio'da gözlemlenmiştir.

## Uygulama sınırı

Yerel yedek `--strict-subject` ile rastgele kontrast karesi yerine uygunluk doğrulanamazsa açıkça **temsili görsel** içeren metin kartına düşer; eski standalone kullanımda `--strict-subject` yoksa kontrastlı kare seçimi geriye dönük korunur. Dış servis HTTP 402 ise beklemeden yedeğe geçilir. Bu yöntem Google ile sıfırdan görsel üretmez; uygunluk, tıklanma ve yayınlanan Studio kapağı garantisi vermez. Gerçek Gemini testi [yayın yapmayan manuel workflow](../.github/workflows/free_gemini_probe.yml) ile yapılacak.

İlk gerçek test #1 (run `41988326325`, commit `f007d7a`): gerçek herkese açık video görseli alındı; Gemini text/vision çağrısı HTTP 404 döndürdü. Bu nedenle üretimde Gemini değişkeni aktif edilmedi. Hesabın model listesi gerçek API ile ayrıca kontrol ediliyor; HTTP 404 nedeni henüz doğrulanmadı.

İkinci canlı CI (`41988450201`): anahtar ile model listesi başarıyla okundu ve `gemini-2.5-flash-lite` listede var; generateContent yine HTTP 404. Ücretli görsel API denenmedi. Yerel yedek CI içinde 1080x1920 doğrulandı. HTTP 404 nedeni belirsiz; farklı ücretsiz text modelleri ile teşhis eklendi.
