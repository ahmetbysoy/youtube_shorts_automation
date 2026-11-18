# YouTube Shorts Automation — Tam Otonom İçerik Fabrikası

> **Güncel Faz 4C — 2026-11-18: Faz4B NOT_ACCEPTED, Faz5 başlamadı.** Kaynak [`14f7896`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/14f78962f2444e9d03fe0d0caf9b22efff06d927); yeni CI [44313713933](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313713933) **361 Python + 16 alt test**, hedefli tekrar **35/182/8**, **16 Node** geçti. Kullanıcının yeni cookies’i **API kullanılmadan** [44313751238](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313751238) Actions koşusunda test edildi: preflight **8 Pexels + 7 Pixabay eşleşen cookie kaydı**, iki ayrı browser araması **HTTP403 / blocked_unverified**. Commons iki CC BY videoda source/deed/download **200**, tam byte/SHA256 ve container probe geçti; **full_decode_failed**, render/final QC not_reached. API/ENV_FILE bu run’da okunmadı; API key eksikliği cookie testi için blocker değildir. Yeşil CI/offline fixture veya eski yerel Commons, yeni canlı kabul yerine geçmez. Önceki iki-run history/gerçek409 proof’unun üç blob’u aynı; cleanup dört404 ile salt-okur tekrar doğrulandı, yeniden dispatch edilmedi. **22 protected blob, 26 topic/0pending** korundu; üretim/yayın/silme yok. [12 başlıklı yeni rapor](docs/evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) · [JSON](docs/evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json).

> **Tarihsel Faz4B snapshot’ı:** Kaynak `59e2c79`, CI44301070745 **301+16/35/122/8/11Node**; eski yerel canlı Commons tam zinciri geçti, eski Actions44301095341 stock403 ve generic Commons download/decode failure verdi. Bu eski kayıtlar yeni koşu değildir; [Faz4B raporu](docs/evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) ve [JSON](docs/evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json) değiştirilmeden korunur.

> **Tarihsel Gemini Faz 4 — 2026-11-18: uygulama var, TAM KABUL GEÇMEDİ.** Son kod [`e4d1144`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/e4d1144116887b31c459bb6a7e171589d214c687); Ubuntu 26 CI [44288761602](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761602) **233 Python + 16 alt test**, ayrı **62** Faz 4 testi ve **5** Node parser testiyle geçti. Yayınsız canlı [44288761461](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761461) yeşil ama **partial_provider_evidence**: Commons iki ayrı sahnede gerçek lisans/download/decode + 6 sn consumer MP4 geçti; Pexels/Pixabay koşu env’inde API key yok, cookie dosyası var, browser aramaları **HTTP 403**. Metadata eşleşmesi görsel anlam doğrulaması değildir; sentetik ton TTS değildir. Legacy/Commons/Faz 3/PUBLIC-uploader davranışı korundu; üretim/publisher/pruner tetiklenmedi. [Kanıt ve kabul açıkları](docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md), [tasarım](docs/PHASE4_MEDIA_ENGINE.md).


> **Güncel durum — 2026-11-18:** **Gemini Faz 3 kabul kapısı geçti.** Kod `0dee88e` üzerinde Ubuntu 26 CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) başarılı: **171 Python testi + 16 alt test**, ayrıca 35 hedefli Faz 3 testi. İki ayrı Actions koşusu [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) (`reserve`) ve [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) (`verify`) kalıcı rezervasyonu yazdı, sonraki koşuda okuyup serbest bıraktı. Mevcut 25 başlık korundu; test başlığı kullanım geçmişine eklenmedi. Exact quote, muhafazakâr deterministik ilişki/sayı-birim denetimi ve Wikipedia HTTP/canonical sayfa kimliği kontrolleri ayrı değerlendirilir. Önceki gerçek Gemini Web probe **44262444017** (58 kelime, 5 sahne, 3 claim; `draft_only=true`, `publish=false`) korunur; yeni kod için canlı model/YouTube yayın kanıtı değildir. Cookie-only/fallback, secret’lar ve kullanıcı onaylı `partial` yayın politikası değişmedi; `partial`, `verified` diye etiketlenmez. Bu doğrulamada üretim/publisher/pruner workflow’u tetiklenmedi. [Actions kanıt raporu](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md), [TODO](docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md), [plan](docs/GEMINI_AUTONOMOUS_SHORTS_PLAN.md), [mimari](docs/ARCHITECTURE.md).

> Faz 15: 08:39 UTC envanterinde 58 PUBLIC + 3 taslak; PUBLIC videoların kapakları ve örnek kareleri, taslakların önizlemeleri incelendi. Baştan sona ses/olgu doğrulaması yapılmadı. Özel kapaklar günlük kota nedeniyle değiştirilmedi; #123 otomatik YouTube kapağıyla PUBLIC, iş başarılı fakat workflow iptal. Gemini kare kabulü yanlış eşleşme nedeniyle varsayılan kapalıdır. 58 yüklenmemiş temsili kapak adayı hazırlandı; ikisinin konusu otomatik altyazıya dayanır ve doğrulama bekler. [Canlı plan/TODO](docs/FAZ15_TAM_OTONOM_KANAL_VE_KAPAK_TODO.md).

> Faz 15 canlı plan/TODO: [Kanalın tek tek incelenmesi, kapak yenileme ve otonom sistem](docs/FAZ15_TAM_OTONOM_KANAL_VE_KAPAK_TODO.md).

> **Güncel operasyon notu (5 Kasım 2026):** Kullanıcı seçimiyle 26 mevcut taslak PUBLIC yayınlandı; silme yapılmadı. [Video kanıtları](docs/evidence/draft_publications_2026-11-05.md). İki başlık `final short`; tekrar, görsel eşleştirme ve açıklama kalitesi TODO. Aktif pruner politikası değiştirilmedi. Aşağıdaki eski faz özetleri tarihsel olabilir; tek kanal ve güncel TODO için `AI_HANDOFF.md` ve Faz 13 planına bakın.

> Faz 14 ilk kod: `GEMINI_FREE_VISION_ENABLED` kod varsayılanı `0`, bu depoda `1`; gerçek tek kare API testi başarılı; Studio üzerinde yeni kapak henüz doğrulanmadı. Mevcut kareler uygun değilse temsili yerel kapak. Ücretli görsel üretimi yapılmaz. Projeye billing bağlanırsa text/vision istekleri ücretlenebilir; bu durumda değişkeni `0` yapın.

> Faz 14 güncel plan: [ücretsiz Gemini kare değerlendirmesi ve yerel yedek](docs/FAZ14_FREE_GEMINI_KAPAK_PLANI.md); ücretli görüntü üretimi kullanıcının tercihi nedeniyle kapalı.

Python, FFmpeg ve Node.js Playwright tabanlı, GitHub Actions üzerinde Türkçe Shorts üretip PUBLIC yayınlamayı amaçlayan sistem. Ücretsiz katmanlar ve YouTube kotaları sınırlıdır; maliyet ve sıfır manuel müdahale garantisi verilmez. Güncel durum ve açık doğrulama eksikleri için Faz 15 TODO’ya bakın.

