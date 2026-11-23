# experiments.md — BOBİ Deney Defteri

> Protokol: `SKILL.md` §5.1–5.2. Her deney **tek değişken, tek ölçüt, sabit pencere**.
> Makine yan kaydı: `logs/experiments.json` (git ignore'da, çalışma sayacı); bu dosya insan karar kaydıdır.
> Karar kuralı (başlangıç; veriyle ezilir): 24 saatte kanal medyanının **2×'si** → katla (aynı varyasyon 3 yeni konuda tekrarla); medyanın **altı** → 48 saatte kes. Silme/geri alma işlemleri önce `PRUNE_DRY_RUN=true`, sonra gerçek çalışma, sonra satır.

## Karar kuralları ve veri bağları
- Ölçüt Studio'dan geliyorsa: `viewed/swiped` oranı, ortalama izlenme yüzdesi (APV), ilk saat ve 24 saat izlenme. Studio erişimi yoksa "ölçülemedi" yazılır, varsayıma karar verilmez.
- Rakipsel kıyas kaynakları `docs/BOBI_STATE.md` §3'te; kopyalama yok, mekanizma öğrenme var.
- Format çeşitliliği zorunlu (SKILL §5.3): üst üste iki video aynı hook kalıbı/kurgu olmaz.
- YPP riski: aynı şablon tekrarı "yapay/tekrarlı içerik" sınıfına girebilir (SKILL §4).

---

## Açık deney tablosu

| # | Deney | Değişken | Ölçüt | Pencere | Durum | Karar |
|---|---|---|---|---|---|---|
| E1 | Hook laboratuvarı | İlk 2–3 sn hook kalıbı (soru / rakam şoku / "yanlış biliyorsun") | İzlenen-kaydırılan oranı (Studio), ilk 1s ve 24s izlenme | 7 gün | **Açıldı — kod hazır, canlı ölçüm bekliyor** | Bekliyor |
| E7 | Görsel–konu uyumu | Sahne karesi seçim/uyum QC'si | Uyumsuz kare sayısı, APV, olumsuz yorum sinyali | 14 gün | **Açıldı — temel tarama** | Bekliyor |
| E9 | Pruner eşiği | 60 dk/100 izlenme (kontrol) vs 48 sa/100 izlenme (uygulama adayı) | Kanal toplam izlenme, silinen video sayısı, kurtarılan izlenme | 14 gün | **Açıldı — kontrol grubu kaydı** | Bekliyor |

## Detay kartları

### E1 — Hook laboratuvarı (7 gün)
- **Hipotez:** Aynı konuda ilk-3-saniye kalıbı değişimi, `viewed/swiped` oranını ve ilk-saat izlenmeyi hareket ettirir; soru ve rakam şoku "düz anlatım" açılışından iyidir.
- **Değişken (tek):** İlk 2–3 cümlenin hook kalıbı; konu, süre, ses, medya stili sabit tutulur.
- **Varyasyonlar:**
  - A (soru): "Hiç düşündün mü, neden …?"
  - B (rakam şoku): "…'da şu rakam tek başına her şeyi değiştiriyor: 0,7 / 38 kat / 14 milyar yıl."
  - C (yanlış biliyorsun): "Çoğunluk tersini sanıyor: aslında …"
- **Ölçüt:** Studio retention (viewed/swiped ≥%60 hedef, swipe-away <%40), ilk 1 saat ve 24 saat izlenme, APV (kaynak: Instavar retention PDF, InstantViews 2026 kılavuzu — `BOBI_STATE.md` §3).
- **Yöntem:** `prompts/gemini_web_story_v1.md` hook bölümü üretime bağlı; varyasyon etiketi `logs/experiments.json` `variant` alanına yazılır. Her varyasyon en az 3 farklı konuda tekrar edilmeden "katla" kararı verilmez.
- **Karar:** 24s'te medyan 2× üstü varyasyon → katla; altı → 48s içinde kes.
- **Risk notu:** Hook yanıltıcı iddia veya abartı içeremez (kırmızı çizgi #6); merak boşluğu gerçek iddiaya bağlanır.

### E7 — Görsel–konu uyumu (14 gün)
- **Hipotez:** Kareler konuyla eşleştiğinde APV artar, olumsuz "alakasız görsel" yorumu azalır; bilinen açık sorun #123/#97 (uçak karesi, yabancı yazı).
- **Değişken (tek):** Kare seçim önceliği ve uyum QC'si (metadata BLOCKED temelli filtreden anlam-uyum katmanına).
- **Ölçüt:** Üretilen videolarda uyumsuz kare sayısı (QC logu), APV, yorum duygu dengesizliği, ilk-saat izlenme.
- **Kural:** Uyum doğrulanamayan kare için montaja geçilmez; kaynak keyless önce (NASA, Internet Archive, Mixkit, Commons), cookie'li ikinci sırada.
- **Sınır:** Otomatik kapak/kape kabulü varsayılan kapalı kalır; tek koşuya bakarak açılmaz (Faz 15 dersi).
- **Karar:** Uyum oranı ve APV birlikte yükselirse katla; sadece üretim yavaşlıyorsa kaynağı genişlet, eşiği düşürmeden kaliteyi boşaltma.

### E9 — Pruner eşiği (14 gün)
- **Hipotez:** Shorts dağıtımı gecikmeli geldiği için 60 dk/100 izlenme eşiği erken silme yapar; 48 saat bekleme, izlenmesi sonradan gelen videoları kurtarabilir. Karşı uyarı: silinen Shorts izlenmesi YPP sayacına katılmaz ve silip yeniden yükleme spam filtresi tetikler (kaynaklar `BOBI_STATE.md` §2 tablosu alt notu).
- **Değişken (tek):** `PRUNE_MIN_AGE_MINUTES` (3600 aday) vs mevcut 60; `PRUNE_MIN_VIEWS=100` sabit; `PRUNE_MAX_DELETIONS=25` ve `PRUNE_MIN_REMAINING=1` korunur.
- **Ölçüt:** Kanal toplam PUBLIC izlenme eğilimi, silinen video sayısı, kurtarılan (48. saatte eşik üstü kalan) video sayısı, kalıcı izlenme kaybı.
- **Yöntem:** Önce `PRUNE_DRY_RUN=true` ile kimler düşeceği raporlanır; ardından tek seferde bir eşik değişir; her silme (video ID olmadan sayı neden) bu dosyaya satır eklenir.
- **Karar:** Eşik yükselişi toplam izlenmeyi artırır ve koruma tavanı aşılmazsa katla; izlenme yavaşlar veya taban koruması devreye girerse eski eşiğe dön.
- **Koruma:** Kanal tabanı boşaltılmaz; `wouldEmptyChannel` reddi kapanmaz.

---

## Bekleme sırası (SKILL §5.2 havuzu, öncelik veriye göre değişir)

| # | Deney | Neden sırada bekliyor |
|---|---|---|
| E2 | Döngü final (kapanış cümlesi başa bağlanır) | E1 bitmeden iki değişken birden değişmesin |
| E3 | Seri formatı ("Parça N" + sabit soru yorumu) | Kanal yorum/abone sinyali Studio'dan alınmadan ölçülemez |
| E4 | Format çeşitliliği (mit/gerçek, Top 3, karşılaştırma) | E1 sonucu format tercihini besleyecek |
| E5 | Trend avı (Trends TR + Wikipedia trafiği, 6 saatte video) | Konu kaynağı API/anahtarsız izlenecek; E1/E7 ile çakışmasın |
| E6 | Süre eğrisi (20–25 / 35–40 / 60 sn) | Medya ve TTS timing QC kararlı olunca |
| E8 | Yayın saati (4 dilim, eşit konu) | Günlük yayın hacmi stabilize olunca |
| E10 | Gömülü kapak açık/kapalı | Kapak kotası günlük gözlemiyle |
| E11 | Başlık kalıbı (merak/rakam/soru/zıtlık) | E1 hook sonuçlarıyla eşzamanlı okunur |
| E12 | Kanal vitrini (öne çıkan, playlist, hakkında) | Abone dönüşüm ölçümü Studio gerekli |

## Karar geçmişi
| Tarih | Deney | Gözlem (kanıt) | Karar |
|---|---|---|---|
| 2026-11-23 | E1/E7/E9 | Başlangıç kaydı; Studio sayaçları erişilemediği için sadece hipotez ve ölçüt bağlandı | Açıldı, bekliyor |

## Komut (makine yan kaydı)
```bash
python3 scripts/experiment_ledger.py add --id E1 --variant A --hypothesis "..." --metric "viewed/swiped" --window 7d --status active --note "ilk varyasyon yüklendi"
python3 scripts/experiment_ledger.py list
```
Üretilen `logs/experiments.json` mahalli sayaçtır; bu dosyadaki karar satırları insan onayı/veri sonrası girilir.
