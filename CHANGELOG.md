# Değişiklik Günlüğü

## 2026-11-05 — Gerçek kapak kotası yolu ve Gemini yanlış eşleşmesi

- #123 build-and-upload başarılı, `Ph4448Rkw3Q` PUBLIC: günlük özel kapak modalı aşıldı ve kullanıcı kararıyla YouTube otomatik kapağı kullanıldı.
- Aynı koşuda Gemini, gözlemde konu nesnesi belirsiz ve yabancı yazılı bir kareyi 0.90 ile seçti. Model eşleşmesi henüz güvenilir değil; otomatik kare kabulü varsayılan kapalı, temsili yerel yedek korunur.

## 2026-11-05 — Üç taslağın Studio önizleme incelemesi

- Üç yeni taslağın kendi ID ayrıntı sayfaları salt okunur incelendi; önizlemelerinde konu dışı görseller var. Hiçbiri değiştirilmedi veya yayımlanmadı.

## 2026-11-05 — Medya anahtar güvenliği

- Pixabay gereği URL sorgusunda bulunan API anahtarı hata loguna yazılmasın diye tam istisna yerine yalnız sınıfı kaydedilir; HTTP yönlendirmesi reddedilir. Medya uygunluğu ayrıca doğrulanmalıdır.

## 2026-11-05 — Gerçek Gemini metin kuru testi

- Yayınsız #41991785782 testinde Gemini 3.1 Flash Lite geçerli 84 kelimelik senaryo döndürdü. Yıldızlara göre dönüş/Güneş günü ayrımı ve tekrar güvenliği nedeniyle otomatik senaryo yayınına bağlanmadı.
- Günlük kapak kotası devam ederken kullanıcı otomatik YouTube kapağıyla yeni yayına devamı seçti; modal düzeltmesinin canlı kanıtı bekleniyor.

## 2026-11-05 — Gemini metin bağlantısı güvenlik düzeltmesi

- Kullanılmayan 2.5 Flash text endpointi gerçek erişimi test edilen 3.1 Flash Lite ile değiştirildi; API anahtarı URL yerine header üzerinden geçer, redirect kapalı. Yeni senaryo akışı ve gerçek içerik doğrulaması hâlâ test edilmedi; `--force-fallback` korunuyor.
- 56 PUBLIC videonun her biri için mevcut kapak ve 4 gerçek kare örneklemesi, 56 otomatik altyazı indirimi yapıldı; iki taslak ve kapsamlı doğrulama açık.

## 2026-11-05 — Kota durumunda kullanıcı tercihi

- Kullanıcı kota doluyken YouTube otomatik kapakla yayına devamı seçti. Özel küçük resim kota modalını tanıyıp kapatma ve sonucu loglama eklendi; yeni kodla canlı yayın kanıtı henüz yok. AI video yalnız doğrulanmış ücretsiz ve yedekli ise araştırılacak.

## 2026-11-05 — Faz 15 ilk gerçek envanter ve kota engeli

- HAR ile 58 Shorts: 56 PUBLIC ve 2 taslak; veri özel tutuldu.
- Gerçek #121 hatası Studio ekranında günlük özel küçük resim kotası olarak doğrulandı; yükleme modalı işlemi engelledi. Eski "kapak kaydedildi" logu kanıt değil.
- Özel kapak alanı salt okunur görüldü; kota nedeniyle pilot ve toplu değişiklik yapılmadı.

## 2026-11-05 — Faz 15 planı

- Kanaldaki videoların tek tek incelenmesi, kapak pilotu ve toplu doğrulanmış uygulama ile otonom sistem eksikleri için kanıt odaklı TODO eklendi. Henüz video değiştirilmedi.

## 2026-11-05 — Ücretsiz vision etkinleştirme

- Bu depoda `GEMINI_FREE_VISION_ENABLED=1` API ile ayarlandı ve okundu; kodun güvenli varsayılanı 0. Google billing sonradan açılırsa maliyet mümkün, kapatılmalı. Anahtarın Free tier projeye aitliği kullanıcı beyanına dayanır.
- Uploader önizleme değişimini kalıcı kayıt diye sunmaz; gerçek Studio sonrası kontrol hâlâ bekleniyor.

## 2026-11-05 — Gerçek ücretsiz Gemini kare testi

- CI `41988709577`: gerçek Zanzibar video kapağı için `gemini-3.1-flash-lite` konu uyumsuzluğu yanıtı ve yerel yedek başarılı; yeni görsel üretilmedi.
- Ücretsiz kare incelemesi açıkken üretimde önce bu yol kullanılır, dış servis/billing ile ücretli görüntü API çağrılmaz. `FORCE_LOCAL_THUMBNAIL` tüm AI incelemesini kapatır.
- Kapak yükleyicisi artık salt DOM bileşeni varlığını başarı saymaz; önizleme değişimi gerektirir. Gerçek Studio yüklemesi ayrıca doğrulanmalı.

## 2026-11-05 — Gemini deneme sonucu

- Gerçek CI #1 `41988326325`: video görseli alındı, ücretsiz Gemini model çağrısı HTTP 404 döndü; üretimde kapalı. Model erişimi için güvenli keşif testi eklendi.

## 2026-11-05 — Faz 14 ilk uygulama

