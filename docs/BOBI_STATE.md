# BOBI_STATE.md — Canlı Durum Panosu

> Protokol: `SKILL.md` v2.0 (§1 açılış protokolü, §5 oyun kitabı)
> İlk doldurma: **2026-11-23 (UTC+3)** · Mod: tam otonom · Platform: yalnızca YouTube
> Kural: ölçülmeyen sayı yazılmaz; "ölçülemedi" işaretlenir. Bu repo herkese açıktır; Studio/Analytics özel sayıları buraya yazılmaz.

---

## 1. Envanter ve canlı kanıtlar

### 1.1 Repo (canlı `git` durumu)
- Remote: `origin https://github.com/ahmetbysoy/youtube_shorts_automation.git`, dal `main`; **push kimliği bu ortamda yok** → yerel commit + patch teslimi, push kullanıcı ortamında.
- Yerel commit zinciri: `c0d5cdc` (SKILL v4.0 kurulumu) → `57cc69a` (son Action koşulu düzeltmeleri) → `f55b273` (base).
- Çalışma ağacı temiz; üretilen dosyalar bu oturumun son commit'inde toplanır.

### 1.2 GitHub Actions — son 20 koşu (anonim REST API, 2026-11-23 çekimi)
Kaynak: `GET https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/runs?per_page=20`

| Sonuç | Sayı | Not |
|---|---:|---|
| success | 18 | Blitzkrieg 658/660/661/662, Pruner 607–611, Draft Publisher 215–220, Cron Probe 66/67, Günlük Özet 3 |
| failure | 2 | **Run 659 / `45069984817`** Blitzkrieg: fallback rezervasyon çarpması (fallback fix `fda5080` sonrası üretim kanıtı run `45071568645` SUCCESS, `lu94KrH3XxY` canlı). **Run 139 / `45071562145`** Ubuntu 26 geçiş testi: Wikipedia 429 flaky, kod değişikliği değil. |
| canceled | 0 | Son 20'de iptal fırtınası yok. |

Workflow registry (anonim): 25 workflow `active/enabled`; üretim zinciri `daily_shorts.yml`, `hourly_pruner.yml`, `draft_publisher.yml`, `daily_analytics.yml` açık. Bilinen zayıflık: GitHub `schedule` güvenilmez → zincir kalp atışı manuel/chain dispatch; aktif koşu sayılmadan yeni dispatch açılmaz (`scripts/active_runs_count.sh`).

### 1.3 Yerel durum dosyaları (bu klon, ham JSON sayımları)

| Dosya | Değer | Yorum |
|---|---:|---|
| `.used_topics.json` | 40 başlık rezervasyonu | Tekrar koruması gevşetilmez |
| `logs/published_log.json` | 11 kayıt; son 24s 4 kayıt, hepsi PUBLIC | Yerel ledger kapsamı; Studio tam envanteri yerine geçmez |
| `prune_state.json` | videos=57, `deleted_ids`=1 | Pruner taban koruması (`wouldEmptyChannel`) aktif |
| `analytics_feedback.json` | kazanan niş Tarih; `boost_active=False`; outperformance ratio 1.13 | Eşik altı → boost kapalı |
| niş ağırlığı | Tarih 5 video / 1176.6 ortalama; Bilim 6 / 1036.7; Uzay 3 / 917.0 | Tarih önde, Bilim takipte |
| `.media_history.json` | 116 medya kaydı | Çift-indirme / kayıt dedup zinciri var |
| `prune_report.json` | bayat (2026-11-05, scanned=0) | Canlı pruner logu Actions artifact'inden alınır; dosya güvenilmez |
| `kapak_gemini.json` | prompt korunmuş, `videolar=[]` | Kapak üretici PW adapter; özel kapak kotası dolunca gömülü kare devreye girer |

