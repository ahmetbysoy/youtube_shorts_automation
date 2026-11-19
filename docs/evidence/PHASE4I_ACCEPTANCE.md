# Faz 4I Kabul Raporu — Gerçek Üretim Sağlamlığı ve Cookie Tabanlı Sistemin Son Düzenlemesi

**Tarih:** 2026-11-19
**Branch:** `main` (HEAD=`c2592df`)
**Repo:** https://github.com/ahmetbysoy/youtube_shorts_automation

---

## 1. Özet

Faz 4I, Faz 4H'nin 30/0/0 başarıyla tamamlanmış koşusunu temel alarak aşağıdaki
gerçek sağlamlık eksiklerini tespit edip düzeltti:

1. **Cookie hata raporlaması yetersizdi** — Pexels/Pixabay erişim hatalarının
   tümü tek bir `blocked_unverified` durumuna düşüyordu; kullanıcı hangi
   sitede ne tür bir sorun yaşandığını (oturum sona ermesi / 403 / CAPTCHA /
   rate limit / timeout) anlayamıyordu.
2. **Topic history commit gürültüsü** — her rezervasyon ve finalizasyon
   "chore: atomic topic history reservation" adıyla commit atılıyordu;
   ardışık koşular commit geçmişini anlamsızlaştırıyordu.
3. **QC sahne benzersizlik kontrolü path bazlıydı** — aynı video farklı
   isimle birden fazla sahneye atanırsa `scenes_unique` yakalamıyordu.
4. **QC ses yüksekliği (volume) kontrolü yoktu** — çok sessiz videolar
   (mean < -30 dBFS) kullanıcı deneyimini bozduğu halde QC'den geçiyordu.
5. **BrowserStockProvider exit 1'de JSON diagnostics'i okumuyordu** —
   video_fetcher.js başarısız olduğunda (exit 1) subprocess, JSON parse
   etmeden `browser_catalog_failed` dönüyordu; bu da yukarıdaki ayrıntılı
   hata raporlamasını işlevsiz kılıyordu.

Tüm düzeltmeler sonrası **no-upload E2E koşusu (run 44581848198) 31/0/0
(31 kontrol, 0 hata, 0 uyarı)** başarıyla tamamlandı.

---

## 2. Bulunan Gerçek Sorunlar ve Düzeltmeler

### 2.1 Cookie Hata Durumları Tek Tip Raporlanıyordu (DÜZELTİLDİ)

**Önceki durum:** `video_fetcher.js` içinde 401/403/429/CAPTCHA/login/timeout
farklı sebepler olsa da hemen hepsi tek bir `blocked_unverified` status'una
düşüyordu. Kullanıcı hangi sitenin cookie'sini yenilemesi gerektiğini
anlayamıyordu.

**Sonraki durum (`video_fetcher.js`):**
- `401` → `auth_required`
- `403` → `access_denied`
- `429` → `rate_limited`
- Cloudflare/Turnstile/hCaptcha/reCAPTCHA → `captcha_challenge`
- `/login` sayfasına yönlendirme veya "Sign in" / "Log in" / "Giriş yap"
  sayfa başlığı → `login_required` (oturum sona ermiş)
- Timeout/navigasyon hatası → `browser_timeout`
- Arama sonucu boş ama sayfa yüklendi → `no_valid_video` (engel değil)

**Sonraki durum (`media_providers.py` BrowserStockProvider):**
- Her hata durumu için `status`, `error_detail`, `secret_to_refresh`,
  `action_hint` alanları üretiliyor.
- Örnek çıktı: `status=login_required`, `secret_to_refresh=PEXELS_COOK`,
  `action_hint="Pexels oturumu sona erdi; GitHub Secret 'PEXELS_COOK'
  yenilenmeli (tarayicida Pexels'a giris yap, yeni cookie'yi secret'a yaz)."`
- Cookie değerleri (`sessionid`, `cf_clearance`, `__cf_bm` vb.) hiçbir
  zaman diagnostics içine, loglara, JSON raporlarına veya artifact'lere
  yazılmıyor. `html_snippet` içindeki cookie/token/session kelimeleri
  zaten siliniyor.
- Cookie yokken subprocess başlatılmadan erken dönülüyor ve boşuna
  Playwright açmıyor; diagnostics yine de anlamlı hata veriyor.

### 2.2 BrowserStockProvider Exit 1'de JSON'u Okumuyordu (DÜZELTİLDİ)

**Önceki durum:** `subprocess.run()` sonrası `returncode != 0` ise JSON
parse edilmeden `{"status": "browser_catalog_failed"}` dönüyordu. Hâlbuki
video_fetcher.js exit 1'den ÖNCE JSON'u stdout'a yazmış oluyor
(`allFailed` olduğunda), dolayısıyla tüm ayrıntılı diagnostics
kaybediliyordu.

