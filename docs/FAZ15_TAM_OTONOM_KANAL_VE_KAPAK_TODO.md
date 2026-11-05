# Faz 15 — Kanalın tek tek incelenmesi, kapak yenileme ve otonom sistem

Tarih: 5 Kasım 2026. Bu plan canlı TODO'dur; her tamamlanan adım somut kanıtla işaretlenir, ilgili belgeler güncellenir, commit/push ve gizli bilgiler hariç Drive yedeği alınır.

## Kullanıcı kapsamı ve güvenlik

- Kullanıcı kanaldaki **tüm videoların tek tek incelenmesini ve kapaklarının yeniden düzenlenmesini** istiyor. Kanalın güncel Studio envanteri alınır; değişiklik yalnız doğru video ID'sinde, mevcut yayın/görünürlük durumunu koruyarak yapılır. Kapatılmış/silinmiş videolar için durum kaydedilir, içerik yeniden yayımlanmaz.
- Ücretli kullanım, ücretli plan veya billing açmak yok. Ücretsiz Gemini metin/görsel-anlama yeni görüntü **üretmez**. API anahtarından gerçek billing durumu her çalışmada bağımsız doğrulanamaz; Free tier durumu kullanıcı beyanı ve Studio gözlemine dayanır; billing değişirse ücret ihtimali vardır. Ücretli veya ücretsizliği belirsiz özellik açılmadan kullanıcıya sorulur.
- "Tümünü bağla" ifadesinin AI video üretimine etkisi netleştirilmeli: önceki talimat AI videoyu tüm sisteme bağlamamaktı. Ücretsiz, gerçekten kullanılabilir bir üretim yolu kanıtlanmadıkça ücretli AI video/görsel servisleri çağrılmaz.
- Yalnız gerçek hesap/oturum ve gerçek içerikle çalış; mock testleri canlı doğrulama diye raporlama. Cookie/anahtar/HAR gizli kalır. Özel Studio/Analytics verileri herkese açık GitHub'a konmaz.
- Mevcut PUBLIC, tek kanal, cron/zincir ve pruner kuralları kullanıcı talimatlarına göre korunur; toplu işlem sırasında pruner video silerse yeniden oluşturma yok, envanterde değişikliği kaydet. Bilinmeyenler tamamlandı diye gösterilmez.
- YouTube'a göre Shorts'a özel kapak bilgisayarda Studio'da doğrulanmış hesapla eklenir, kaydedilir; günlük limit olabilir ve görüntünün yayılmasına zaman gerekebilir. Hesapta gerçekten görünmüyorsa özelliği zorlamadan dur: https://support.google.com/youtube/answer/72431

## A. Plan ve mevcut durum
- [x] Bu plan/TODO hazırlanıp sürüm kontrolüne eklenecek.
- [ ] Güncel repo/workflow, aktif CI, vars/secret varlığı, koşular ve en son değişiklikler salt okunur kontrol edilsin. Ücretli erişim ve faturalandırma açılmasın.
- [ ] Geçmiş faz 13/14 eksikleri mevcut kanıtla yeniden ayrıştırılsın; eski iddialar yerine gerçek durum kaydedilsin.

## B. Güncel kanal envanteri ve video incelemesi
- [ ] Aynı yetkili HAR/Google oturumuyla YouTube Studio'ya gir ve sayfaların tamamını gezerek video ID, başlık, görünürlük, mevcut kapak ve erişilebilir metaveri envanterini **özel** sakla. Tekrar eden başlıkları ID ile ayır; sayımların gözlem zamanını kaydet.
- [ ] Her erişilebilir videoyu tek tek incele: gerçek içerik/ses/altyazı, iddia/kaynak, mevcut kapak-konu uyumu, metin okunabilirliği, sentetik içerik beyanı ve açıklama. Kapsamlı izleme veya ses dökümü başarısızsa video bazında eksik olarak işaretle, tahmin etme.
- [ ] Her video için özel rapora kaynak/kapsam, önceki kapak referansı, öneri ve işlem durumunu kaydet; telifli/yanıltıcı/konu dışı görsel ve desteklenmeyen iddia kullanma. Mevcut görseli mümkün olduğu ölçüde yedekle; indirilen görsel, orijinalin tam çözünürlüklü kopyası olmayabilir.

