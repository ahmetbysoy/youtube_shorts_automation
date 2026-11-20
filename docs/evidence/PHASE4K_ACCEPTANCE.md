# Faz 4K Kabul Raporu — Orkestrasyon Kök Neden Analizi ve Medya Zinciri Güçlendirmesi

**Tarih (Europe/Istanbul):** 2026-11-20
**Branch:** `main` (commits: `b6a54f9` → `f8a53b9`)
**Repo:** https://github.com/ahmetbysoy/youtube_shorts_automation

---

## 1. Yönetici Özeti

Faz 4J sonrası Faz 4G uçtan uca koşuları rastgele fallback konularında
`storyboard_media_selection_blocked` ve `black_frames` ile başarısız oluyordu.
İlk başarılı koşu (Posta Pulları — run **44670492824** @ `e5c0f70`) sonrasında
yeni konularda (Fatih Sultan Mehmet, Mariana Çukuru, Beyin Ağrı, Mariana plastik,
İlk Uçuş, Domuzlar, Antarktika, Çikolata-Uzay, Piri Reis) peş peşe farklı hata
modları ortaya çıktı; her biri tek tek teşhis edilip düzeltildi.

**Nihai başarı:** Faz 4G run **44700976069** @ `f8a53b9` → **SUCCESS**
- ✅ 4/4 sahne medya seçimi (Wikimedia; resim+crop, video+contain, loop_allowed)
- ✅ FFmpeg cinematic montaj + altyazı + kapak
- ✅ Final QC: **39/39 geçti, 0 hata** (3 uyarı)
- ✅ Video: **6.91 MB, 38.57s, 1080×1920, h264/aac**, black frames %0.0
- ✅ YouTube yüklemesi HİÇ çalıştırılmadı
- ✅ scene_media_manifest.json artifact olarak kaydedildi

URL: https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44700976069

Önceki ara başarılar (daha dar konu seti):
- **44670492824** @ `e5c0f70` — Posta Pulları (39/39 QC)
- **44682413882** @ `0ab08bc` — İlk Uçuş (39/39 QC)

---

## 2. Kök Nedenler (Kümülatif)

### İlk dalga (b6a54f9 → e5c0f70; Posta Pulları başarısı)
1. **Wikimedia CC0 lisans tespiti sıkıydı** — `/deed.en` suffix ve "No restrictions"
   PD işaretleri reddediliyordu.
2. **gsrlimit=6 küçük** — ilk sayfa BY-SA doluysa seçim bloklanıyor.
3. **iiurlwidth=1440 yetersiz** — dikey videoda `min(w,h)≥720` sağlanamıyor.
4. **Video min süre ≥ scene.duration** — loop ile uzatılabileceği hesaba katılmıyor.
5. **`loop_allowed: False`** — kısa klipler V/A süre uyumsuzluğu yaratıyor.
6. **Browser provider probe/consecutive_empty cache yoktu**.
7. **Jenerik Wikimedia fallback yoktu**.

### İkinci dalga (c15a3dd → 14ef346; konu-özel hatalar)
8. **Osmanlı/tarih kategorisi dardı** — "ottoman","sailing","constantinople","bizans"
   gibi kelimeler fallback'te yoktu (Fatih Sultan Mehmet konusu).
9. **Image fit_mode=contain** → landscape görsellerde siyah letterbox → QC
   `black_frames` ~%20 (Mariana Çukuru). **Düzeltme:** imajlar `crop`, videolar
   `contain`.
10. **Medikal kategori eksikti** — "beyin","ağrı","doktor","ameliyat","surgery",
    "brain","medical","biology","cell" gibi kelimeler yoktu; otomatik keyword
    çıkarma (ALIASES ile kök birleştirme) "absent agri agrilarinizi" gibi çöp
    üretiyordu.
11. **LLM garbage query'leri** — local-fallback matrix "science named",
    "science nature", "history fear", "science together", "history back" gibi
    placeholder/geçersiz sorgular üretiyor; visual_keywords enjekte edildi,
    "science X" / "history X" / "nature X" placeholder pattern'i tespit edilip
    konu-özel sorgular eklendi.

### Üçüncü dalga (2981157 → f8a53b9; dil ve kategori kör noktaları)
12. **TR→EN alias kapsamı yetersizdi** — Türkçe ekli kelimeler (uzayda, çukuru,
    beynin, yılda, kızaklar, vs.) İngilizce köklere eşlenmiyordu. Prefix-match
    ile Turkish agglutinative suffix stripping eklendi; 120+ yeni alias
    (osmanlı→ottoman, çukur→trench, antarktika→antarctica, çöl→desert,
    foton→photon, ışık→light, beyin→brain, domuz→pig, ve niceleri).
13. **Compound splitter yanlış pozitif üretiyordu** — heuristic pozisyona
    dayalı ayırma "çıkmadı" → "cikm"+"adi" → "named" gibi saçma eşleşmeler
    yaratıyordu. Kapatıldı; sadece bilinen İngilizce compound'lar kullanılıyor.
14. **Relevance anchor primary_query'e çok bağlıydı** — primary query garbage
    ("history back") ise "back" gibi stop-word'e anchor alınıyordu. Düzeltme:
    primary sağlam değilse (content-word yoksa) mevcut query ile narration
    kesişimi anchor olarak kullanılıyor.