> 🤖 **Projeyi Devralacak Yapay Zeka / Geliştirici İçin İlk Adım:**  
> Tüm sistem durumu, kimlik/oturum dosyalarının Google Drive & GitHub Secrets konumları, kritik güvenlik kuralları ve çözülmüş teknik tuzaklar için önce **[`AI_HANDOFF.md`](./AI_HANDOFF.md)** ve **[`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)** belgelerini okuyun.

---

## Tamamlanan Fazlar ve Sistem Özeti

| Faz | Modül | Açıklama | Durum |
| :---: | :--- | :--- | :---: |
| **Faz 1** | `youtube_auth.py`, `src/youtube_upload/` | Headless/bulut uyumlu OAuth2 PKCE akışı ve YouTube Data API v3 yedek yükleme modülü | ✅ |
| **Faz 2** | `content_engine.py`, `scripts/gemini_web_story.py` | Cookie-only Gemini Web, free Wikipedia HTTP araştırması, JSON/quote/storyboard sözleşmesi; gerçek taslak kanıtı [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017); paid text API yok, cookie failure'da mevcut fallback | ✅ (eski live probe) |
| **Gemini Faz 3** | `scripts/semantic_fact_check.py`, `scripts/topic_history.py`, `daily_shorts.yml` | Exact quote’tan bağımsız muhafazakâr ilişki/sayı-birim denetimi; Contents API SHA-CAS rezervasyonu; Ubuntu 26 CI ve iki ayrı Actions koşusunda kalıcılık/release başarılı | ✅ (yayınsız kabul) |
| **Gemini Faz 4** | `media_providers.py`, `scene_media.py`, `media_io.py`, `media_history.py` | Strict storyboard query/alternatives, lisans/atıf, ölçüm/decode, 1:1 manifest/dedup; Commons canlı, stock blocked | 🟡 Kabul geçmedi |
| **Medya Faz 3 (legacy)** | `src/media_processing/media_processor.py` | Dikey stok video indirme (Pexels / Pixabay / Wikimedia), pop-animasyonlu `.ass` altyazı, arka plan müziği miksajı ve tek geçişli `1080x1920` (30 FPS, H.264/AAC) FFmpeg montajı | ✅ |
| **Tarihsel Faz 4 (uploader)** | `src/youtube_upload/youtube_uploader.py` | Resumable API yükleme ve onay kuyruğu altyapısı (`22/22` birim testi) | ✅ |
| **Faz 5** | `youtube_studio_uploader.js` | API kotasını (`10.000 birim`) tamamen aşan Playwright Chromium YouTube Studio yükleyicisi + kalıcı oturum (`cookies.json`, `storage_state.json`) | ✅ |
| **Faz 6** | `main.py`, `.github/workflows/daily_shorts.yml` | Tüm fazları tek komutta zincirleyen Ana Orkestratör ve GitHub Actions `ubuntu-latest` + `Xvfb` bulut otomasyonu | ✅ |
| **Faz 7** | `daily_shorts.yml`, `youtube_studio_uploader.js`, `scripts/rotate_cookies.py` | Doğrudan **`PUBLIC` (Herkese Açık)** otomatik yayın; kanal matrisi 10 kanalı `max-parallel: 1` ile sırayla işler; 14 günlük Cookie/StorageState rotasyon aracı | ✅ |
| **Faz 8** | `content_engine.py`, `media_processor.py`, `main.py`, `daily_shorts.yml` | **15-Minute Blitzkrieg Sniper Modu:** MD5/zaman tabanlı 15dk benzersizlik garantisi (`23` asal senaryo havuzu), mobil-optimize sinematik FFmpeg (`unsharp` + `eq` + `MarginV=250`) ve `concurrency` kuyruk kilidi | ✅ |
| **Faz 9** | `content_engine.py`, `youtube_studio_uploader.js`, `analytics_scraper.js`, `daily_analytics.yml` | **Monetizasyon & Analitik Geri Bildirim Döngüsü:** Konu bazlı otomatik `affiliate_link` / CTA enjeksiyonu (açıklamanın en üst satırı) ve her sabah YouTube Studio izlenme/AVD verisini kazıyıp kazanan nişi (`%80` ağırlıkla) besleyen otonom analitik döngüsü | ✅ |

---

## Hızlı Kurulum ve Çalıştırma

### 1. Sistem ve Dil Bağımlılıkları (Debian / Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg fonts-montserrat fonts-liberation fonts-dejavu-core libass9 xvfb

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm install
npx playwright install --with-deps chromium
```

### 2. Ortam ve Oturum Dosyaları

`.env.example` dosyasını `.env` olarak kopyalayın (veya devir teslim yedeğindeki `.env`, `cookies.json` ve `storage_state.json` dosyalarını kök dizine yerleştirin):

```bash
chmod 600 .env cookies.json storage_state.json
```

Üretim içerik hattı `GEMINI_COOK` JSON cookie değerini ortam değişkeninden kullanır. Bu değer Git'e, loglara veya artifact'lere yazılmamalıdır. Cookie eksik/geçersiz ya da Gemini yanıtı uygunsuzsa metin sağlayıcısı olarak ücretli API çağrılmaz; içerik motoru mevcut fallback havuzuna döner.

**Stok video cookie'leri:** `video_fetcher.js` Pexels ve Pixabay'den video aramak/indirmek için `PEXELS_COOK` ve `PIXABAY_COOK` ortam değişkenlerini (veya geriye dönük uyumluluk için kökteki `cookies.json` / `storage_state.json` dosyalarını) kullanır. Cookie formatı üç seçenekten biri olabilir: Playwright storage_state içindeki `cookies` JSON dizisi, `[{name,value,domain,...}]` Netscape JSON dizisi, ya da `"name=value; name2=value2"` düz string. Playwright Chromium headless modda Cloudflare "Just a moment..." doğrulamasını gerçek tarayıcı gibi otomatik geçer; `curl` ile aynı deneme yapılırsa TLS parmak izi nedeniyle 403 döner. Cookie geçersizse veya arama başarısız olursa video kaynağı otomatik olarak Wikimedia Commons fallback'ine düşer.

### 3. Uçtan Uca Üretim ve `PUBLIC` Yayın

```bash
# Sanal ekran (Xvfb) ile tam tarayıcı bütünlüğünde çalıştırma:
xvfb-run -a --server-args="-screen 0 1366x900x24" python main.py
```

### 4. Birim Testlerini Çalıştırma

```bash
python -m pip install -r requirements-test.txt
env -u GITHUB_REPOSITORY -u GH_TOKEN -u GITHUB_TOKEN python -m pytest -q tests
npm test
node --test tests/stock_media_catalog.test.cjs
npm run test:syntax
```

---

## Gemini Faz 4 — strict sahne-medya yolu

- `storyboard` anahtarı varsa her sahne ayrı `visual_query`, en fazla 3 sıralı `alternative_queries` ve `narration` ile değerlendirilir. Boş/bozuk board veya tükenen sorgular legacy/random klibe dönmez; montaj durur. Storyboard **yoksa** eski Playwright → Pexels → Pixabay → Commons yolu aynen kalır (eski eksikleri strict doğrulanmış sayılmaz).
- Pexels/Pixabay API + source-page metadata Playwright ve Commons ortak source/media ID/URL, gerçek boyut-süre-oran, license evidence, attribution ve download durumu döndürür. Her query'de sağlayıcı havuzu global puanlanır; indirme başarısı tek başına kabul değildir. Eksik/uyumsuz lisans, atıf, subject kanıtı veya teknik koşul güvenli ret.
- Seçim/ret ayrıntısı `output/scene_media_manifest.json` ve `script.json.scene_media/media_selection` içine yazılır. Required credit tam korunur; unchanged uploader'ın CTA/hashtag eklemesi ve JS UTF-16 kesmesi için de güvenli bütçe ayrılır. Public-domain LicenseUrl yoksa uydurulmaz; BY-SA/NC/ND downstream policy olmadan otomatik kabul edilmez.
- İç-video ID/URL/dosya-hash tekrarları reddedilir; ayrı `.media_history.json` yakın dönem tekrara ceza verir. Local atomic lock / optional Contents SHA-CAS var; Faz 4B’de izole ref/path üzerinde gerçek iki-Actions history, kontrollü HTTP 409/reread/merge ve cleanup kanıtlandı ([44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963) → [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849)). Hash-only recent hit artık en fazla dört indirilen uygun aday arasında measured rerank yapar. Bu distributed reservation değildir. Faz 3 topic history değişmedi.
- Minimum çözünürlük/oran/süre ve tam dosya decode kapıları var; strict framing contain/pad, video loop yok. Relevance **metadata_supported**, visual verification **not_performed**. Scene süreleri word-weighted provisional; gerçek TTS alignment, motion/era anlam doğrulaması ve bütünleşik yayın QC tamamlanmadı.

[Eski davranış envanteri](docs/PHASE4_MEDIA_BASELINE.md) · [ayrıntılı kontrat/puanlar/sınırlar](docs/PHASE4_MEDIA_ENGINE.md) · [canlı ve mock kanıt ayrımı](docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md) · [Faz 1 ek tüketici envanteri](docs/PHASE1_SCRIPT_JSON_INVENTORY.md#7-2026-11-18-faz-4--genişletilmiş-statik-üreticitüketici-taraması).

**Test güvenliği:** `main.py` PUBLIC yayın yapar; `daily_shorts.yml`, pruner ve draft publisher test amacıyla çalıştırılmaz. `media_processor.py` gerçek bir `--help` parser'ı içermez: **`--help` bile montaj başlatır**, benign smoke diye kullanmayın. Güvenli CLI `python -m scripts.phase4_media_probe --help`; gerçek provider kanıtı ayrı `phase4_media_probe.yml` ile, source/secret denetimi sonrası alınır. Tarihsel Faz 4 probe’u partial iken yeşildi; yeni Faz 4B workflow’u eksik zorunlu provider coverage için nonzero verir. CI yeşili veya yerel Commons başarısı Actions stock/Commons kabulü değildir. Yerel yanlış media `--help` çağrısının örnek-dosya yan etkisi geri alındı; [rapor §6](docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md#6-güvenlik-ve-test-komutu-düzeltmesi).

---

## GitHub Actions Otomasyonu ve Sıralı Kanal Matrisi

`.github/workflows/daily_shorts.yml` güncel yapılandırmada iki saatlik cron (`13 */2 * * *`) ve `workflow_dispatch` ile çalışır. Kanal işlerini `max-parallel: 1` ile sıralar.

1. Üretim adımı `GEMINI_COOK` Repository Secret'ını doğrudan process env'e verir; cookie değeri dosyaya/loga/artifact'e yazılmaz.
2. `main.py` → `content_engine.py --gemini-web-only` yolunda cookie tabanlı Gemini Web taslağı dener. Kaynak REST summary'si ve canonical article URL'si HTTP ile kontrol edilir; title/page identity, exact quote, script span ve storyboard doğrulanır. Exact quote tek başına semantic support sayılmaz: deterministik relation/lexical ve tarih/sayı/birim kontrolleri claim başına kaydedilir. Ücretli text API fallback'i yok; mevcut local fallback korunur.
3. V2 `fact_check` yeni `verified`, `partial`, `rejected`, `unavailable` durumlarını kabul eder; eski enumlar geriye uyumlu. Kritik unsupported claim üretimi durdurup mevcut fallback/reselection yoluna döner. `partial` etiketleri `verified`'e çevrilmez; kullanıcının mevcut `partial` yayın hattı onayı ve uploader sırası değişmedi.
4. `.used_topics.json` geçmiş başlıklarını koruyan v2 store `used_titles`, topic/category/entity/core-claim/scenario fingerprints ve `pending` içerir. Actions üretiminden önce Contents API SHA-CAS rezervasyonu yapılır; orchestrator başarısında commit, başarısızlığında release; 30 dk TTL ve kontrollü SHA retry vardır. Yerel seçimlerde `.used_topics.json` unreadable ise fail-closed. Bu değişiklik sonrası production workflow'u çalıştırılmadı.
5. Faz 3 hedefli suite **35 passed**; yeni kod CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) üzerinde tam suite **171 passed + 16 subtests passed**. Gerçek Wikipedia HTTP kontrolü HTTP 200 ve canonical sayfa eşleşmesi verdi. Yayınsız iki-run kalıcılık testi [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) → [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) başarılı; `pending` 0 → 1 → 0, eski 25 başlığın hash’i aynı. [Kanıt ve sınırlar](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md). Daily üretim hattının gerçek yayın/finalize uçtan uca testi bu kabulün kapsamı dışındadır.

---

## Gizli Bilgiler ve Güvenlik

`.env`, `cookies.json`, `storage_state.json`, `*.har`, `client_secret*.json` ve `*token*.json` dosyaları `.gitignore` ile koruma altındadır; **asla** Git deposuna eklenmez. Bulut ortamında yalnızca şifreli **GitHub Repository Secrets** ve özel **Google Drive** yedekleri kullanılır.

---

## Faz 10 — Otonom "Ölü Ağırlık" Temizliği (Auto-Pruner, Saatlik)

`.github/workflows/hourly_pruner.yml` iş akışı **her saat başı (`cron: '0 * * * *'`)** devreye girer, 10 kanallı matrisle (kanal `1..10`, `fail-fast: false`) YouTube Studio'ya girer ve **ilk 1 saatini geçmiş + 100 izlenmenin altında kalmış** videoları kalıcı olarak siler.

### Çalışma Mantığı (`prune_low_performers.js`)

| Adım | Gerçek YouTube Studio Yapısı (canlı kanalda doğrulandı) |
| :--- | :--- |
| **Video Satırları** | `ytcp-video-row` (her satırda `#video-title`, `a[href*="/video/{ID}"]`) |
| **İzlenme Sütunu** | `.tablecell-views` (Türkçe sayı biçimi: `1.234`, `1,2 B`, `3,4 Mn`) |
| **Yayın Tarihi Sütunu** | `.tablecell-date` (`3 Kas 2026` + `Yayınlandı` / `Yüklendi`) |
| **Seçenek Menüsü** | `ytcp-icon-button.open-menu-button` (`aria-label="Seçenekler"`) |
| **Silme Kalemi** | `tp-yt-paper-item[test-id="delete"]` (metin: **"Tamamen sil"**) |
| **Onay Penceresi** | `ytcp-video-delete-dialog` → `#confirm-checkbox #checkbox` (kalıcılık onayı) → `#confirm-button` |

### Yaş (Süre) Çözümleme — 3 Katmanlı, Asla Erken Silme Garantili

1. **Kanal RSS yayını** (`https://www.youtube.com/feeds/videos.xml?channel_id=...`) → kesin ISO yayın zamanı.
2. **`prune_state.json`** (ilk görülme kaydı) → gözlem tabanlı kesin yaş (gizli videolar için de çalışır).
3. **Studio tarih sütunu** → göreli (`3 saat önce`) veya mutlak tarih; mutlak tarihte video günün **en geç 23:59'unda** yayınlanmış sayılır (asla erken silinmez).

### Emniyet Kilitleri (Env ile ayarlanabilir)

| Değişken | Varsayılan | Açıklama |
| :--- | :--- | :--- |
| `PRUNE_MIN_VIEWS` | `100` | Bu izlenmenin altındakiler hedeflenir |
| `PRUNE_MIN_AGE_MINUTES` | `60` | İlk 1 saatteki videolar **dokunulmaz** |
| `PRUNE_MAX_DELETIONS` | `10` | Tek çalıştırmada silme üst sınırı |
| `PRUNE_MIN_REMAINING` | `1` | Kanalda bırakılacak en az video |
| `PRUNE_DRY_RUN` | `false` | `true` ise yalnızca raporlar, silmez |

### Çıktılar

- `prune_report.json` → tarama/HD/KORUNDU/silme raporu (artifact + repo'ya yazılır).
- `prune_state.json` → video ID → ilk görülme zamanı (yaş çözümleme hafızası).
- Log satırları: `[!] HEDEF TESPİT EDİLDİ: ...`, `[+] BAŞARILI: '...' kalıcı olarak silindi.`, `[*] KORUNDU: ...` ve `🚀 TEMİZLİK TAMAMLANDI: X adet düşük performanslı video imha edildi. 🚀`

### Manuel Tetikleme

```bash
curl -X POST -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/hourly_pruner.yml/dispatches \
  -d '{"ref":"main","inputs":{"target_channel":"1"}}'
```

---

## Faz 11 — Viral Metadata, AI Kapak (Thumbnail) ve Cron Kilidi Kırma

### 1) Viral Metadata Üretimi (`content_engine.py`)

LLM istemi artık metinle birlikte **algoritma hackleme metadatası** da üretir:

| Alan | Açıklama |
| :--- | :--- |
| `hook` | İlk 3 saniyenin kancası ("Merhaba" yasak) |
| `cta_line` | Videonun son cümlesi: yorum/abone çağrısı |
| `thumbnail_prompt` | **İngilizce**, dikey (9:16), yüksek kontrastlı kapak görseli promptu |
| `viral_hashtags` | **Tam 3 adet** spesifik trend hashtag (YouTube 3'ten fazlasını yok sayar) |

Açıklama sırası (YouTube'da görünen hâli):
```
[1] Affiliate CTA + link      (Faz 9: en üstte)
[2] Etkileşim CTA (cta_line)
[3] Govde metni
[4] #hashtag1 #hashtag2 #hashtag3
```
Yedek senaryo havuzu (LLM anahtarı yokken) için 23 başlığın **elle seçilmiş** hashtag haritası `FALLBACK_VIRAL_TAGS` içinde tanımlıdır.

### 2) Ücretsiz AI Kapak Üretimi + Yükleme (`youtube_studio_uploader.js`)

- **Görsel motoru:** `https://image.pollinations.ai/prompt/<prompt>?width=1080&height=1920&nologo=true&model=flux` (anahtar istemez, ücretsiz).
- **Rate limit (HTTP 402/429) yönetimi:** 4 deneme / 12s-60s bekleme. **Tüm denemeler 402 alırsa artık otomatik kare seçimine düşülmez** → Islah 10: yerel yedek kapak üretilir (bkz. aşağıdaki "Yerel Yedek Kapak").
- **FFmpeg ile 1080x1920'e ölçekleme** (YouTube minimum genişlik 640 px) + filigran kırpma.
- **Studio'ya yükleme:** `ytcp-thumbnail-uploader input[type="file"]` → özel kapak anında uygulanır (doğrulama: `ytcp-video-custom-still-editor`).
- Log satırları: `[*] AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...` → `[+] Kapak resmi başarıyla yüklendi.`

## FAZ 13 — Kanal Güveni, Kalite ve Marka Düzeltmeleri (Denetim Tabanlı)

**Tarih:** 2026-11-04 · **Kaynak:** kanal denetimi (herkese açık 9 Shorts, kapaklar, otomatik altyazılar)
**Canlı TODO:** `docs/FAZ13_AUDIT_PLAN.md`

### 13.1 — Açıklama Güvenliği (ürün iddiası ↔ gerçek link)

Denetim bulgusu: *"Bu teleskobu incele", "Bu kitabı oku", "Bu bilim setini incele"*
metinleri **abone linkine** bağlandığı için açıklamalar yanıltıcıydı.

Kök neden `content_engine.py::resolve_affiliate_offer()`: varsayılan affiliate URL'i
kanalın abone linkiydi (`https://www.youtube.com/@mentansiytas?sub_confirmation=1`),
CTA metni ise ürün iddiasıydı.

| Durum | Davranış |
| :--- | :--- |
| Link = kanalın kendi abone linki | CTA: `Benzer videolar için abone ol: <link>` — **ürün iddiası yok** |
| Link = gerçek ürün/affiliate URL (`AFFILIATE_URL_SPACE/HISTORY/SCIENCE`) | `Bu teleskobu incele: <link> (Bu bir affiliate bağlantısıdır.)` |
| LLM hook'unda uydurma URL | Gerçek link ile değiştirilir (`uydurma_link`) |
| LLM hook'unda ürün iddiası + kanal linki | Dürüst CTA'ya çevrilir (`urun_iddiasi`) |

Ürün iddiası tespiti Türkçe ek toleranslıdır (`teleskobu`, `kitabı`, `bilim setini`, `mikroskoba`…).

### 13.2 — Kaynak satırı + iddia/rakam doğrulama

Her açıklamaya doğrulanmış bir kaynak eklenir:

```
[1] Benzer videolar için abone ol: <link>
[2] Etkileşim CTA
[3] Gövde
[4] Kaynak: NASA — https://svs.gsfc.nasa.gov/11260/
[5] #hashtag1 #hashtag2 #hashtag3
```

**Kaynak haritası** (`content_engine.py::KNOWLEDGE_SOURCES`) — 23/23 senaryo için
2026-11-04'te canlı HTTP 200 ile doğrulandı (NASA, NOAA, UNESCO, Smithsonian,
Wikipedia). Bot koruması veren kaynaklar (Britannica 403) kullanılmadı.

**Düzeltilen iddialar:**

| Konu | Önce | Sonra | Kaynak |
| :--- | :--- | :--- | :--- |
| Nötron yıldızı | 6 milyar ton, "küp şeker" | **1 milyar ton**, tek ölçü: çay kaşığı | NASA SVS 11260 |
| Denizanası | "asla yaşlanmayan", "sonsuza kadar", "insan yaşlanmasını durdurur" | "yaşlanmayı biyolojik geri alabilir", "fiziksel olarak ölümsüz değildir", "doğrulanmış tedavi yok" | Smithsonian |
| Emu Savaşı | "devekuşu", "resmen savaş" | "emu", "resmî bir savaş değildi" | Wikipedia (tr) |
| Göbeklitepe | 12.000 yıl | ~11.000 yıl (MÖ 9600–8200) | UNESCO |
| Antikythera | "bin dört yüz yıl sonra" | "en az bin yıl daha üretilmedi" | Smithsonian |
| Napolyon | "üç bin tavşan" | "binlerce evcil tavşan" | Wikipedia (tr) |

Testler: `tests/test_faz13_trust.py` (79 testin tamamı yeşil).

### 13.3 — Kapak iyileştirmesi (konu uygunluğu doğrulama bekliyor)

Denetim: "Nötron yıldızı" kapağı bitiş kartıydı (konu görseli yok), "Denizanası"
çok karanlıktı, "Antikythera"da asıl mekanizma görünmüyordu.

| Katman | Değişiklik |
| :--- | :--- |
| AI kapak (pollinations) | Stil suffix'ine `single clear subject filling the frame`, `bright well-lit subject`, `no text, no logo, no end card, no split screen` eklendi. |
| Yedek kapak (`scripts/generate_fallback_thumbnail.py`) | Artık **video karesi + başlık kompoziti**: ffmpeg ile videodan 5 aday kare alınır, en kontrastlı kare seçilir, 1080×1920'e kırpılır, üstüne siyah konturlu sarı başlık + kırmızı konu rozeti + konuya işaret eden sarı ok + kırmızı "ABONE OL" butonu çizilir. Video yoksa eski metin kartına düşülür. |
| `content_engine.build_thumbnail_prompt()` | Prompt "the single main subject fills the frame, large, bright and instantly recognizable; no text, no watermark, no logo, no end card" ile güçlendirildi. |

Testler: `tests/test_faz13_trust.py::TestFaz13ThumbnailSubject` gerçek ffmpeg karesi ve renk farkını kontrol eder. **En yüksek kontrast, konu nesnesinin görünür olduğunu veya karede bitiş kartı/metin bulunmadığını kanıtlamaz.** Run #58, 13.3 öncesi yerel yedek kapağa aittir; yeni algoritma ve Studio sonucu için canlı doğrulama gereklidir.

Tarihsel Faz 13.4 audit notu: başlık/konu tekrar koruması Gemini Faz 3 ile `.used_topics.json` Contents API SHA-CAS ve failure release akışına alındı. 18 Kasım’da yeni kodun CI ve iki ayrı Actions koşusunda kalıcılık/release kabulü tamamlandı: [Faz 3 kanıtı](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md). Bu, tüm kanal geçmişinin tarandığı veya gerçek yayın hattının yeni kodla uçtan uca denendiği anlamına gelmez; `docs/FAZ13_AUDIT_PLAN.md` içindeki ayrı denetim işleri korunur.

Gerçek veri hazırlığı: `python3 scripts/audit_public_feed.py --channel-id UCBZVbwc7s7TeUCcOaN58oHQ` kamuya açık Atom akışının anlık görüntüsünü üretir. 4 Kasım ölçümünde akışta 7 video, Studio pruner raporunda 8 korunan video vardı; eksik görünen kayıt ve zamanlar `docs/evidence/` altında. Akış gecikmeli/sınırlı olabilir, tüm yayın geçmişi sayılmaz; bu betik yayın yapmaz ve tekrar korumasını etkinleştirmez. `scripts/audit_repeat_candidates.py docs/evidence/public_feed_2026-11-04.json` karşılaştırması, Mariana için 1.000 fakat aynı denizanası konusu için 0.125 başlık Jaccard skoru verdi; tek eşik güvenilir değildir. Bu da yalnızca rapordur, üretimi etkilemez. `scripts/build_verified_history.py`, gerçek Atom ve Studio raporu kayıtlarını kanal/video kimliğine göre birleştirir, kaynak ve gözlem zamanlarını korur; yayın zamanı yalnızca akışta varsa kaydedilir. Kapsam iki anlık görüntüyle sınırlıdır. 17:11 UTC Studio raporunda Antikythera aynı başlıkla iki ayrı ID üzerinde görüldü (`BlrZMXlIbU0`, `T_yIHvyUY2Y`); bu kayıt üretim korumasının henüz eksik olduğuna dair canlı kanıttır.

### 2b) Yerel Yedek Kapak (Islah 10 — AI servis rate-limit yedeği)

`image.pollinations.ai` kota/rate-limit verdiğinde (HTTP 402/429) **zorunlu kapak teslimi düşmez**:

1. `youtube_studio_uploader.js` → `generateAiThumbnail()` 4 deneme sonunda `null` döner.
2. `generateLocalFallbackThumbnail(title)` devreye girer → `python3 scripts/generate_fallback_thumbnail.py "<başlık>"` (PIL, 60 sn timeout).
3. Üretilen **1080x1920** PNG: siyah/koyu kırmızı gradyan zemin, kırmızı "SON BULMA" bandı, sarı kalın başlık (siyah kontur), sarı ok, kırmızı "ABONE OL" butonu — banner ile aynı görsel dil.
4. Dosya `logs/fallback_thumbnail.png` olarak kaydedilir ve **Studio'ya zorunlu kapak olarak yüklenir**.

Kanıt (run #52, 2026-11-04): pollinations 4/4 deneme HTTP 402 döndürdü → `***!*** Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak.` (özel kapak yok, zorunlu satır kayboldu).
Islah 10 sonrası aynı senaryoda beklenen log: `[*] Yerel yedek kapak hazir (PIL): <yol>` → `[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`

| Dosya | Rol |
| :--- | :--- |
| `scripts/generate_fallback_thumbnail.py` | PIL tabanlı yerel 1080x1920 kapak üreticisi (bağımsız, anahtar gerektirmez) |
| `youtube_studio_uploader.js` → `generateLocalFallbackThumbnail()` | AI kapak null döndüğünde yedeği devreye alır |

### 3) Günlük Kota Koruması

YouTube günlük yükleme limiti dolduğunda yükleme **çökmez**, planlı olarak atlanır:
`⏭️ YÜKLEME ATLANDI: YouTube günlük yükleme kotanı dolmuş (limit gece yarısı sıfırlanır).` (çıkış kodu `42` → `main.py` bunu hata saymaz).

### 4) Cron Kilidi Kırma (Zamanlayıcı Bağımsız Zincir)

GitHub'ın `schedule` tetikleyicisi bu depoda **hiç otomatik tetiklenmemişti** (`event=schedule` toplam çalıştırma = 0). Çözüm:

1. `cron: '0,15,30,45 * * * *'` (kesin dilimler) + `permissions: contents/actions/pull-requests: write`.
2. **Otomatik commit mesajlarındaki `[skip ci]` kaldırıldı** — HEAD commit mesajında `[skip ci]` varsa zamanlayıcı sessizce atlanır.
3. **`cron-kick` job'ı (zincir):** Her çalıştırmanın sonunda zamanlayıcı canlı mı kontrol edilir (API: `?event=schedule`); **ölüyse** iş akışı `workflow_dispatch` ile kendini bir sonraki 15 dakikalık dilime yeniden tetikler. Böylece üretim zinciri zamanlayıcıdan bağımsız çalışır.
4. `.github/workflows/cron_probe.yml`: 5 dakikada bir "PROBE OK" atan nabız iş akışı (zamanlayıcı sağlık teşhisi).

### 5) Kanal Sırası + "Aynı Hesap" Koruması (Faz 11 düzeltmesi)

Daha önce 10 kanal **aynı anda** çalışıyordu ve 10 secret'in tamamı **aynı YouTube hesabını**
işaret ettiği için kanalın günlük yükleme kotası 10 katına kadar harcanıyordu.

| Sorun | Çözüm |
| :--- | :--- |
| 10 paralel job, aynı kanal | `max-parallel: 1` + zincir **tek kanal** tetikler (dizi kanal sırası) |
| 10 secret = aynı hesap | `scripts/channel_map.sh` → aynı hesabı işaret eden kanallar **ayıklanır** |
| Kota doluyken boşuna üretim | Zincir, kotaya takılan turdan sonra **4 saat** bekler (15 dk değil) |
| GitHub matris çıktısını siliyordu | Matris `distinct_csv` (virgüllü liste) olarak taşınır, iş akışında JSON'a çevrilir |

**Kanal haritası job'u** her çalıştırmada hangi kanalların AYRI hesap olduğunu loglar:
```
[AYRI HESAP] Kanal 1 (hash a4ae91d03ee1) -> uretime dahil.
[AYNI HESAP] Kanal 2 = Kanal 1 (hash a4ae91d03ee1) -> atlandi (gunluk kota korunuyor).
...
[*] Benzersiz kanallar: 1
[*] Siradaki kanal (rotasyon 17): 1
```

> ⚠️ **Kanal kurulumu:** `COOKIES_JSON_1..10` şu anda **tek hesabı** gösteriyor. Gerçek 10 kanal için
> her kanalın **ayrı bir YouTube hesabı** (ayrı `cookies.json` + `storage_state.json`) olmalı.
> Ayrı hesaplar girildikçe `channel_map.sh` otomatik olarak üretime alır (matris büyür).

---

## Faz 12 — TOTAL DOMINATION (Silahlandırılmış Prompt + Agresif Kapak + Kanal Hijyeni)

### 1) Cron Throttle Bypass
```yaml
on:
  schedule:
    - cron: '0,13,27,41,55 * * * *'   # asal olmayan dakikalar
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true            # tıkanmış/eski job iptal, en güncel çalışır
permissions:
  contents: write
  actions: write
```
> Zincir (cron-kick) tetikleme POST'u tamamladıktan sonra iptal olur; self-perpetuating zincir bozulmaz.

### 2) Silahlandırılmış LLM Promptu
`content_engine.py → build_llm_prompts()` artık "algoritma hacker'ı" personasıyla çalışır:
scroll-stop hook (60-80 kelime), zorlayıcı CTA, **zorunlu kapak dili**
(`YouTube Shorts thumbnail, vertical 9:16, hyper-dramatic lighting, high contrast, vibrant colors,
glowing elements, 8k resolution, cinematic`), tam 3 spesifik hashtag + `affiliate_hook`.
JSON şeması: `topic, title, description, hook, script_text, cta_line, thumbnail_prompt,
viral_hashtags, affiliate_hook, visual_keywords`.

### 3) Agresif AI Kapak (CTR odaklı)
`youtube_studio_uploader.js` → kapak promptuna otomatik eklenen stil suffix'i:
`glowing arrows, shocked expression, unreal engine 5 render, dramatic shadows, 8k resolution...`
Yükleme iki katmanlıdır: önce `ytcp-thumbnail-uploader input#file-loader` (doğrulanmış yol),
olmazsa `Kapak resmi / Thumbnail` butonu + `filechooser` yedeği. Başarı logu:
`[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!`

### 4) Açıklama Sırası (Metadata Zehiri)
```
[1] affiliate_hook (varsa) / affiliate CTA + link
[2] Etkileşim CTA (cta_line)
[3] Gövde
[4] Tam 3 trend hashtag
```

### 5) Kanal Hijyeni (otomasyon)
| Adım | Nerede | Durum |
| :--- | :--- | :--- |
| Banner (2560x1440, siyah + sarı/beyaz + kırmızı "ABONE OL") | `scripts/generate_banner.py` | ✅ üretildi & yüklendi |
| Kanal "Hakkında" açıklaması | `ytcp-social-suggestions-textbox#description-textbox` + "Yayınla" | ✅ güncellendi |
| Sabitlenmiş yorum | `ytd-comment-simplebox-renderer` → `İşlem menüsü` → "Sabitle" | ✅ yazıldı & sabitlendi (`#pinned-comment-badge`) |

Hepsi `scripts/channel_hygiene.js` ile yapılır; **hata olursa yayınlama akışı bozulmaz**.


---

## Faz 12.6 — Denetim İslahları (Ekip Denetimi, 04.11.2026)

Ekip denetimi 5 bulgu getirdi. Her bulgu için **neden** + **nasıl doğrulandı** kaydı:

### 1) İptal fırtınası (asıl dert) — DÜZELTİLDİ
**Kök neden:** `cron-kick` job'ı `if: always()` ile çalışıyordu. İptal edilen bir koşu
bile yeni bir zincir koşusu tetikliyordu → #34 iptal → #35 doğdu → #35 iptal → #36…
Ayrıca GitHub `schedule` olayı ile zincir **aynı anda** iki video üretiyordu.

| Önlem | Nerede |
| :--- | :--- |
| `if: always()` → `if: ${{ !cancelled() }}` (iptal edilen koşu yeni koşu doğurmaz) | `daily_shorts.yml`, `hourly_pruner.yml` |
| Tetiklemeden önce aktif koşu kontrolü (`scripts/active_runs_count.sh`) | `cron-kick` |
| Cron artık **bekçi (watchdog)**: zincir aktifse üretim yapmaz (`scripts/production_gate.sh`) | `build-and-upload` |
| Zincir koşuları ayrı concurrency grubunda (`chain=1`) → elle/schedule koşusu yayını iptal etmez | `concurrency.group` |

**Doğrulama:** zincir kırıkken zincir yeni koşu üretmiyor; `schedule` koşusu aktif zincir
varsa `produce=false` ile üretimi atlıyor; 57/57 unittest + actionlint temiz.

### 2) Ubuntu 26.04 geçişi — SABİTLENDİ
GitHub 19 Ekim–19 Kasım 2026 arasında `ubuntu-latest` → 26.04'e geçiyor. Bu repo
`libass9`, `fonts-*`, `xvfb` ve `playwright install --with-deps` kullanıyor.

- Ana workflow'lar: `runs-on: ubuntu-24.04` (resmî öneri)
- Yeni `.github/workflows/ubuntu_26_test.yml`: `ubuntu-26.04` imajında paket kurulumu,
  Playwright, **altyazı montaj testi** (FontSize=56 / MarginV=250) ve birim testleri.
  (Geçiş öncesi ölçüm; kanal/yayın yapmaz.)
- `.github/actionlint.yaml`: actionlint'in etiket listesi 26.04'ü bilmiyor → ignore.

### 3) Node 20 uyarıları — YÜKSELTİLDİ
`action.yml → runs.using` doğrulandı (v4/v5 = node20, v6/v7 = node24):

| Action | Eski | Yeni | Breaking change etkisi |
| :--- | :--- | :--- | :--- |
| actions/checkout | v4 (node20) | **v7** (node24) | fork-PR engeli (kullanmıyoruz) + ESM → etkisiz |
| actions/setup-python | v5 (node20) | **v7** (node24) | `pip-install` input'u kaldırıldı (kullanmıyoruz) → etkisiz |
| actions/setup-node | v4 (node20) | **v7** (node24) | yeni output'lar, sahte `NODE_AUTH_TOKEN` kaldırıldı → etkisiz |
| actions/upload-artifact | v4 (node20) | **v7** (node24) | `archive:false` opsiyonel (varsayılan zip aynı) → etkisiz |

### 4) Koddan okunduğu buglar — DÜZELTİLDİ
- `ARGS` artık **bash array** (`ARGS=(--banner ... --about "$ABOUT_TEXT")` + `"${ARGS[@]}"`).
  Önceden `$ARGS` boşluklu metni (e-posta) birden fazla argümana bölüyordu.
- Hata `|| echo` ile yutulmuyor → `::warning::Kanal hijyeni başarısız (rc=…)` annotation'ı.
- `${{ inputs.slot_epoch }}` artık **env** (`SLOT_EPOCH`) ile geçiliyor (script injection riski yok).
- **actionlint bulgusu:** `join(distinct_csv, '","')` → GitHub ifadelerinde `join()` ARRAY
  bekler, `distinct_csv` STRING'dir (tek kanalda tesadüfen çalışıyordu). Artık
  `scripts/channel_map.sh` → `distinct_json='["1"]'` üretiyor, matrix `fromJSON(distinct_json)`.

### 5) Artifact güvenliği — EKLENDİ
`scripts/sanitize_logs.sh`: artifact'a girmeden önce `logs/` içinden
cookie/storage_state/token dosyaları **silinir**, kalan dosyalardaki
`SIDCC/SAPISID/HSID/SSID/__Secure-*`/`Bearer …`/`AIza…`/`refresh_token` kalıpları
**redakte** edilir ve `::warning::` üretilir.

### 6) Tek satırlık durum bildirimi — EKLENDİ
`scripts/run_summary.py` → `::notice::Kanal 1: YÜKLENDİ | Video: … | https://…`
(+ GitHub Step Summary tablosu). `scripts/pruner_summary.py` → pruner özeti.

### Tek üretim mekanizması: ZİNCİR
GitHub `schedule` olayı **best-effort**: 13 saatte sadece **2 kez** ve 4–6 dk gecikmeyle
tetiklendi (#28 01:51, #29 08:31). Bu yüzden:
- **Zincir (cron-kick) = asıl motor** (15 dk'da bir, kendini devam ettiren).
- **Cron = bekçi**: yalnızca zincir ölüyse devreye girer.


### 7) GitHub output maskeleme tuzağı (CI'da ölçüldü) — ÖNEMLİ
`channel-map` job'ının çıktısı **düz string** olmak zorunda. GitHub, **köşeli parantez
içeren** output değerlerini secret sanıp maskeliyor ve outputu **atıyor**:

| Output değeri | Sonuç (run 41851410202, channel-map job) |
| :--- | :--- |
| `["1"]` (tırnaklı JSON dizi) | `Skip output ... since it may contain secret` ✗ |
| `[1]` (sade JSON dizi) | `Skip output ... since it may contain secret` ✗ |
| `1` (düz string) | `Set output 'distinct_csv'` ✓ |

Bu yüzden `distinct_json` çıktısı **kullanılamaz**; matris şu ifadeyle kurulur
(runtime'da doğrulandı: schedule koşuları #28/#29 bu ifadeyle video üretti):
```yaml
channel_id: ${{ fromJSON(format('["{0}"]', join(needs.channel-map.outputs.distinct_csv, '","'))) }}
```
> `split()` **GitHub ifade dilinde yoktur** — `workflow_dispatch` 422 ile reddedilir
> ("Unrecognized function: 'split'"). actionlint de uyarır.

### 8) Ek denetim düzeltmeleri (2. tur)
| Bulgu | Durum |
| :--- | :--- |
| `hourly_pruner.yml` → `#{{ matrix.channel_id }}` yazım hatası | ✅ düzeltildi (`${{ }}`) |
| `cron_probe.yml` → `*/5` (ayda ~8.640 job) | ✅ saatliğe çekildi (`17 * * * *`) |
| `daily_analytics.yml` → push öncesi rebase yok | ✅ `git pull --rebase` eklendi |
| `sanitize_logs.sh` → dar dosya kalıpları | ✅ `*session*`, `*.key`, `*.pem`, `id_token`, `session_id` eklendi |
| Hijyeni adımı `if: always()` → gate `produce=false` iken About metnini ezip **kanal hakkında alanını bozabilirdi** | ✅ gate'e bağlandı |
| `actions/checkout@v7` "yok" iddiası | ❌ **yanlış** — v7.0.1 (20.07.2026) mevcut, `runs.using: node24`; CI'da fiilen çalıştı (#43/#44 başarılı) |
| `ubuntu-26.04` runner "yok" iddiası | ❌ **yanlış** — 17.09.2026 changelog'u duyurdu; `ubuntu_26_test.yml` iki kez 26.04'te **başarıyla** çalıştı (ffmpeg 8.0.1, altyazı montajı OK, 57 test OK) |
| `requirements.txt` "pinler bulunamaz" iddiası | ❌ **yanlış** — zaten tam pin (`==`) ve her CI koşusunda başarıyla kuruluyor |

### 13 — Taslak ve yayın doğrulaması (5 Kasım 2026)

Run #90 gerçek Studio görüntüsünde zorunlu çocuklara özel seçimi boştu; İleri pasif kaldı. Uploader artık bu seçimin ve PUBLIC seçiminin gerçekten işaretlendiğini kontrol eder. Yayın sonrası ilgili video ID'si için Studio satırında PUBLIC ikonu + etiketi görülmezse `publish_unverified` ile hata verir; yeniden yüklemeden önce Studio kontrol edilmelidir. Gerçek bir taslakta çocuk radyo seçimi, mevcut bir PUBLIC videoda Studio görünürlük seçicisi doğrulandı; **yeni kodla uçtan uca yayın doğrulaması henüz yapılmadı**.

Tarihsel not: 5 Kasım’da CI `--force-fallback` kullanıyordu. 18 Kasım’daki gerçek, yayın yapmayan Gemini Web cookie-only kanıtı [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017) korunur. Yeni Faz 3 kodu CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) ve ayrı `reserve`/`verify` koşularıyla kabul edildi; [kanıt raporu](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md). Konu uyumu/izlenme artışı veya yeni kodla canlı YouTube yayını doğrulanmış değildir.

**Canlı test:** #97 (`41948576364`) yayın işi başarılı; [7DULxjp6PsQ](https://youtube.com/shorts/7DULxjp6PsQ) Studio'da PUBLIC ve girişsiz oynatılabilir. Koşunun geneli cron-kick iptali yüzünden `cancelled`. Örnek karelerde uçak, yana dönmüş kıyı ve alakasız yazılı grafik görüldüğü için görsel kalite **başarısız**; aynı başlık `WKYwF96hQzg` üzerinde de mevcut. Taslak silme Studio kimlik doğrulaması istedi; silme yapılmadı. Otomatik workflow yeniden aktifleştirildi.

---

## Gemini Tabanlı Otonom Shorts — Geliştirme ve Kabul Durumu

Gemini Web route’u ile Faz 3 kaynak/tekrar-koruma uygulandı. **Faz 3 kabul edildi:** yeni kodun Ubuntu 26 CI koşusu ve iki ayrı Actions koşusu arasında rezervasyonun kalıcı olması/serbest bırakılması doğrulandı. [Faz 3 Actions kanıt raporu](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md); gerçek YouTube yayın testi yapılmadı. Sahne-medya uyumu, zamanlama/lisans ve bütünleşik kalite kapısı hâlâ sonraki fazların işidir.

- **[Mimari ve ayrıntılı uygulama planı](docs/GEMINI_AUTONOMOUS_SHORTS_PLAN.md)** — mevcut kod akışı, hedef mimari, veri sözleşmesi, kalite kapıları, hata politikası, güvenlik ve fazların kabul kriterleri.
- **[Canlı TODO / ilerleme listesi](docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md)** — her fazın yapılacak işleri, tamamlanma koşulları ve kanıt kaydı.
- **[Faz 0 başlangıç ve test baseline raporu](docs/evidence/FAZ0_BASELINE_2026-11-17.md)** — branch/commit, workflow güvenliği, gerçek üretim logu ve 108 testlik CI kanıtı.

İlerleme kuralı: Her iş yalnız gerçek kod değişikliği, başarılı test ve gereken CI/Studio doğrulaması görüldüğünde tamamlandı işaretlenir. Ücretli API/görsel/video üretimi veya billing açılmaz; ücretsiz erişimi doğrulanmayan özellik etkinleştirilmez. Mevcut cron, kanal, pruner, PUBLIC yayın ve güvenlik davranışları başlangıç denetimi yapılmadan değiştirilmez.

**Sıradaki adım: İzinli mevcut konfigürasyonla stock canlı source/license/download erişimini ve Actions Commons download/decode ayrımını çözmek; erişilemiyorsa kabul blokajını korumak. Faz 4B yerel Commons video/CC BY, izin verilen fixture gerçek tüketici ve iki-Actions history alt kanıtlarını ekledi; TAM KABUL GEÇMEDİ. Faz 5 başlamadı.**

## Gemini Faz 4B — kapsam ve karşılanmayan kapılar

- Başlangıç [`316ae2e`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/316ae2e3e1aff89483d367a5d7ea2e82f0f68665) → ana kod [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472) → yalnız izole medya workflow dependency düzeltmesi [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106). [Ayrıntılı rapor](docs/evidence/PHASE4B_ACCEPTANCE_2026-11-18.md). CI altkümeleri ana 301 teste tekrar dâhildir, toplanmaz.
- Gerçek root `content_engine.py` writer, ara `draft_to_script_metadata`, bağımsız eski `src/content_generation/engine.py` birbirinden ayrıldı. Explicit scenario/sentetik-ses girdileriyle gerçek root writer → pre-schema CLI → aynı JSON `run_media_pipeline` → manifest/credits/persist/reload → post-schema CLI → gerçek `embed_cover_frame --no-ai` JSON salt-okur tüketici → uploader’dan yalnız iki gerçek saf metadata işlevi çalıştı. Bu canlı Gemini/TTS veya Studio değildir; uploader entrypoint’i import/require edilmez.
- Aynı final kodla **yerel** canlı Commons video174336538 (Magpieturtle, CC BY4.0) ve still83667454 (Alexander Grebenkov, CC BY3.0): gerçek source/deed HTTP200, download/full decode, gerçek tüketici ve 858/4900 UTF-16 içinde iki tam atıf geçti. Hareketli video temporal değişim gösterir; metadata/pixel değişimi genel sahne-anlam onayı değildir. İkinci kare downstream kanyon/akarsu görünümüdür, belirgin falling-water yüzeyi doğrulanmadı; narration değiştirilmedi.
- **Actions [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) failure:** Pexels/Pixabay exact allowlisted API key nonempty gözlenmedi; cookie file vardı, browser403. Commons katalog adayı buldu, uygun video174336538/83680173 generic download/decode RuntimeError ile reddedildi; HTTP mi decode mu olduğu kanıttan ayrışmıyor. Yerel başarı bunu yeşile çevirmez. İlk [44297831876](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297831876) provider’a ulaşmadan yavaş Ubuntu apt indirmesinde iptal edildi, silinmedi; resmî ayna/no-recommends/timeouts düzeltmesinden sonra yalnız bir gerekçeli yeni media dispatch yapıldı.
- Public media transport prepared-request aşamasında session auth/Cookie/custom-key header’larını her allowlisted hop’ta temizler. Probe ENV_FILE’ı disk/shell yerine dotenv DATA/interpolate=False parse eder; yalnız exact iki stock key kendi adaptörüne bellekte gider. Browser child key/GitHub/Gemini env alamaz; 403 bypass yoktur. Üretim `.env`/cookie kurulum davranışı değiştirilmedi.
- History yalnız ayrı probe ref/path’te üç synthetic sentinel kullandı: gerçek stale-SHA409 → reread/merge, farklı Actions’ta aynı blob/entry okuma, dosyaDELETE200/refDELETE204 ve bağımsız404. Production topic/media history değişmedi; local flock dağıtık kilit veya selection reservation değildir.
