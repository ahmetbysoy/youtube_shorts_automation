# Gemini Tabanlı Otonom Shorts — Canlı TODO

> Bu dosya uygulamanın tekil takip listesidir. Bir kutu yalnız ilgili kod/test/CI veya canlı kanıt elde edilince işaretlenir. Mimari: [GEMINI_AUTONOMOUS_SHORTS_PLAN.md](GEMINI_AUTONOMOUS_SHORTS_PLAN.md).

## Durum özeti

- [x] Mimari plan ve TODO GitHub'a dokümantasyon olarak eklendi.
- [ ] Kod entegrasyonu başlamadı.
- [ ] Gemini üretimi ana otomasyon akışına bağlanmadı.
- [ ] Sahne bazlı storyboard medya motoruna bağlanmadı.
- [ ] Yeni kalite kapısı yayın akışına bağlanmadı.

## Faz 0 — Başlangıç envanteri ve emniyet

- [ ] Aktif branch, HEAD commit ve çalışma ağacı durumunu kaydet.
- [ ] daily_shorts.yml tetikleyicileri, concurrency/lock, matrix ve ana job komutlarını incele.
- [ ] Son başarılı/başarısız workflow koşularını karşılaştır; gerçek run kanıtını kaydet.
- [ ] main.py orkestrasyon adımlarını ve exit-code politikasını baseline test et.
- [ ] content_engine.py sağlayıcı seçimini, promptu, fallback koşullarını ve script.json üretimini doğrula.
- [ ] media_processor.py ve video_fetcher.js arama sırası, API/Playwright fallback'leri, lisans ve klip seçimini doğrula.
- [ ] youtube_studio_uploader.js yayın sonucu doğrulamasını ve belirsiz upload davranışını incele.
- [ ] Mevcut test paketini çalıştır; test sayısı ve sonucu commit/run ile kaydet.
- [ ] Secret isimlerinin varlığını değerleri göstermeden kontrol et; secret değerlerini asla çekme/yazma.
- [ ] Pruner, cron/watchdog, kanal ve PUBLIC kurallarını koruma listesine al.
- [ ] Başlangıç envanteri ve baseline kanıtını bu TODO'ya ekle.

**Kabul kapısı:** Mevcut davranış ve test baseline'ı biliniyor; yayın davranışı değiştirilmedi.

## Faz 1 — JSON sözleşmesi ve test altyapısı

- [ ] script.json üreten/tüketen tüm kod yollarını bul.
- [ ] Mevcut JSON örneklerini ve geriye uyumluluk gereksinimlerini kaydet.
- [ ] Versiyonlu JSON Schema tanımla.
- [ ] schema_version, generation_id, fact_check ve storyboard alanlarının tiplerini belirle.
- [ ] Geçerli/eski JSON, eksik alan, yanlış tip, bozuk JSON ve sınır durum testleri ekle.
- [ ] Eski medya tüketicisinin geçiş süresince çalışmasını sağla.
- [ ] Schema testlerini CI'a ekle.

**Kabul kapısı:** Eski üretim yolu bozulmadan yeni şema doğrulanıyor; hatalı JSON sonraki aşamaya geçemiyor.

## Faz 2 — Gemini API adaptörü ve prompt

- [ ] Güncel Gemini model/endpoint ve yapılandırılmış çıktı desteğini resmi dokümandan doğrula.
- [ ] Ücretsiz kota/erişimi gerçek API çağrısıyla kontrol et; ücretli plan veya billing açma.
- [ ] API anahtarını header ile gönder; URL/log/artifact sızıntısını test et.
- [ ] Ana promptu versiyonlu dosyada tut; konu, araştırma, senaryo, storyboard, arama ve kapak alanlarını tanımla.
- [ ] Son kullanılan konu/başlık özetini prompta ekle.
- [ ] Timeout, 429, 5xx, bozuk JSON ve boş yanıt için sınırlı retry/backoff yaz.
- [ ] JSON Schema doğrulamasını gerçek Gemini yanıtına uygula.
- [ ] Yayın yapmayan dry-run workflow ekle.
- [ ] Gerçek çağrı ve doğrulama sonucunu gizli bilgi içermeyen kanıtla kaydet.

**Kabul kapısı:** Gerçek Gemini yanıtı geçerli şemada; ücretli çağrı yok; PUBLIC yayın yok.

## Faz 3 — Kaynak doğrulama ve tekrar koruması

- [ ] Her önemli iddia için kaynak URL, kaynak adı, erişim zamanı ve ilgili metin kaydını tanımla.
- [ ] Kaynak erişilebilirliğini ve iddiayla ilişkisini doğrula.
- [ ] Tarih/sayı/ölçü gibi kritik iddiaları kaynak metniyle karşılaştır.
- [ ] Doğrulanamayan iddiayı çıkar veya konuyu yeniden seç.
- [ ] Kalıcı geçmiş yöntemini belirle; geçici Actions dosyasını kalıcı hafıza sayma.
- [ ] Konu, ana iddia, varlık ve normalize metin üzerinden tekrar kontrolü oluştur.
- [ ] Paralel koşular için atomik rezervasyon/lock/idempotency uygula.
- [ ] Geçmiş okunamıyor veya benzerlik belirsizse güvenli durdurmayı test et.

**Kabul kapısı:** Kaynaksız iddia ve tekrar konu yayın kapısından geçemiyor; paralel üretim aynı konuyu rezerve edemiyor.

## Faz 4 — Sahne bazlı medya motoru

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
| 2026-11-17 | Dokümantasyon | Bu dokümantasyon commit'i | Plan/TODO eklendi; kod değişmedi | Faz 0 başlayacak |
