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
- [x] Plan/TODO commit `b8d3860` ve Drive kaynak yedeğiyle kaydedildi.
- [x] Güncel repo/workflow ve Gemini variable kontrol edildi; daily_shorts ve hourly_pruner aktif. `GEMINI_FREE_VISION_ENABLED=1`. Run #121 başarısız; #122 gözlem sırasında devam ediyordu. Ücretli erişim/faturalandırma açılmadı.
- [x] Faz 13/14 eksikleri planla karşılaştırıldı; geçmiş, altyazı, beyan ve Studio kapak doğrulaması açık.

## B. Güncel kanal envanteri ve video incelemesi
- [x] Aynı yetkili HAR/Google oturumuyla 5 Kasım 2026 07:49 UTC Studio Shorts envanteri alındı: 56 PUBLIC ve 2 taslak, toplam 58; taslak ID bilgileri ayrı salt-okunur kontrole tamamlandı. Başlık/durum özel saklandı; daha sonra değişebilir. Her videonun ayrıntılı içeriği henüz incelenmedi.
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

## 5 Kasım 2026: kota engeli ve gerçek kanıt

- Run #121 `41988308192` eski commit `d9263dc` ile başarısız. Gerçek `studio_error.png` üzerinde **“Günlük özel küçük resim sınırına ulaşıldı … 24 saate kadar beklemeniz gerekebilir”** modalı var; overlay sonrasındaki tıklamayı bloke etti. Bu, video yükleme kotasıyla aynı şey değildir. Eski koşudaki "kapak başarıyla kaydedildi" logu güvenilir değildir.
- Mevcut PUBLIC Zanzibar videosu `7DULxjp6PsQ` ayrıntı sayfasında Studio özel resim editörü ve JPEG/PNG dosya alanı salt okunur görüldü. Bu görünüm, **başarılı özel kapak kaydını kanıtlamaz**. Kota modalı nedeniyle pilot/toplu kapak yükleme denenmedi; sınır zorlanmayacak.
- İnceleme anında iki yeni taslak oluşmuş; bu yeni taslaklar kullanıcıdan yeni bir yayınlama talebi olmadan değiştirilmez/yayınlanmaz. Mevcut pruner ve scheduler ayarları henüz değiştirilmedi. Run #122 kendi eski checkout'u ile sürüyor; sonucu ayrıca değerlendirilmeli.
- Kullanıcı kararı: kota doluyken yeni yayın denemeleri YouTube otomatik kapak seçimiyle devam etsin; AI video yalnızca ücretsizliği ve güvenli yedeği gerçek olarak kanıtlanırsa araştırılıp bağlansın. Ücretli plan/model kullanılmaz.
- Kod: özel küçük resim kotası, genel video kotasından ayrı tanınır; eşleşen modalın Kapat düğmesi üzerinden kapatılması denenir ve otomatik kapak uyarısıyla devam edilir. Modal kapatılamıyorsa yayın durur. Henüz bu yeni sürümle gerçek yayın ve modal kapatma kanıtı yoktur.

## İlk görsel tarama ve AI video araştırması

- Envanterdeki 56 PUBLIC videonun tamamının gerçek video dosyası indirildi, her birinden 4 örnek kare ve mevcut public kapak alındı; 56 otomatik Türkçe altyazı indirildi. Özel raporda her ID için örnek kare gözlemi vardır; bu işlem tüm videoları baştan sona izlemek veya her altyazıyı/ses metnini doğrulamak değildir. 2 taslak ayrıca incelenmeli. Kapaklar kota sebebiyle henüz değiştirilmedi.
- Kullanıcı isteğiyle ücretsiz AI video araştırıldı. Google Veo 2/3/3.1 ve Gemini Omni Flash API için resmi fiyat tablosunda ücretsiz video üretim katmanı bulunmadı: https://ai.google.dev/gemini-api/docs/pricing?amp= . Yerel Wan2.1 1.3B resmi model kartı 8,19 GB VRAM belirtir: https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B . Araştırma ortamında GPU algılanmadı ve yaklaşık 1,9 GiB RAM var; bu GitHub runner durumunun kanıtı değildir. Ücretsiz ve güvenilir gerçek üretim henüz kanıtlanmadığı için AI video bağlanmadı.
- Mevcut `content_engine.py` Gemini yolu 404 veren 2.5 Flash kullanıyor ve anahtarı URL'ye koyuyordu. Ücretsiz model `gemini-3.1-flash-lite` ve key header'a taşındı; redirect kapatıldı. `main.py --force-fallback` sürmektedir; gerçek senaryo isteği ve iddiaların bağımsız doğruluğu kanıtlanana kadar üretim senaryosuna bağlandığı iddia edilmez.

