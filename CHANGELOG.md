# Değişiklik Günlüğü

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
