# FAZ 13 — Kanal Güveni, Kalite ve Marka Düzeltmeleri (Denetim Tabanlı)

**Tarih:** 2026-11-04
**Kaynak:** Kanal denetimi (`@mentansiytas` herkese açık Shorts sayfası, 9 video, kapaklar, otomatik altyazılar)
**Kanal:** `UCBZVbwc7s7TeUCcOaN58oHQ` — https://www.youtube.com/@mentansiytas/shorts

Bu belge **canlı TODO**'dur: her adım bitince `[x]` işaretlenir, commit + push + Drive yüklemesi yapılır.

---

## 0. Denetim → Aksiyon Haritası

| # | Denetim bulgusu | Kök neden (kodda) | Aksiyon | Durum |
| :-- | :--- | :--- | :--- | :-- |
| 1 | "Bu teleskobu incele / bu kitabı oku" ama link **abone** linki (yanıltıcı) | `content_engine.py::resolve_affiliate_offer` varsayılan URL'i **kanal abone linki**; CTA metni ürün iddiası içeriyor | Ürün linki yokken dürüst CTA: "Benzer videolar için abone ol"; LLM'in uydurduğu ürün iddialı hook'lar sanitize edilir | ✅ 13.1 |
| 2 | Kapaklar "bitiş kartı / yanlış kare" (konu nesnesi yok) | AI kapak başarısız olabilir; otomatik kare seçimi de ilgisiz kare getirebilir | Video karesi ve başlık kompoziti uygulandı; konu uygunluğu ve Studio görüntüsü henüz kanıtlanmadı | ⚠️ 13.3 doğrulama bekliyor |
| 3 | "Nötron yıldızı 6 milyar ton" → NASA ~1 milyar ton | Promptta doğrulama/iddia disiplini yok, kaynak satırı yok | `source_line` zorunlu (LLM + küratörlü kaynak haritası), abartılı rakam yasağı, nötron yıldızı gerçeği | ✅ 13.2 |
| 4 | Mariana Çukuru iki kez yayımlandı | `.used_topics.json` yalnızca **tam başlık eşitliğine** bakıyor | Konu/anahtar kelime benzerliği ile tekrar reddi (Yeni açı şart) | ⏳ 13.4 |
| 5 | AI içerik beyanı (altered/synthetic) yok | Yükleme ekranında beyan kutusu işaretlenmiyor | Studio'da beyan kutusu otomatik işaretlenir + log kanıtı | ⏳ 13.5 |
| 6 | "Şablon hissi" / inauthentic risk | Tekrarlanan açılış/CTA kalıpları | Açılış + CTA rotasyon havuzları, son 3 kalıbın tekrarı engellenir | ⏳ 13.6 |
| 7 | Otomatik altyazı hataları ("11 ket", "Büyük EU") | YouTube kendi ASR'ini kullanıyor | Ürettiğimiz `voiceover.srt` YouTube'a **caption track** olarak yüklenir | ⏳ 13.6 |
| 8 | Profil görseli jenerik (pembe zemin + beyaz "m") | Marka görseli üretilmemiş | Banner ile uyumlu profil fotoğrafı üretilir + yüklenir | ⏳ 13.7 |
| 9 | Kaynak gösterimi yok | Açıklamada kaynak satırı şeması yok | Her açıklamada `Kaynak: <kurum> — <URL>` | ✅ 13.2 |

---

## 1. FAZ 13.1 — CTA / Açıklama Güvenliği (yanıltıcı ürün iddiası)

- [x] `resolve_affiliate_offer()`: URL kanal/abone linki ise CTA "Benzer videolar için abone ol: <url>" olur.
- [x] `sanitize_affiliate_hook()`: LLM hook'undaki ürün iddiaları (teleskop/kitap/bilim seti/satın al/indir/kaşif) kanal linkiyle birleşince dürüst metne çevrilir. **Not:** ek toleransı gerekti (`teleskobu`, `kitabı`) → regex tabanlı desenler.
- [x] Log token'ları: "CTA guvenlik", "urun linki yok" (main.py `show_tokens`).
- [x] Testler: `tests/test_faz13_trust.py` → toplam **79/79 OK**.
- [ ] **Mevcut 9 videonun açıklamaları canlı düzeltildi** (`scripts/fix_existing_descriptions.js` + `logs/description_fix_report.json`).

## 2. FAZ 13.2 — Kaynak satırı + rakam/iddia doğrulama

- [x] `source_line` şeması (LLM) + küratörlü kaynak haritası (`content_engine.py::KNOWLEDGE_SOURCES`) → 23/23 senaryoya kaynak eklenmiş; URL erişimi kontrol edildi. HTTP 200 tek başına her iddiayı doğrulamaz.
- [x] Açıklama sırası: [1] abone/CTA → [2] etkileşim CTA → [3] gövde → [4] `Kaynak:` → [5] 3 hashtag.
- [x] Prompt kuralları: abartılı/şişirilmiş rakam yasak; sayısal iddialar kaynakla eşleşmeli (havuz metinleri kaynaklı olarak düzeltildi).
- [x] Nötron yıldızı gerçeği: NASA ~1 milyar ton ("çay kaşığı") → başlık+metin düzeltildi (1 Milyar Ton).