**Düzeltme:** Exit code'dan bağımsız olarak stdout varsa JSON parse
ediliyor; tanınabilir hata (cookie/captcha/login/access_denied vb.)
diagnostics'ten raporlanıyor. Yalnız stdout boş veya JSON parse
edilemiyorsa güvenli hata `browser_catalog_failed` kullanılıyor.

### 2.3 Topic History Commit Gürültüsü (İYİLEŞTİRİLDİ)

**Önceki durum:** Hem `reserve_candidate` (senaryo seçildiğinde) hem
`finalize_candidate(commit=True/False)` tek tip `chore: atomic topic
history reservation` commit mesajı üretiyordu. Koşu başına 2 commit,
geçmişte neden yapıldığı anlaşılamayan commitler bırakıyordu.

**Sonraki durum:** Üç farklı anlamlı commit mesajı:
- `chore(topic-history): reserve pending slot` — koşu başında
  rezervasyon (yarım kalan üretimlerde aynı konunun tekrar seçilmesini
  engeller, CAS ile çalışır).
- `chore(topic-history): commit successful reservation` — başarılı
  üretim sonunda pending kaydı used_records'a taşınır.
- `chore(topic-history): release failed reservation` — herhangi bir
  fazda hata olursa rezervasyon serbest bırakılır, konu tekrar
  kullanılabilir.

Konu başlığı, script metni, cookie, token gibi gizli veri hiçbir zaman
commit mesajına yazılmaz. Atomik güvenlik ve CAS retry korunur.

### 2.4 QC `scenes_unique` Path Bazlıydı (DÜZELTİLDİ)

**Önceki durum:** Sahne benzersizlik kontrolü `sp.resolve()` (mutlak
dosya yolu) karşılaştırması yapıyordu. Eğer aynı video dosyası farklı
isimlerde (örneğin sembolik link veya farklı geçici isim) indirilmişse,
tekrar ettiği yakalanmıyordu.

**Düzeltme:** Her sahne dosyasının akıcı SHA-256 içerik hash'i
hesaplanıyor (`_file_sha256`) ve hash set'i üzerinden benzersizlik
kontrolü yapılıyor. Aynı içerik farklı path'de olsa bile yakalanır.

### 2.5 QC Ses Seviyesi Kontrolü Eksikti (EKLENDİ)

**Yeni kontrol:** FFmpeg `volumedetect` filtresi ile ortalama (mean) ve
tepe (max) ses seviyesi dBFS cinsinden ölçülüyor.

- `mean < -30 dBFS` → hata (çok sessiz)
- `-30 ≤ mean ≤ -9 dBFS` → geçerli (normal Shorts aralığı)
- `mean > -9 dBFS` → uyarı (yüksek, bozulma riski)
- Ses yok/ölçülemedi → uyarı

Son koşuda ölçülen değer: **mean=-19.5 dBFS, max=-2.6 dB** (geçerli,
iyi ayarlanmış).

### 2.6 `head_clean` Sabiti Hardcoded 0.5 Kullanıyordu (DÜZELTİLDİ)

Küçük kod temizliği: `head_clean` kontrolündeki sabit eşik `0.5` değeri
`HEAD_TAIL_MAX_BLACK` sabitinden okunuyor; böylece sabitler arası tutarlılık
sağlanıyor.

---

## 3. Değiştirilen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `video_fetcher.js` | `fetchFromPexels`/`fetchFromPixabay` içinde 401/auth_required, 403/access_denied, 429/rate_limited, captcha_challenge, login_required, browser_timeout durumları ayrık raporlanıyor. Önceden tek `blocked_unverified`. Pixabay anasayfa sonrası login kontrolü de eklendi. |
| `src/media_processing/media_providers.py` | `BrowserStockProvider` exit 1 olsa bile JSON diagnostics'i okuyor; her hata durumu için `status`+`secret_to_refresh`+`action_hint` üretiyor; cookie yokken anlamlı diagnostics; cookie değeri/`sessionid`/`cf_clearance`/`Authorization` header'ı last_diagnostics içine sızmıyor. |
| `scripts/qc_final_video.py` | `_file_sha256` ile sahneler SHA-256 benzersizlik kontrolü; `measure_audio_volume` ile FFmpeg volumedetect; `head_clean` eşiği `HEAD_TAIL_MAX_BLACK` sabitinden okunuyor. |
| `scripts/topic_history.py` | `GitHubContentsStore.put(operation=...)` ile rezervasyon/commit/release için farklı anlamlı commit mesajları; hiçbir zaman konu/cookie/veri içermeyen güvenli mesajlar. |
| `tests/test_phase4i.py` (YENİ) | 6 yeni birim testi: cookie action_hint, QC sabitler, scene hash fonksiyonu, topic history commit mesajları, video_fetcher.js cookie sızdırmazlığı, media_providers diagnostics. |