### 1.4 Kanal (`@mentansiytas`, `UCBZVbwc7s7TeUCcOaN58oHQ`) — **CANLI ÖLÇÜM YAPILAMADI**
- Anonim `www.youtube.com/@mentansiytas/videos` çekimi 200 dönüyor ama sayfa login/consent arkasına düşüyor: `subscriberCountText`, video listesi (`videoRenderer/gridVideoRenderer`) gövdeye gelmedi. **Abone sayısı, toplam izlenme, son 28 gün, en iyi/kötü 5 Short: ölçülemedi.** Uydurulmadı.
- Sonraki adım: Studio oturumu olan cihazdan `kpi_snapshot.py` ve manuel ekran envanteri; özel sayaçlar bu repoya değil, kullanıcının özel kaydına girer (SKILL §1.7).
- Bilinen yayın kanıtları (handoff'tan, yerel olmayan ama repo yazılı geçmiş): 22 Kasım'da 5–6 PUBLIC video canlı (`i1Qly2bE-K8`, `KJOkVyH2w-A`, `0_4S3RIGrgc`, `WF987yaDEO8`, `59U5ld3MRrw`, `lu94KrH3XxY`); `publish_anon_pending` yumuşak iniş kanıtlı.

### 1.5 YPP sayacı (hedef: 90 gün, 1 Şubat 2027 eşik artışından önce)
| Ölçüt | Değer | Durum |
|---|---|---|
| Abone | ölçülemedi (Studio gerekli) | Hedef 1.000; erken kademe 500 |
| Shorts izlenmesi (son 90 gün, yalnız PUBLIC akış) | ölçülemedi | Hedef 10M (yeni kademe sonrası 20M) |
| Saat süresi (4.000 / yeni 8.000) | ölçülemedi | Shorts'tan sayılmaz |
| Kalan süre (1 Şubat 2027'ye) | ~10 hafta (23 Kas 2026 itibarıyla) | Saat işliyor |
> Platform gerçekleri ve kaynaklar `SKILL.md` §4'te korunur; değişirse ayda bir yeniden doğrulanır.

---

## 2. Bilinen duvarlar ve durum (SKILL §3)

| Duvar | Durum | BOBİ eylemi |
|---|---|---|
| Runner IP'sinde Google kimlik modalı → taslak | Açık, atlatma yok | `draft_publisher` + kullanıcı cihazı; self-hosted runner deneyi (dış iş) |
| Günlük özel kapak limiti | Açık | `THUMBNAIL_MODE=frame` gömülü kare; limit dolunca zorlama yok |
| `schedule` cron gececiliği | Kanıtlı | Zincir asıl motor; dispatch öncesi aktif koşu say |
| Tek hesap / tek kanal (`COOKIES_JSON_2..10` yok) | Kanıtlı | Matris büyütme = ikinci Google hesabı cookie'si şartı; `wire_channel2` fail-closed |
| Pexels/Pixabay 403/boş sorgu | Kısmi | Keyless kaynaklar (NASA, IA, Mixkit, Commons) önce; cookie ikinci |
| Atıf lisans satırı | Kural | Açıklamada her zaman; Wikimedia CC BY-SA etiketi düşmez |
| Konu tekrarı | Korumalı | CAS rezervasyonu gevşetilmez; fallback dedup fail-open okuma, fail-closed yazma |
| **Kare–konu uyumsuzluğu (#123, #97)** | **Açık, en büyük kalite kaldıracı** | E7 deneyi (aşağı); uyumsuz karede duraklatma QC'si |
| Cookie ömrü (~14 gün) | Takvimli | Rotasyon scripti; değerler asla log/commit |
| Pruner kalıcı siler; silinen Shorts izlenmesi sayılmaz | Açık | E9 eşik deneyi; `PRUNE_MIN_REMAINING`/`PRUNE_MAX_DELETIONS` korunur |

**Dış veriyle çelişki kaydı (E9 tasarımı için kritik):** 2026 kılavuzları, silinip yeniden yüklenen Shorts'ların spam filtresine takılıp erişimi kalıcı sınırlayabileceğini yazıyor. Kaynaklar: <https://instantviews.net/youtube-shorts-not-getting-views>, <https://influenceflow.io/resources/optimizing-youtube-shorts-the-complete-2026-masterclass-for-creators-and-brands/>. Buna karşı pruner yalnız **düşük performanslı, yeniden yüklenmeyen** videolar için; silme sayısı `PRUNE_MAX_DELETIONS=25` ve taban korumasıyla sınırlı; her silme deney kaydına yazılır.

---

## 3. Rakip ve mekanizma taraması (kopyalama yok, mekanizma öğrenme)

İzlenen Türkçe bilim/tarih/merak odaklı kanallar (kayıt amaçlı, abone ölçümü bu oturumda alınmadı): Evrim Ağacı, Gelecek Bilimde, Hypatia Bilim, Bebar Bilim, Kozmik Anafor, Dr. Umut Yıldız, Tarih Obası, Kağan'la Keşfet. Kaynaklar: <https://www.tamindir.com/blog/takip-edilmesi-gereken-youtube-kanallari_75664/>, <https://www.plumemag.com/bilim-tarih-varolus-felsefe-temali-en-iyi-youtube-kanallari/>, <https://kagangenc.tr-cam.net/>, <https://www.erkeklersoruyor.com/teknoloji/youtube-bildiginiz-guzel-bilgilendirici-paylasim-yapan-kanallar-mi-q18059482>.

Öğrenilen mekanizma kriterleri (kaynak yanında):
- İlk 3 sn "kaydır ya da kal"; izlenen/kaydırılan oranı ≥%60 hedef, swipe-away <%40. <https://instavar.com/pdf/YouTube_Shorts_Retention_Curve_Guide_2026.pdf>, <https://instantviews.net/youtube-shorts-not-getting-views>
- APV (ortalama izlenme yüzdesi) %80+ güçlü dağıtım sinyali; Shorts 15–35 sn tatlı noktası. <https://emretekin.tr/youtube-shorts-ve-tiktok-icin-gunde-10-viral-video-uretme-3-saniyelik-kanca-hook-ve-senaryo-formulu/>, <https://influenceflow.io/resources/optimizing-youtube-shorts-the-complete-2026-masterclass-for-creators-and-brands/>
- Hook kalıpları: soru, rakam şoku, "yanlış biliyorsun", sonuç-önce-ver, yasak/hatı latifi; aynı konuda varyasyon üretmeden önce metin kalıbı kayda geçirilir. <https://pentory.net/blog/4836>
- Format çeşitliliği şartı: üst üste aynı şablon YPP "tekrarlı/içerik" riski (SKILL §4, TechCrunch 2026-07-20 kaynağı).

---

## 4. 8 rol dağılımı (SKILL §7, onaysız atama)

| # | Rol | Bu oturumdaki ilk iş |
|---|---|---|
| 1 | Repo Kazıcı | Handoff/CHANGELOG/tarama; iki Action fail kök nedeni ayrıldı (yukarı §1.2) |
| 2 | Kanal Dedektifi | Anonim sayfa ölçülemedi → Studio envanteri bir sonraki cihaz oturumuna yazıldı; rakip mekanizma tarandı (§3) |
| 3 | Büyüme Hackeri | İlk 3 deney: E1 hook, E7 görsel uyum, E9 pruner eşiği → `docs/experiments.md` |
| 4 | Etkileşim Kankası | **Sınır kararı:** yorumlar yalnız kanalın kendi videolarında; üçüncü kanala yorum bu oturumda çalıştırılmadı (kullanıcı kararı + kırmızı çizgi #2 spam). Sabit soru yomu `auto_pinned_comment.py` dry-run varsayılan, `--live` bayrağı şart |
| 5 | İçerik/Hook Yazarı | `prompts/gemini_web_story_v1.md` ilk-3-saniye hook bölümü eklendi; E1 varyasyon metinleri hazırlanır |
| 6 | Üretim Mühendisi | E7: sahne görsel filtresi `scene_media.py` BLOCKED metadata temelli; gerçek görsel eşleşme için QC eşği planlandı; medya keyless önceliği |
| 7 | Otomasyon/DevOps | Kill gate + KPI snapshot zincire eklendi; pruner env eşikleri deney değişkeni; workflow YAML parse doğrulandı |
| 8 | Editör/Rapor | Bu dosya + `docs/experiments.md`; CHANGELOG girişi; mobil 8 satır rapor |

---

## 5. İlk 24 saat planı

1. **E1 (hook):** Üretim hattındaki birbirine yakın 3 konuda 3 hook varyasyonu (soru / rakam şoku / "yanlış biliyorsun"); her varyasyon için ilk-saat izlenme ve Studio retention (erişilince) `logs/experiments.json`'a yazılır.
2. **E7 (görsel uyum):** Mevcut üretimde uyumsuz kare izleme; QC raporundaki `BLOCKED` satırları sayılır; görsel-eşleşme reddi eşiği kurulmadan yeni görsel üretimi açılmaz.
3. **E9 (pruner):** Mevcut eşik (60 dk / 100 izlenme) kontrol grubu olarak kayda geçirilir; 48 dk→48 saate alma yalnız env değişikliğiyle, kuru çalışma (`PRUNE_DRY_RUN=true`) sonrası, silme sayısı loglanarak denenir.
4. Studio oturumu açıldığı an: abone/izlenme/en iyi 5 Short sayacı özel kayda alınır, bu dosyaya yalnız özet (eşik yüzdeleri) işlenir.
5. Zincir kırılmadıkça yeni dispatch açılmaz; her commit mesajına deney numarası yazılır (SKILL §11).

## 6. Sınırlar (bu oturumda korundu)
- Secret/cookie/token: hiçbir dosya, log veya rapora yazılmadı; ekli dökümlerde görünen token'lar için kullanıcıya rotate uyarısı verildi (bu repoda tekrarlanmadı).
- Ücretli API/billing açılmadı; `partial` ≠ `verified`; `xvfb-run` tam tarayıcı; secret yazımı `printf '%s\n'`; `if: ${{ !cancelled() }}` koşuları bozulmadı.
- Üçüncü taraf kanala yorum, bot/sahte etkileşim, CAPTCHA/kimlik duvarı atlatma: yapılmadı.
