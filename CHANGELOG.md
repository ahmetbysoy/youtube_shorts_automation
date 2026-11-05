# Değişiklik Günlüğü

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
