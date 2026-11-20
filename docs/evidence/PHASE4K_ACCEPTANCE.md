# Faz 4K Kabul Raporu — Orkestrasyon Kök Neden Analizi ve Medya Zinciri Güçlendirmesi

**Tarih (Europe/Istanbul):** 2026-11-20
**Branch:** `main` (commits: `b6a54f9` → `e5c0f70`)
**Repo:** https://github.com/ahmetbysoy/youtube_shorts_automation

---

## 1. Yönetici Özeti

Faz 4J sonrası Faz 4G uçtan uca koşuları (run `44662518260`, `44663635924`, `44664938550`)
`storyboard_media_selection_blocked` hatasıyla ve bir durumda video-ses süre uyumsuzluğuyla
başarısız oluyordu. Aynı SHA (`e117660`) ile çalışan Faz 4E cookie-only storyboard testi
(`44662520660`) başarılıydı; bu da sorunun kodda değil, **4G orkestrasyonunun gerçek
fallback senaryolarıyla karşılaştığında medya zincirinin zayıf halka** olduğunu gösterdi.

**Kök nedenler (kümülatif):**

1. **Wikimedia Commons lisans tespiti çok sıkıydı** — CC0 URL'sinde `/deed.en` veya `/deed.tr`
   dil suffix'i varsa (ki Commons'un varsayılan URL biçimi budur) lisans "doğrulanamadı"
   olarak reddediliyordu. Ayrıca müzelerin "No restrictions" / "No known copyright
   restrictions" (örn. Getty Open Content) public domain işareti kabul edilmiyordu.
2. **Wikimedia gsrlimit=6 çok küçüktü** — ilk sayfa tamamen CC BY-SA dosyalarından
   oluşuyorsa (örn. "dead sea crystals") seçim tamamen bloklanıyordu.
3. **Wikimedia thumbnail width=1440 yetersizdi** — dikey 1080×1920 videoda `min(w,h)≥720`
   kuralı geçilemiyordu (`insufficient_resolution`).
4. **Video süre kuralı çok sıkıydı** — `video.duration ≥ scene.duration` gerektiriyordu;
   6-8 saniyelik stok klipler 9+ saniyelik sahneler için reddediliyordu. Loop ile
   uzatılabileceği hesaba katılmıyordu.
5. **`loop_allowed: False`** — seçilen medya metadata'sında loop izni yoktu; kısa
   videolar FFmpeg'de `-t` ile kesilip video akışı sesten kısa kalıyordu.
6. **Browser provider boş sonuç cache'i yoktu** — cookie oturumu açık olsa bile
   (Pexels/Pixabay 403 değil ama arama sonucu dönmüyorsa) her sahne için tarayıcı
   tekrar açılıyor, 30-60 saniye boşa harcanıyordu.
7. **Jenerik fallback yoktu** — tüm sahne-özel sorgular başarısız olursa (örn.
   "science tooth", "history day" gibi anlamsız kelimeler) tüm pipeline çöküyordu.

**Sonuç:** `phase4g_e2e_no_upload.yml` koşusu **run 44670492824** olarak SUCCESS ile
tamamlandı (commit `e5c0f70`).
- ✅ 4/4 sahne medya seçimi (Pexels + Wikimedia karışımı; loop_allowed=True)
- ✅ FFmpeg cinematic montaj + altyazı + kapak
- ✅ Son QC: 39/39 kontrol geçti, 0 hata, 0 uyarı
- ✅ Video: 6.7 MB, 33.33s, 1080×1920, h264/aac, V/A sync 0.04s
- ✅ YouTube yüklemesi HİÇ çalıştırılmadı
- ✅ scene_media_manifest.json artifact'e eklendi (hata ayıklama için)

---

## 2. Kök Neden Analizi — Üç Başarısız Koşu

### 2.1 Run 44662518260 @ `e117660` (faz4k: 3 kritik hata düzeltmesi)
- **Konu:** "Çikolata Yer Çekiminin Olmadığı Yerde Farklı Erir!" (fallback)
- **Hata:** `SceneMediaError: storyboard_media_selection_blocked`
- **Kök neden:** Pexels HTTP 403 (cookie geçersiz). Pixabay de 403. Wikimedia
  Commons adaylarının tümü `missing_or_unsupported_file_license` ile elendi
  — CC0 `/deed.en` suffix ve "No restrictions" lisansları tanınmıyordu.

### 2.2 Run 44663635924 @ `fa419f1` (topic-history chore)
- **Konu:** "Roma'yı Bitiren Son İmparator Sadece 16 Yaşındaydı!" (fallback)
- **Hata:** `SceneMediaError: storyboard_media_selection_blocked`
- **Kök neden:** Aynı kod, aynı Wikimedia lisans hatası. Pexels+Pixabay ikisi de
  403, Wikimedia CC0/NoRestrictions dosyaları eleniyor. Sorgular "history only",
  "history day", "history dead" gibi çok genel kelimeler — by-sa dosyalar
  çoğunlukta ve uygun CC0 dosya kalmıyor (gsrlimit=6).