- Kaynaklı fakat **yayın yapmayan** gerçek Gemini senaryo testi workflow olarak eklendi. NASA'ya göre Venüs'ün yıldızlara göre dönüşü 243 Dünya günü, yılı 225 gündür; Güneş günü yaklaşık 117 gündür: https://science.nasa.gov/venus/venus-facts/ . Başlıktaki "bir gün" ifadesi bu ayrımı belirtmediğinden mevcut Venüs videoları için açıklama/netleştirme ayrıca incelenmeli. Bu kuru test, konu tekrarını veya bütün üretilen cümlelerin doğruluğunu garanti etmez.

## Gerçek senaryo kuru testi

- Yayın yapmayan Actions koşusu `41991785782`, commit `17b5ed0`, `gemini-3.1-flash-lite` ile 84 kelimelik gerçek JSON senaryosu döndürdü. Sadece erişim/şema kanıtıdır: başlık yine “bir gün” ile yıldızlara göre dönüşü karıştırabilecek şekilde belirsizdi; NASA kaynaklarında Güneş günü ve dönüş ayrımı ayrıca incelenmeli. Üretime doğruluk/tekrar koruması olmadan bağlanmadı.
- 56 videonun her biri için kapak + 4 örnek kare ve 56 otomatik altyazı alındı. Özel rapor her videoya ait gözlem içerir, fakat yalnız örneklemeye dayalıdır, baştan sona ses/gerçeklik denetimi değildir. İki taslağın kimlikleri bulundu ama içerikleri ID bazında henüz doğrulanmadı. Videoların orijinal kapakları değil, public küçük önizlemeleri saklandı.
- #122 `41989980767`, eski `b8d3860` koduyla tamamı iptal; build-and-upload hata verdi ve aynı overlay tarafından tıklandı. Bu yeni kota-modal kodu canlı kanıtı değildir. #123 `41991701631`, yeni `31e4fa2` kodunu çekmiş ve gözlem anında devam ediyordu.

- NASA Venüs facts sayfasında “sunrise to sunset 117” ifadesi, NASA GISS kaynak sayfasındaki 117 günlük **Güneş günü** ifadesiyle çelişkili/yorum gerektiriyor. İlk kuru test bağlamında bu belirsiz ifade de üretime yansımış; bu nedenle ilk senaryo doğruluk onayı değildir. Test bağlamı GISS kaynağındaki Güneş günü ifadesiyle düzeltildi ve yeniden sınanacak.
- 08:10 UTC civarında yapılan salt-okunur kontrolde yeni bir Göbeklitepe taslağı daha (`hlmfIWp3rSc`) tespit edildi: toplam 3 taslak. #122 artefaktı aynı başlıkta, ancak eşleşme salt başlıkla kesin sayılmaz. Taslaklar yayınlanmadı ve değiştirilmedi.

- Pixabay API anahtarı servis gereği sorgu parametresindedir; eski kod hata metniyle tam URL/anahtar sızdırabiliyordu. Hata logu istisna türüne indirildi, yönlendirme reddedildi. Otomatik medya kalitesi/telif/konu doğruluğu bu düzeltmeyle kanıtlanmış değildir.
- Düzeltilmiş NASA GISS girdisiyle yayınsız Gemini text koşusu `41992632308` HTTP/API ve şema testini geçti (83 kelime). Üretilen metin hâlâ “fiziksel dengesizlik/evrenin hatası” gibi yanıltıcı retorik içerdi; kaynak doğrulama ve editoryal kontrol yokken otomatik senaryo yayınını etkinleştirmeme kararı geçerli.

- Üç taslak da kendi Studio video ID ayrıntı sayfasında salt okunur incelendi: Napolyon önizlemesinde yabancı yazı, denizanasında uzay aracı, Göbeklitepe'de Grand Canyon yazılı kap var; üçü de taslak olarak kaldı. Yalnız önizleme; tüm video/sesler tek tek doğrulanmış değildir.

## Canlı otomatik yayın #123 — başarılı yayın, kare kalite hatası

- #123 `41991701631`, `31e4fa2`: üretim/yükleme job success, `Ph4448Rkw3Q` Mariana Shorts Studio'da PUBLIC doğrulandı. Günlük özel kapak limiti uyarısı tanındı; modal kapatıldı ve kullanıcının seçtiği YouTube otomatik kapağıyla devam edildi. Koşunun geneli cron-kick nedeniyle gözlemde sürüyordu; job success, tüm koşu success değildir.
- Gemini aynı işte kare 2/5 için 0.90 güven bildirdi. Yayımlanan gerçek videodan ilgili zamanda alınan karede yabancı yazı ve kırmızı nesneler var; Mariana çukuru olduğu görünür biçimde doğrulanmıyor. Bu canlı örnekte modelin olumlu kararı kalite açısından başarısız. Özel kapak kota yüzünden zaten yüklenmedi; yayımlanan kapak YouTube otomatik seçimidir.
- Prompt daha katı ve eşik 0.95 yapıldı; bu kendi başına güvenilirlik garantisi değildir. Ek olarak gerçek kalitesi onaylanmayan karelerin otomatik seçimi varsayılan kapatıldı (`GEMINI_ALLOW_UNVERIFIED_FRAME_SELECTION` yalnız izole testte 1); üretim temsili yerel karta düşer. Seçimi açmak için gerçek olumlu/olumsuz örneklerle ayrıca doğrulama şart.