- Gemini text/vision, mevcut kareden konu seçimi (tek istek, açık Free-tier anahtarı gerekli); varsayılan kapalı. Ücretli Google görsel üretimi yok.
- Doğrulama başarısızsa 9:16 temsili yerel kapak; HTTP 402 derhal fallback. Zanzibar gerçek videosuyla yerel JPEG denendi. Gemini ve Studio yükleme kanıtı henüz yok; var olan birim testleri 87/87 geçti (canlı yayın kanıtı değildir).

## 2026-11-05 — Faz 14 planı

- Kullanıcı ücretli API kullanımını reddetti; AI Studio Free tier projesi ve GitHub Actions secret varlığı doğrulandı. Gerçek Gemini API ve kapak testleri henüz yapılmadı.
- Mevcut karelerin ücretsiz Gemini ile değerlendirilmesi ve yerel yedek için plan eklendi. Gemini ile yeni görsel üretildiği iddia edilmez.

## 2026-11-05 — Taslakların kullanıcının seçimiyle yayınlanması

- Kullanıcı silme yerine tüm taslakları herkese açık yayınlamayı seçti; 26 mevcut video PUBLIC olarak yayınlandı ve aynı ID’ler Studio’da doğrulandı. Silme yapılmadı.
- Telefon doğrulaması sonrası işlem tamamlandı; iki video mevcut `final short` adıyla yayınlandı. Tekrarlar, görsel kalite ve açıklama düzeltmeleri çözülmedi.
- Yayın kimlikleri: `docs/evidence/draft_publications_2026-11-05.md`. Otomatik workflow ve pruner politikası değiştirilmedi.

## 2026-11-05 — Canlı tek kanal yayın testi

- #97 yayın adımı başarılı; `7DULxjp6PsQ` Studio PUBLIC ve girişsiz player OK. Genel koşu cron-kick iptali nedeniyle cancelled.
- 25 taslak seçildi, başka içerik seçilmedi; Studio kimlik doğrulaması istediğinden hiç silinmedi. Workflow yeniden etkinleştirildi.
- Gerçek videonun örnek kareleri konuya uymuyor; ayrıca aynı başlıklı başka PUBLIC video var. Görsel eşleştirme ve tekrar önleme çözülmedi.

## 2026-11-05 — Taslak / PUBLIC doğrulaması

- Run #90 gerçek ekranında boş çocuklara özel seçimi tespit edildi. Seçim ve PUBLIC radyo durumları artık beklenip doğrulanır.
- Yayın butonu sonrasında video ID ile Studio PUBLIC ikonu ve etiketi kontrol edilir; doğrulanamazsa başarı raporlanmaz. Gerçek yeni yayın testi henüz bekliyor.
- Hero prompt şablonu ve LLM için çok sözcüklü görsel sorgu yönergesi eklendi. CI fallback bu LLM promptunu kullanmaz; görsel uyumu garanti edilmez.
- Gerçek bir taslakta çocuk seçimi ve önceden yayımlanmış videoda PUBLIC seçicisi incelendi. Mevcut birim testleri 87/87 geçti.


## 2026-11-04 — FAZ 13.4 kaynaklı gözlem geçmişi

- Atom akışı ve Studio pruner raporunu kanal/video ID, kaynak ve gözlem zamanı ile birleştiren salt-okunur araç eklendi; gerçek olmayan yayın zamanı üretilmez.
- Gerçek Studio raporunda `BlrZMXlIbU0` ve `T_yIHvyUY2Y` Antikythera başlığıyla ayrı kayıtlar. Gözlem anlık görüntüdür, üretim koruması henüz yoktur.
- Gerçek anlık görüntülerle 4 yeni test; toplam 87/87 test geçti. Canlı yayın veya engelleme kanıtı değildir.

## 2026-11-04 — FAZ 13.4 gerçek veri hazırlığı

- Kamuya açık YouTube Atom akışını kanal/video kimliği ve zaman doğrulamasıyla okuyan salt-okunur denetim betiği eklendi.
- Canlı akış ve pruner anlık görüntü karşılaştırması kaydedildi: 7 akış kaydına karşılık pruner raporunda 8 korunan video. Akış eksiksiz geçmiş değildir; tekrar koruması henüz etkinleştirilmedi.
- Gerçek başlıklara karşı salt-okunur token/Jaccard denetimi eklendi; Mariana 1.000 ve denizanası 0.125 sonucu, tek eşik yaklaşımının sınırlılığını gösteriyor.
- Mevcut testler sanal ortamda 83/83 geçti; bu sonuç canlı yayın veya yeni tekrar korumasının kanıtı değildir.

## 2026-11-04 — FAZ 13 doğrulama durumu

- 13.3 için kontrast temelli kare seçiminin konu tanıma veya bitiş kartı filtreleme sağlamadığı açıklandı. Run #58 önceki yedeğe ait; yeni algoritmanın canlı kanıtı bekliyor.
- 13.4 için `.used_topics.json` kalıcılığı ve sayısal kanal seçim yolundaki boşluk belgelenerek gerçek veriye dayalı uygulama ve doğrulama planlandı. Tekrar koruması henüz uygulanmadı.
- Mevcut videoların açıklama ve başlık düzeltmeleri halen bekliyor.