15. **query_coverage=0.5** — uzun/çok-kelimeli sorgularda tek kelime eşleşmesi
    yetersiz kalıyordu. 0.34'e düşürüldü (en az 1/N kelime).
16. **Hayvan/çöl/kutup/fizik kategorileri yoktu** — domuz/çöl/antarktika/ışık/foton
    gibi konularda fallback hiç tetiklenmiyordu. Kapsam genişletildi,
    kategoriye özel ek sorgular eklendi.
17. **Schema validasyonu** — emergency fallback yolunda scene_media kaydına
    `assessment`, `media`, `file_probe` alanları yazılmıyordu; schema zorunlu
    kılıyor. Düzeltildi.
18. **En son çare katmanları** — tüm kategoriler ve Türkçe kelimeler başarısız
    olursa (a) tüm visual_keywords tek tek Wikimedia'da denenir, (b) title/topic
    kelimeleriyle arama yapılır, (c) relaxed modda narration overlap zorunluluğu
    kaldırılır, yalnızca lisans/çözünürlük/aspect kontrolü yapılır.

---

## 3. Yapılan Düzeltmeler (Commit Özeti)

| Commit | Düzeltme |
|---|---|
| `b6a54f9`–`e5c0f70` | İlk dalga: probe cache, CC0/deed/NoRestrictions fix, gsrlimit=30, iiurlwidth=1920, video min 2s/loop, `loop_allowed=True`, generic fallback, manifest artifact |
| `c15a3dd` | Osmanlı/tarih kategori genişletmesi (ottoman/sailing/bizans/medieval) |
| `14ef346` | Image fit_mode=crop (black letterbox fix); video=contain |
| `bae4c8c`–`372c554` | Medikal kategori + auto-keyword removal + last-resort queries |
| `2981157`/`0fd6c8a` | visual_keywords scene queries'e enjekte; placeholder ("science X") toleransı; Anchor garbage fix (named/back/most/deep) |
| `067dbac` | ALIASES: cukur*→trench, mariana→trench (over-broad alias removed) |
| `b1c730d` | Çöl/kutup/antarktika aliases + desert/antarctica/polar kategori sorguları |
| `89bec94`/`7821107` | Emergency fallback record schema fields (assessment/media/file_probe) |
| `f37a224`/`8f1f220` | Fizik/ışık/quantum kategori + isik/foton/lazer/optik/enerji/hız aliases |
| `f8a53b9` | **En son çare katmanı**: tüm vk + title kelimeleri Wikimedia'da; relaxed evaluate (narration overlap zorunlu değil) |

---

## 4. Test Kapsamı

- `tests/test_phase4i.py`, `tests/test_phase4_media.py`: **75 geçti, 2 atlandı**
  (çevresel/fixture bağımlı olanlar)
- Sıkı güvenlik testleri korundu (örn. `test_invalid_storyboard_never_degrades_to_legacy_or_generic_query`
  tamamen alakasız narration için hala hata fırlatıyor)
- QC scripti (MAX_BLACK_RATIO=0.15, pix_th=0.05, tail_clean son 1.0sn)
  değişmeden kullanılıyor.

### Gerçek CI kanıtı
- **Faz4G run 44700976069** @ `f8a53b9` → SUCCESS (Piri Reis Haritası konusu)
  - QC: 39/39, 0 hata, 3 uyarı
  - Video: 6.91 MB, 38.57s, 1080×1920, V/A sync 0.09s
  - Black frames: 0.00s (%0.0)
- **Faz4G run 44682413882** @ `0ab08bc` → SUCCESS (İlk Uçuş konusu)
  - QC: 39/39, 0 hata
  - Video: ~7 MB, Wright Brothers/İlk Uçuş
- **Faz4G run 44670492824** @ `e5c0f70` → SUCCESS (Posta Pulları)

Önceki başarısız koşular ve teşhisleri için artifactler
(`faz4g-e2e-video-N`) ve scene_media_manifest.json kayıtları mevcuttur.

---

## 5. Kabul Kanıt Matrisi

| Kriter | Kanıt | Durum |
|---|---|---|
| Birim testleri (cookie/lisans/fallback/aliases) | `tests/test_phase4i.py` + `tests/test_phase4_media.py` | ✅ 75 pass |
| Hedefli entegrasyon (Wikimedia) | `test_wikimedia_*` | ✅ |
| Faz 4E cookie-only storyboard | run 44662520660 | ✅ |
| Faz 4G tam orkestrasyon (rastgele konu) | run **44700976069** | ✅ |
| FFmpeg montaj (loop + crop/contain) | 38.57s, V/A 0.09s | ✅ |
| Final QC (39 kontrol) | 0 hata, black %0.0 | ✅ |
| YouTube yüklemesi | skip-upload=1 | ✅ Çalıştırılmadı |
| Artifact: scene_media_manifest.json | Her koşuda artifact'e kaydediliyor | ✅ |
| Birden fazla farklı konuda başarı | Posta Pulları, İlk Uçuş, Piri Reis | ✅ |
