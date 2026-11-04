# Değişiklik Günlüğü

## 2026-11-04 — FAZ 13.4 gerçek veri hazırlığı

- Kamuya açık YouTube Atom akışını kanal/video kimliği ve zaman doğrulamasıyla okuyan salt-okunur denetim betiği eklendi.
- Canlı akış ve pruner anlık görüntü karşılaştırması kaydedildi: 7 akış kaydına karşılık pruner raporunda 8 korunan video. Akış eksiksiz geçmiş değildir; tekrar koruması henüz etkinleştirilmedi.
- Gerçek başlıklara karşı salt-okunur token/Jaccard denetimi eklendi; Mariana 1.000 ve denizanası 0.125 sonucu, tek eşik yaklaşımının sınırlılığını gösteriyor.
- Mevcut testler sanal ortamda 83/83 geçti; bu sonuç canlı yayın veya yeni tekrar korumasının kanıtı değildir.

## 2026-11-04 — FAZ 13 doğrulama durumu

- 13.3 için kontrast temelli kare seçiminin konu tanıma veya bitiş kartı filtreleme sağlamadığı açıklandı. Run #58 önceki yedeğe ait; yeni algoritmanın canlı kanıtı bekliyor.
- 13.4 için `.used_topics.json` kalıcılığı ve sayısal kanal seçim yolundaki boşluk belgelenerek gerçek veriye dayalı uygulama ve doğrulama planlandı. Tekrar koruması henüz uygulanmadı.
- Mevcut videoların açıklama ve başlık düzeltmeleri halen bekliyor.