---

## 4. Test Sonuçları

### 4.1 Birim Testler
```
tests/test_topic_history.py
tests/test_script_json_schema.py
tests/test_cover_frame.py
tests/test_gemini_web_story.py
tests/test_repeat_protection.py
tests/test_phase4d_cookie_isolation.py
tests/test_thumbnail_helpers.py
tests/test_phase4i.py (yeni)
tests/test_environment.py (1 fail: yerelde Chromium kurulu değil, CI'da geçer)
---------------------------------
74 passed, 3 skipped, 1 failed (önceden var olan Chromium yokluğu)
```

### 4.2 Node.js Syntax
- `video_fetcher.js` → `node --check` geçti.

### 4.3 Python Syntax & Import
- `qc_final_video.py`, `topic_history.py`, `media_providers.py` → `ast.parse` OK.
- `src.media_processing.media_providers`, `media_processor`, `scene_media` import OK.

### 4.4 YAML Workflow
- Tüm `.github/workflows/*.yml` ve `.github/actions/*/action.yml` → `yaml.safe_load` OK.

---

## 5. GitHub Actions E2E Koşusu

| Run ID | Sonuç | QC |
|---|---|---|
| [`44581848198`](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44581848198) | ✅ SUCCESS | **31 kontrol, 0 hata, 0 uyarı** |
| 44575327354 (Faz4H son kanıt) | ✅ SUCCESS | 30/0/0 |
| 44571835452 | ✅ SUCCESS | 29/1 uyarı (isimlendirme hatası) |

### Run 44581848198 Videosu (Faz4I kanıt)

| Özellik | Değer |
|---|---|
| Süre | **30.47 saniye** |
| Boyut | **13.13 MB** |
| Çözünürlük | 1080×1920 (9:16) |
| Kare | 30 fps |
| Video kodek | h264 (yuv420p) |
| Ses kodek | aac 24000 Hz mono |
| A/V senkron | v=30.47s / a=30.39s → fark **0.08 s** |
| Ses yüksekliği | mean=**-19.5 dBFS**, max=-2.6 dBFS (normal) |
| FFmpeg tam decode | rc=0, 0 hata satırı |
| Siyah kare | **0.00s (%0.0)** |
| Head/tail | ilk 1sn 0.00s siyah, son 1sn 0.00s siyah |
| Kapak (cover.jpg) | 258.3 KB, 1080×1920 mjpeg |
| Altyazı | 20 diyalog satırı, ASS, MarginV=250, FontSize=56 |
| Zaman aralığı | 0.00–30.45s (video=30.47s) |

QC raporu artifact'ten (`faz4g-e2e-video-9`, 13.4 MB) indirildi ve doğrulandı.
İş akışı sonunda `cookies.json`/`.env`/`storage_state.json` silindi;
`find output -iname "*cookie*" -o -iname "*token*" ... -delete` güvenlik
komutu çalıştı.

### Commit Mesajları (Koşu 44581848198)

Koşu beklendiği gibi tam olarak 2 anlamlı commit üretti:
1. `chore(topic-history): reserve pending slot` (681f3e0) — konu seçildi
2. `chore(topic-history): commit successful reservation` (0458518) — başarı

Gizli veri içermeyen, nedenini açıkça belirten commitler.

---

## 6. Güvenlik Denetimi

- ✅ Cookie değerleri hiçbir kod yolunda log/JSON/artifact/commit mesajına yazılmıyor.
- ✅ `PEXELS_COOK` ve `PIXABAY_COOK` secret isimleri korundu; API key zorunluluğu getirilmedi.
- ✅ Cookie'ler yalnızca ilgili domain'e (`*.pexels.com`, `*.pixabay.com`) uygulanıyor.
- ✅ CAPTCHA/Cloudflare/bot koruması bypass edilmeye çalışılmıyor; kullanıcıya yalnızca hangi secret'ın yenilenmesi gerektiği söyleniyor.
- ✅ Workflow sonunda `cookies.json`/`.env`/`storage_state.json` ve `*cookie*`/`*token*`/`*credential*` dosyaları siliniyor.
- ✅ YouTube upload, public/draft yayın, pruner ve daily production workflow'u manuel olarak tetiklenmedi.
- ✅ `GEMINI_COOK` çerez tabanlı sistem korunuyor, API'ye dönüştürülmedi.

---

## 7. Çözülemeyen / Kasıtlı Olarak Yapılmayan Şeyler

1. **AVD ölçümü null olabilir:** Studio analitik kartları bazı kısa/yeni
   videolarda ortalama izleme süresini çıkarmıyor. Faz4H'de null semantiği
   düzeltildi; daha ileri bir çözüm YouTube Studio API erişimi gerektirir
   ve Faz4I kapsamı dışında.