### 2.3 Run 44664938550 @ `9eea0bd` (Wikimedia CC0 lisans düzeltmesi)
- **Konu:** "Dünyanın İlk Programcısı Bir Kadındı!" (fallback)
- **Hata:** `SceneMediaError: storyboard_media_selection_blocked`
- **Kök neden:** Pexels cookie oturumu aktif ama "historical woman scientist"
  gibi sorgulara video döndürmüyor. Pixabay de boş. Wikimedia tarafında CC0 fix
  uygulanmış ama gsrlimit=6 ve iiurlwidth=1440 nedeniyle adaylar ya by-sa
  ya da `insufficient_resolution` ile eleniyor.

### 2.4 4E (44662520660) başarılı — 4G neden başarısız?
- 4E workflow'u basit, kanıtlanmış sorgular kullanır: `"cat"`, `"dog"`. Bu
  kelimeler Pexels'te binlerce yüksek kaliteli video döndürür.
- 4G ise fallback havuzundan üretilen `visual_query` ve `alternative_queries`
  kullanır. Bu sorguların çoğu ya çok genel ("science", "history") ya da
  alakasız ("history only", "science deep", "science named"). Pexels'te
  cookie 403 veya sonuç dönmediğinde tüm yük Wikimedia'ya biner, ama
  Wikimedia tarafındaki sıkı lisans/çözünürlük/süre filtreleri uygun aday
  bulamaz.

---

## 3. Yapılan Düzeltmeler

| Commit | Dosya | Düzeltme |
|---|---|---|
| `b6a54f9` | `src/media_processing/media_providers.py` | BrowserStockProvider için cookie/auth **probe cache** — kalıcı hatalarda (403/cookie_missing/captcha) her sahne tarayıcı tekrar açmaz. |
| `9eea0bd` | `src/media_processing/media_providers.py` | **Wikimedia lisans tespiti** — CC0 URL path `/publicdomain/zero/1.0` ile başlayarak kontrol (deed.XX suffix tolere edilir); "No restrictions"/"No known copyright restrictions" public domain olarak kabul edilir. |
| `9fda0b7` | `.github/workflows/phase4g_e2e_no_upload.yml` | `output/scene_media_manifest.json` artifact'e eklendi. |
| `35bfc61` | `src/media_processing/media_providers.py` | Wikimedia **gsrlimit=20** (sonra 30); Browser provider **consecutive_empty** cache (ok durumda 2+ boş sonuç sonrası tarayıcı tekrar açılmaz). |
| `e11b25d` | `src/media_processing/media_providers.py` | Wikimedia **iiurlwidth=1920** (thumbnail 1440→1920, vertical 1080p için yeterli). |
| `abcb635` | `src/media_processing/scene_media.py` | **Video süre kuralı** yumuşatıldı — min 2.0 saniye (loop ile uzatılabilir), video≥scene_duration zorunluluğu kaldırıldı. Skor: eşit/uzun=10, ≥2s=7. |
| `cd49aaa` | `src/media_processing/scene_media.py` | **Jenerik Wikimedia fallback** — son çare (space/ancient/science/nature/cinematic keyword'leri). |
| `e5c0f70` | `src/media_processing/scene_media.py` | `loop_allowed: True` — kısa videolar `-stream_loop -1` ile sahne süresince tekrar edilir (V/A sync sağlanır). |

---

## 4. Test Kapsamı

### Birim testler (lokalde çalışan)
- `test_browser_provider_probe_cache_skips_subprocess_on_permanent_error` ✅
- `test_browser_provider_transient_errors_not_cached` ✅
- `test_browser_provider_consecutive_empty_short_circuits` ✅
- `test_commons_license_accepts_cc0_with_deed_suffix` ✅
- `test_commons_license_accepts_no_restrictions` ✅
- `test_wikimedia_provider_returns_enough_licensed_results_for_common_queries` ✅
- `test_wikimedia_returns_high_resolution_candidates` ✅
- 118 Python + 4 Node testi geçti (6 test ffmpeg yokluğundan çevresel olarak başarısız).

### Gerçek CI kanıtı
- **Faz4G run 44670492824** @ `e5c0f70` → SUCCESS
  - QC: 39/39, 0 hata, 0 uyarı
  - Video: 6.7 MB, 33.33s, 1080×1920, cover 265 KB
  - Artifact: faz4g-e2e-video-25

---

## 5. Kabul Kanıt Matrisi

| Kriter | Kanıt | Durum |
|---|---|---|
| Birim testleri (cookie/lisans/fallback) | `tests/test_phase4i.py` 13/13 | ✅ Mock/offline |
| Hedefli entegrasyon (Wikimedia CC0 araması) | `test_wikimedia_*` | ✅ Gerçek HTTP |
| Faz 4E cookie-only storyboard | run 44662520660 | ✅ Gerçek sağlayıcı |
| Faz 4G tam orkestrasyon | run 44670492824 | ✅ Tam zincir |
| FFmpeg montaj (loop ile) | 33.33s, V/A 0.04s | ✅ Gerçek render |
| Final QC (39 kontrol) | 0 hata, 0 uyarı | ✅ Final QC |
| YouTube yüklemesi | skip-upload=1 | ✅ Çalıştırılmadı |
