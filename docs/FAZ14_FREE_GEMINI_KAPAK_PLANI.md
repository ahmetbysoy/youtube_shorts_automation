# Faz 14 — Ücretsiz Gemini ile kapak karesi ve güvenli yedek

Kullanıcı ücretli API kullanımını reddetti. AI Studio projesi gözlemde Free tier; `GEMINI_API_KEY` GitHub Actions secret'ı mevcut. Anahtarın değeri repo, log, artifact veya Drive'a yazılmaz.

## TODO

- [x] AI Studio aynı hesapla açıldı; kullanıcı Google koşullarını onayladı ve projeyi kendisi oluşturdu. Google görsel üretim modelleri resmi fiyat listesinde ücretsiz değil; ücretli üretim yapılmayacak.
- [ ] Ayrı, elle başlatılan ve yayın yapmayan gerçek CI testinde ücretsiz Gemini görsel-anlama/text model erişimini ve anahtarın kullanılabilirliğini doğrula; ücretli image-generation endpointine istek gönderme.
- [ ] Üretilen videodan aday kareleri çıkar. Ücretsiz görsel-anlama modeli yalnız mevcut karelerdeki konunun eşleşmesini incelesin; uygun kare yoksa uydurma eşleşme yerine güvenli yerel yedek üret.
- [ ] Kota, zaman aşımı, eksik anahtar, düşük güven veya geçersiz yanıt durumlarında AI'ya bağlı olmadan yerel yedek kapak oluştur. Fallback kapasitesi ve video/konu uygunluğu ayrı ayrı gerçek örneklerle kontrol edilsin.
- [ ] Otomasyona güvenli sınırlı bağlantıyı ekle; secret'ı yalnız gereken işleme aktar. Bir isteği geçme, anahtarı yazdırma, ücretli görsel modeli çağırma. Free tier haricinde varsayımsal ücretsiz olduğu iddia edilmesin.
- [ ] Otomatik workflow, pruner ve PUBLIC görünürlük kuralları korunmalı; kullanıcı istemeden mevcut yayınlar düzenlenmemeli ve AI video tüm sisteme bağlanmamalı.
- [ ] Gözlemleri/tüm sınırlamaları belgeleyip GitHub ve Drive'a yedekle; gerçek canlı yayın denemesi ayrıca izin ve kanıt gerektirir.

## Doğrulanmış sınırlamalar

Google fiyat sayfasında Gemini 3.1 Flash Lite Image ve Nano Banana 2.1 için ücretsiz API katmanı yoktur. Gemini'nin ücretsiz metin/görsel-anlama modeli, görsel dosyası ÜRETMEZ. Google projesine sonradan faturalandırma bağlanırsa model kullanım ücretleri değişebilir; her koşuda yalnız API anahtarıyla proje fatura durumunu bağımsız doğrulamak mümkün değildir. Mevcut projenin Free tier durumu 5 Kasım 2026'da AI Studio'da gözlemlenmiştir.