## 3. FAZ 13.3 — Kapak: konu nesnesi görünür

- [x] `scripts/generate_fallback_thumbnail.py` → **video karesi + başlık kompoziti** (ffmpeg kare + PIL metin) + konu rozeti + yukarı bakan ok.
- [x] AI kapak promptu: "single clear subject filling the frame", "no text, no end card".
- [x] Zorunlu teslim satırı korunur (`KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`). Run #58 önceki yerel yedeği kanıtlar; **13.3 sonrası yeni kare algoritmasını kanıtlamaz**.
- [ ] Gerçek video örneklerinde konunun görünürlüğü, bitiş kartı/yazı kontrolleri ve Studio’da kapağın görünmesi doğrulanacak. Kontrast seçimi bu şartları tek başına garanti etmez.

## 4. FAZ 13.4 — Tekrar koruması (konu bazlı)

**Durum: tasarım / henüz uygulanmadı.** `.used_topics.json` Git tarafından izlenmiyor; CI çalışma ortamı yeni oluşturulduğunda bu dosya kalıcı değil. Sayısal kanal kimliği için slot seçimi geçmiş başlık filtresini de kullanmıyor. Bu bulgular mevcut koddan doğrulandı; Mariana tekrarının tek nedeninin bunlar olduğu ve kesin kaç saatte tekrarlandığı kanıtlanmış değil.

- [x] Gerçek kanalın herkese açık akışından doğrulanabilir anlık görüntü alındı (`scripts/audit_public_feed.py`, `docs/evidence/public_feed_2026-11-04.json`).
- [x] Akış ve Studio pruner raporu karşılaştırıldı: akış 7, rapor 8 korunan video; `8_bf4eAz3a0` akışta yok (`docs/evidence/feed_pruner_comparison_2026-11-04.json`). Zamanlar farklı; eksiklik nedeni kesin değil. Akış tek başına eksiksiz geçmiş olarak kullanılmaz.
- [x] Gerçek akış başlıkları ve 23 senaryonun token örtüşmesi salt-okunur incelendi (`scripts/audit_repeat_candidates.py`; `docs/evidence/repeat_candidates_2026-11-04.json`). Mariana tam başlık örtüşmesi 1.000; farklı başlıklı denizanası 0.125: salt Jaccard eşiğinin bu tekrarı kaçırabileceği görüldü. Sayılar karşılaştırmadan çıkarılır; rakam değişikliği yeni açı kanıtı değildir.
- [x] Kanal kimliği eşleşen gerçek Atom/Studio anlık görüntülerini kaynak ve gözlem zamanıyla birleştiren salt-okunur geçmiş oluşturucu eklendi (`scripts/build_verified_history.py`); örnek çıktı `docs/evidence/observed_history_2026-11-04_1711.json`. Studio gözlem zamanı yayın tarihi değildir; eksik tarihler uydurulmaz.
- [x] Gerçek Studio raporunda Antikythera tekrarına rastlandı: `BlrZMXlIbU0` ve `T_yIHvyUY2Y`, aynı başlıkla 17:11:21 UTC raporunda listeleniyor (`docs/evidence/pruner_report_2026-11-04_1711.json`).
- [ ] Gerçek kanal ve video kimliğiyle, yalnızca yayını doğrulanan kayıtları kalıcı geçmişe yaz; zaman ve başlık uydurma. Üretime bağlı, koşular arası kalıcı bir kayıt mekanizması henüz yok. Eski kayıtları kanalın gerçek verilerinden çıkar; eksik kayıtlar açıkça belirtilsin.
- [ ] Geçmişin koşular arasında güncel kalması, aynı kanalda eşzamanlı yayınların yarışı, hata/iptal ve Git push çakışmaları için güvenli iş akışı tasarla; kayıt okunamazsa sessizce boş varsayma.
- [ ] Türkçe normalizasyonu ve konu/anahtar sözcük benzerliğiyle farklı başlıklı tekrarları reddet; yeni açıyı yalnızca benzerlik skoru ile kanıtlanmış sayma.
- [ ] Tüm seçenekler kullanılmışsa tekrarı otomatik seçmek yerine yayını durdur ve uyar; LLM, analitik boost ve fallback yollarının tümünü koru.
- [ ] Üretim tekrar koruması için birim ve entegrasyon testleri, sonra gerçek CI ve kanal üzerinde kanıt. Kaynaklı geçmişin gerçek görüntülerle 4 testi yazıldı (genel test kümesi 87/87). Geçmişe sahte/varsayımsal kayıt yazma.
- [ ] Mariana tekrarının engellendiğine dair gerçek CI kanıtı.