- #123 videosunun gerçek 5 kare adayıyla, yeni sıkı promptun yanıltıcı örneği reddetmesini sınayan yayınsız manuel CI eklendi. Başarı tek örnektir; varsayılan seçim kilidini açmaya tek başına yetmez.

- #123 tüm koşunun kesin sonucu `cancelled`: `channel-map` ve `build-and-upload` başarılı, `cron-kick` iptal. PUBLIC sonucu, tüm workflow success demek değildir; iptal nedeni ayrıca açık.
- Ret testi `41994197825` başarısız: GitHub runner YouTube'dan indirme adımında bot doğrulamasına takıldı, Gemini çağrısı yapılmadı. Test aynı #123 işinin gerçek artefaktını, içindeki video ID ile doğrulayarak okuyacak şekilde düzeltildi; yayın yapmaz.

- Ret testi `41996096862` gerçek #123 artefaktını başarıyla indirdi ve video ID eşleşmesini geçti; kare çıkarma adımı 5 kare üretemedi ve Gemini çalışmadı. CI ortamına FFmpeg/ffprobe kurulumu eklendi; yeni test sonucu bekleniyor.
- 08:39 UTC HAR Studio envanteri: 58 PUBLIC, 3 taslak. Yeni PUBLIC `FGFYAvARDPg` için public kapak ve 5 gerçek kare örneklendi; kapakta arazi taşıtı ve örneklerde astronot duyurusu, taşıt ve uydu yörünge grafiği görülüyor, gözyaşı konusunu örnekler doğrudan göstermiyor. Başından sona izleme/ses doğrulaması yapılmadı.
- Medya hattı Wikimedia sonuçlarını lisans/atıf ayrıntılarını almadan seçiyor; Commons'taki her dosya telifsiz değildir. Kullanım ve atıf koşulları gerçek dosya bazında doğrulanmalı; otomatik medya ve telif güvenilirliği açık görevdir.

## 08:44 UTC — gerçek ret testi ve çevrimdışı kapak adayları

- `41996283537` / commit `4342b1b`: #123 gerçek artefaktı video ID ile doğrulandı, 5 kare çıkarıldı; sıkı prompt için tek gerçek ücretsiz vision çağrısı eşleşmeyi reddetti, yayınsız test success. Tek bir olumsuz örnek yeterli kalite kanıtı değildir; otomatik kare kabulü varsayılan kapalı kalır.
- 08:39 UTC'deki 58 PUBLIC ID için 58 yerel, temsili kapak adayı oluşturuldu; 56 başlık konusu, 2'si `final short` videolarının gerçek otomatik altyazısındaki muz konusundan alındı. Son iki aday ses/içerik doğrulaması bekler. Sayı yalnız bu envanterin anlık durumudur. 23 farklı tema tasarımı örnek olarak görsel incelendi. Başlıktan oluşturulan metinlerin videoların tamamıyla eşleştiği ve iddiaların doğruluğu henüz doğrulanmamıştır.
- Gerçek tasarım kontrolünde bazı uzun sözcüklerin kenardan kesildiği görüldü; başlık yerleşimi bütün satırların genişliği/stroke/yüksekliği sınanacak şekilde düzeltildi, örnek tasarımlar yeniden gözlendi. 87 birim testi geçti. Bunlar yüklenmemiş taslaklardır; özel kapak kotası sonrası pilot ve her video için Studio kayıt kontrolü hâlâ açık.

## Somut Wikimedia atıf riski

- #123 `41991701631` gerçek CI üretim logu `submarine underwater dark` aramasında `Bunker_Valentin_Cross_-_Section.webm` Wikimedia dosyasını kullandığını gösteriyor. Commons API dosyanın `LicenseShortName = CC BY-SA 4.0`, `AttributionRequired = true` bilgisini döndürüyor: https://commons.wikimedia.org/wiki/File:Bunker_Valentin_Cross_-_Section.webm . #123 PUBLIC `Ph4448Rkw3Q` YouTube açıklaması 08:44 UTC salt okunur alındı; dosya adı, `Krauts` veya CC lisans atfı görünmedi. Bu tek bir dosya için somut uyumsuzluk riski; nihai hukuki değerlendirme değildir.
- Üretimde Commons lisans/atıf meta verisi seçilmiyor veya açıklamaya aktarılmıyor. Diğer dosyalar tek tek doğrulanmalı, üçüncü taraf şartları/atıf ve varsa share-alike yükümlülükleri incelenmeli. Kullanıcının izni olmadan mevcut PUBLIC açıklamalar değiştirilmedi. Otonom yayın, olası ek hataları çoğaltabileceğinden durdurma/devam ve mevcut açıklamalara atıf ekleme için kullanıcı kararı istenecek.