## C. Kapak tasarımı, pilot ve tüm videolar
- [ ] Aynı video ID'sinin gerçek içeriğine dayanan, mobilde okunabilir 9:16 tasarımlar oluştur; güvenilir mevcut video karesi veya doğru ve açıkça temsili görsel kullan. LLM'in özgüvenini gerçeğin kanıtı sayma. Fallback, ücretli API'ya veya kota başarısına bağlı olmasın.
- [ ] Tek bir video ile Studio'da özel kapak yükleme yetkisi, doğru ID, kaydetme ve yenileme sonrası kayıt kontrolünü kanıtla. Mümkünse girişsiz görüntü ayrı doğrulansın; önbellek gecikmesini kaydet. Pilot başarısızsa toplu işlemi durdur.
- [ ] Başarılı pilot sonrası her video için teker teker tasarım → yükleme → kaydet → Studio yeniden açma/kanıt sürecini uygula. Hata, captcha, günlük yükleme limiti veya yetki eksikliğinde dur/ertele ve güvenli biçimde devam edilebilir kayıt tut; video silme veya yeniden yayınlama yok.
- [ ] Bütün hedefler için `tamamlandı / kayıt doğrulanamadı / engellendi / erişilemiyor` ayrımını ve hatalı/eksiklerin nedenlerini raporla. Görüntülenme/CTR artışı garanti edilmez.

## D. Gelecekteki otonom yayın hattı
- [ ] Ücretsiz Gemini kullanımı için faturalandırma/kota kontrollerini değerlendir; doğrulanamayan maliyet garantisi vaat etme. `--force-fallback` nedeniyle LLM içeriğinin gerçekten devre dışı kaldığı yol incelensin. Ücretsizliği doğrulanan metin üretimi, başlık, kaynak kontrolü, kapak ve diğer uygun özellikler; düşük güven/kota/hata durumunda doğrulanmış yerel yedeğe düşsün. API yanıtı kaynak kanıtı değildir.
- [ ] Gerçek ve kalıcı yayın geçmişi, kanal/video kimliği ve yarış/iptal güvenliğiyle tekrar koruması; geçmiş erişilemez ya da havuz tükenirse sessiz tekrarlamak yerine durdur/uyar.
- [ ] Görsellerin video konusuyla uyumu; gereksiz şablon tekrarı; doğru kaynak/iddia, CTA ve açıklama; gerçekçi sentetik sahnelere doğru beyan; erişilebilir düzgün altyazı; profil/marka. Yetki veya doğrulama yoksa ayrı açık görev olarak bırak.
- [ ] Mevcut 14 günlük çerez yenileme, tek kanal matrix, cron/zincir/watchdog, hata kaydı, `headless:false`, pruner, PUBLIC kurallarını koru; iş kesintisinde ikinci kez yayınlamadan devam edilebilirlik sağla.
- [ ] Güvenlik/kota/zaman aşımı sınırları, secret sızıntı denetimi, ilgili birim ve entegrasyon testleri; ardından yalnız gerektiğinde gerçek kontrollü CI/Studio kanıtı ve 14 günlük performans ölçümü. Testler canlı kanıt yerine geçmez.

## E. Teslim
- [ ] Özel video bazlı rapor ve kapakları erişim kontrollü Drive'a koy; halka açık repo yalnız hassas olmayan kod ve kanıt özetini içersin.
- [ ] Her fazda README/AI_HANDOFF/CHANGELOG ve TODO'yu güncelle, commit/push yap ve kaynak yedeğini Drive'a yükle.
- [ ] Gerçek sonuçları, engelleri, değiştirilmemiş videoları, maliyet risklerini ve takip işlerini kullanıcıya açıkça bildir.