## 5. FAZ 13.5 — AI içerik beyanı (altered/synthetic)

- [ ] Yükleme ekranında beyan kutusunu işaretle (`ytcp-video-details` / beyan butonu), yoksa uyarı logu.
- [ ] Kanal "Hakkında" metnine AI üretimi beyanı eklendi.

## 6. FAZ 13.6 — Şablon çeşitliliği + altyazı doğruluğu

- [ ] Açılış/CTA rotasyon havuzları (son 3 kalıp tekrar edilmez).
- [ ] `voiceover.srt` → YouTube caption track yüklemesi (otomatik altyazı yerine doğru metin).

## 7. FAZ 13.7 — Kanal kimliği

- [ ] `scripts/generate_avatar.py` (banner ile aynı dil) + Studio profil fotoğrafı yükleme.

## 8. FAZ 13.8 — Doğrulama ve teslim

- [ ] Birim testleri (`tests/test_faz13_trust.py`) — tamamı yeşil.
- [ ] `actionlint` temiz, `node --check` temiz, YAML parse temiz.
- [ ] Canlı CI koşuları (kapak/kaynak/CTA/beyan log kanıtları).
- [ ] Drive yedekleri (her faz sonunda zip).
- [ ] README + AI_HANDOFF + CHANGELOG güncellendi.

---

## Ölçüm notu (gerçekçilik)

Kanal 2 abone / 9 Shorts ile başlangıç erişimi aldı; ancak **ölçüm penceresi çok kısa** (son 4 video ~49 dk içinde).
Kalıcı performans yargısı için 14 günlük Studio verisi (gösterim, CTR, izlenme süresi, trafik kaynağı) gerekir.
Bu fazda **ölçülebilir sayı uydurulmaz**; ölçüm `scripts/analytics_scraper.js` ile günlük toplanır.

## 9. Yayın / taslak olayı — 5 Kasım 2026

- [x] Run #90 (`41939518221`) gerçek log ve `studio_error.png` incelendi: 18 ilerleme denemesinden sonra PUBLIC radyo zaman aşımına uğruyor; Studio ekranında zorunlu çocuklara özel seçimi boş ve İleri pasif. Bu, #90 için kanıttır; tüm taslakların nedeni olduğu kanıtlanmamıştır.
- [x] Çocuklara özel değil radyo öğesinde görünürlük beklentisi, tıklama sonrası aynı elemanda `aria-checked=true` doğrulaması eklendi. Gerçek mevcut taslakta seçim denendi; `true` gözlendi.
- [x] PUBLIC seçim durumu ve etkin yayın düğmesi kontrolü; yayın sonrasında aynı video ID'sinin Studio satırındaki PUBLIC ikonu ve etiketi doğrulanmadan başarı yazılmaz. Gerçek, daha önce PUBLIC olan `1IAgNqsjgvQ` üzerinde Studio seçicisi doğrulandı.
- [x] `docs/AI_VIDEO_HERO_PROMPT.md` eklendi; LLM arama terimleri için konuya özel 2–3 sözcük önerisi eklendi. Mevcut CI `--force-fallback` kullandığından bu prompt değişikliği CI fallback görsellerini düzeltmez. Medya-konu uyumu veya yüzdelik performans iyileşmesi garanti edilmez.
- [x] `node --check` ve mevcut test kümesi 87/87 geçti (test paketi birim testleri içerir; canlı yeni yayın kanıtı değildir).
- [ ] Gerçek Studio taslaklarını yalnızca taslak oldukları doğrulanarak kalıcı sil; sonuç sayısını kanıtla. 25 taslak seçildi, 0 başka video seçildi; YouTube kimlik doğrulaması istediği için **silme yapılmadı**. Üretim geçici durduruldu, run #96 iptal edildi; ardından workflow yeniden etkinleştirildi.
- [x] Yeni kod `3f759a0` GitHub + Drive'a yüklendi. Tek kanal testinde run #97 (`41948576364`), build-and-upload başarılı; `7DULxjp6PsQ` için Studio PUBLIC ve girişsiz oynatılabilirlik doğrulandı. Koşunun geneli `cron-kick` iptal edildiğinden **cancelled**. Yeni zincir 01:45 UTC için tetiklendi; otomatik workflow yeniden aktiftir.
- [ ] Video-görsel uyumsuzluğunu düzelt ve tekrar test et. 7DULxjp6PsQ gerçek videosunun 4, 10, 17, 24, 31. saniye örneklerinde Rusça yazılı uçak, yan dönmüş kıyı görüntüsü ve ilgisiz yazılı grafik görüldü; İngiliz-Zanzibar savaşı anlatımına uygunluk **başarısız**. Sesin tamamı ayrı transkribe edilmedi; değerlendirme görüntüler ve ekrandaki altyazı üzerindendir. Aynı başlıklı ikinci PUBLIC video da var: `WKYwF96hQzg`. 13.4 tekrar koruması hâlâ üretime bağlı değil.
