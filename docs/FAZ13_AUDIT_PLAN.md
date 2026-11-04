# FAZ 13 — Kanal Güveni, Kalite ve Marka Düzeltmeleri (Denetim Tabanlı)

**Tarih:** 2026-11-04
**Kaynak:** Kanal denetimi (`@mentansiytas` herkese açık Shorts sayfası, 9 video, kapaklar, otomatik altyazılar)
**Kanal:** `UCBZVbwc7s7TeUCcOaN58oHQ` — https://www.youtube.com/@mentansiytas/shorts

Bu belge **canlı TODO**'dur: her adım bitince `[x]` işaretlenir, commit + push + Drive yüklemesi yapılır.

---

## 0. Denetim → Aksiyon Haritası

| # | Denetim bulgusu | Kök neden (kodda) | Aksiyon | Durum |
| :-- | :--- | :--- | :--- | :-- |
| 1 | "Bu teleskobu incele / bu kitabı oku" ama link **abone** linki (yanıltıcı) | `content_engine.py::resolve_affiliate_offer` varsayılan URL'i **kanal abone linki**; CTA metni ürün iddiası içeriyor | Ürün linki yokken dürüst CTA: "Benzer videolar için abone ol"; LLM'in uydurduğu ürün iddialı hook'lar sanitize edilir | ⏳ 13.1 |
| 2 | Kapaklar "bitiş kartı / yanlış kare" (konu nesnesi yok) | YouTube otomatik kare seçimi (AI kapak 402'de düşüyor) + yedek kapak **metin kartı**ydı | AI kapak başarısızsa **video karesi + başlık kompoziti** üretilir (konu görünür); AI prompt "subject fills frame" | ⏳ 13.3 |
| 3 | "Nötron yıldızı 6 milyar ton" → NASA ~1 milyar ton | Promptta doğrulama/iddia disiplini yok, kaynak satırı yok | `source_line` zorunlu (LLM + küratörlü kaynak haritası), abartılı rakam yasağı, nötron yıldızı gerçeği | ⏳ 13.2 |
| 4 | Mariana Çukuru iki kez yayımlandı | `.used_topics.json` yalnızca **tam başlık eşitliğine** bakıyor | Konu/anahtar kelime benzerliği ile tekrar reddi (Yeni açı şart) | ⏳ 13.4 |
| 5 | AI içerik beyanı (altered/synthetic) yok | Yükleme ekranında beyan kutusu işaretlenmiyor | Studio'da beyan kutusu otomatik işaretlenir + log kanıtı | ⏳ 13.5 |
| 6 | "Şablon hissi" / inauthentic risk | Tekrarlanan açılış/CTA kalıpları | Açılış + CTA rotasyon havuzları, son 3 kalıbın tekrarı engellenir | ⏳ 13.6 |
| 7 | Otomatik altyazı hataları ("11 ket", "Büyük EU") | YouTube kendi ASR'ini kullanıyor | Ürettiğimiz `voiceover.srt` YouTube'a **caption track** olarak yüklenir | ⏳ 13.6 |
| 8 | Profil görseli jenerik (pembe zemin + beyaz "m") | Marka görseli üretilmemiş | Banner ile uyumlu profil fotoğrafı üretilir + yüklenir | ⏳ 13.7 |
| 9 | Kaynak gösterimi yok | Açıklamada kaynak satırı şeması yok | Her açıklamada `Kaynak: <kurum> — <URL>` | ⏳ 13.2 |

---

## 1. FAZ 13.1 — CTA / Açıklama Güvenliği (yanıltıcı ürün iddiası)

- [ ] `resolve_affiliate_offer()`: URL kanal/abone linki ise CTA "Benzer videolar için abone ol: <url>" olur.
- [ ] `sanitize_affiliate_hook()`: LLM hook'undaki ürün iddiaları (teleskop/kitap/bilim seti/satın al/indir/kaşif) kanal linkiyle birleşince dürüst metne çevrilir.
- [ ] Log token'ları: "CTA guvenlik", "urun linki yok".
- [ ] Testler: `tests/test_faz13_trust.py`.
- [ ] **Mevcut 9 videonun açıklamaları canlı düzeltildi** (`scripts/fix_existing_descriptions.js` + `logs/description_fix_report.json`).

## 2. FAZ 13.2 — Kaynak satırı + rakam/iddia doğrulama

- [ ] `source_line` şeması (LLM) + küratörlü kaynak haritası (`content_engine.py::KNOWLEDGE_SOURCES`).
- [ ] Açıklama sırası: [1] abone/CTA → [2] etkileşim CTA → [3] gövde → [4] `Kaynak:` → [5] 3 hashtag.
- [ ] Prompt kuralları: abartılı/şişirilmiş rakam yasak; sayısal iddialar kaynakla eşleşmeli.
- [ ] Nötron yıldızı gerçeği: NASA ~1 milyar ton ("çay kaşığı") → birim tutarlılığı kuralı.

## 3. FAZ 13.3 — Kapak: konu nesnesi görünür

- [ ] `scripts/generate_fallback_thumbnail.py` → **video karesi + başlık kompoziti** (ffmpeg kare + PIL metin).
- [ ] AI kapak promptu: "subject fills the frame, bright, single clear object".
- [ ] Zorunlu teslim satırı korunur (`KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`).

## 4. FAZ 13.4 — Tekrar koruması (konu bazlı)

- [ ] `.used_topics.json` → `{title, topic, keywords, ts}` kayıtları.
- [ ] Benzerlik: başlık+konu token örtüşmesi > eşik → yeni konu seç, aynısını tekrar yayımlama.
- [ ] "Mariana Çukuru" tekrarı canlı olarak engellendi (kanıt: yeni konu farklı).

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