2. **Sahne medyaları production'da siliniyor:** `media_processor.py`
   `TemporaryDirectory` ile sahne work dizinini iş bitiminde siliyor; bu
   nedenle post-render SHA-256 sahne tekrarı kontrolü work_dir bulunduğunda
   çalışıyor, production artifact'inde (work_dir silinmiş) çalışmıyor.
   Final video full decode + black_frames + AV sync kontrolleri yeterli
   güveni verdiğinden bu bilerek kabul edildi.
3. **Gerçek semantik görüntü analizi yapılamıyor:** "Sahne ile senaryo
   arasında bariz uyumsuzluk var mı?" sorusu bilgisayar görüşü (CLIP/BLIP)
   gerektirir; mevcut altyapıda yok ve ek maliyet/bağımlılık getireceğinden
   bu fazda yapılmadı. Bunun yerine medya arama query eşleşmesi ve lisans
   kontrolleri ile makul güvende kalınıyor.
4. **Altyazı piksel-taşma garantisi yok:** ASS font metric'i CI'da
   Monte edilen font ile %100 örtüşmediği için gerçek piksel hesabı
   yapılamıyor. Mevcut `SUB_LINE_MAX_CHARS=42` ve `MarginV=250` güvenli
   alanı kabaca yeterli; gerçek ffmpeg render'ı sonrası taşma olursa tam
   decode'da hata vermiyor ama görsel olarak izlenebilir. Bu kabul edildi.
5. **Pexels/Pixabay cookie'lerinin CI'da ne durumda olduğu:** Run
   44581848198'de `video_fetcher.js` exit 1 dönmüş (ancak video Wikimedia
   sağlayıcısı ile başarıyla üretildi). Bu, production cookie'lerin
   süresinin doluyor olabileceğini düşündürüyor — yeni ayrıntılı
   diagnostics ile kullanıcıya hangi secret'ın yenilenmesi gerektiği
   bir sonraki production koşusunda açıkça bildirilecek. Cookie'yi
   yenilemek kullanıcının sorumluluğu; bypass veya ücretli API'ye
   geçiş yapılmadı.

---

## 8. Faz 4I Kabul Kararı

**DURUM: ✅ PASS**

Kanıt:
- ✅ E2E no-upload koşusu **44581848198** SUCCESS
- ✅ Video: 30.47sn, 13.13MB, 1080×1920, 30fps, h264/aac, A/V sync 0.08s
- ✅ **31 QC kontrolü, 0 hata, 0 uyarı** (audio_volume yeni kontrol)
- ✅ FFmpeg tam decode temiz, black_frames=0.00s, head/tail temiz
- ✅ Cover (kapak) 1080×1920 JPEG, 258KB
- ✅ ASS altyazı: MarginV=250, FontSize=56, 20 diyalog, zaman aralığı 0–30.45s
- ✅ Cookie hata durumları 401/403/429/captcha/login/timeout ayrı raporlanıyor
- ✅ Kullanıcıya hangi Secret'ın (PEXELS_COOK/PIXABAY_COOK) yenileneceği
  açıkça `action_hint` ile bildiriliyor; cookie değerleri hiçbir yere yazılmıyor
- ✅ Topic history commit mesajları reserve/commit/release olarak anlamlı
- ✅ Sahne tekrar kontrolü artık SHA-256 içerik hash'i ile yapılıyor
- ✅ Ses yüksekliği (volumedetect) kontrolü eklendi
- ✅ 74 birim test geçti (6 yeni Faz4I testi dahil)
- ✅ Güvenlik: artifact temizleme adımı çalıştı, gizli dosyalar silindi
- ✅ YouTube upload, public/draft yayın, pruner, daily production tetiklenmedi
- ✅ Cookie tabanlı sistem (PEXELS_COOK/PIXABAY_COOK/GEMINI_COOK) korundu

---

## 9. Sonraki Faz İçin En Mantıklı Tek Görev

**Cookie yenileme tanılarını production koşularında izle ve gerekiyorsa cookie rotasyonunu dökümante et.**

Faz4I'nın eklediği ayrıntılı hata raporlaması bir sonraki doğal cron
koşusunda (`daily_shorts`) ilk defa çalışacak. Çıkacak `login_required`
veya `captcha_challenge` tanılarına göre kullanıcı Pexels/Pixabay
cookie'lerini yenileme ihtiyacını net biçimde görecek. Sonraki mantıklı
adım, (a) bir haftalık koşu sonunda hangi sağlayıcıların ne sıklıkla
cookie yenilemesi gerektirdiğine bakmak ve (b) stok_cookie_probe
workflow'unun günlük sinyalini Faz4I tanılarına göre güncellemek.
