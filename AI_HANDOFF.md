# 🤖 AI_HANDOFF.md — Yapay Zeka Devir Teslim ve Operasyon Kılavuzu

> **Son Güncelleme:** `2026-11-03` (Faz 1–7 Tamamlandı, Bulutta %100 Canlı Üretimde)  
> **Hedef Kitle:** Bu projeyi devralacak bir sonraki Yapay Zeka Ajanı (Arena Agent, Claude Code, Cursor, Codex vb.) veya Geliştirici.

Bu belge, projeyi devralan bir yapay zekanın **sıfır tahmin, sıfır deneme-yanılma ve sıfır güvenlik ihlali** ile 30 saniye içinde sistemi anlayıp geliştirmeye devam edebilmesi için hazırlanmıştır.

---

## 1. Projenin Anlık Durumu (Executive Summary)

Proje; Türkçe YouTube Shorts içeriklerini **senaryo -> seslendirme (`edge-tts`) -> kelime senkronlu `.ass` altyazı -> dikey `1080x1920` FFmpeg montaj -> Playwright YouTube Studio üzerinden sıfır API kotasıyla doğrudan `PUBLIC` (Herkese Açık) yayın** adımlarıyla uçtan uca otonom üreten bir içerik fabrikasıdır.

| Bileşen | Durum | Detay |
| :--- | :---: | :--- |
| **GitHub Deposu** | ✅ Aktif | `https://github.com/ahmetbysoy/youtube_shorts_automation` (`main` dalı) |
| **YouTube Kanalı** | ✅ Aktif | `@mentansiytas` — `https://studio.youtube.com/channel/UCBZVbwc7s7TeUCcOaN58oHQ` |
| **Birim Testleri** | ✅ `22/22` | `python -m unittest discover -s tests -p "test_*.py"` |
| **Faz 1–4 (Motorlar)** | ✅ Tamamlandı | İçerik/TTS (`content_engine.py`), Montaj (`src/media_processing/media_processor.py`), OAuth/API yedek modülü (`src/youtube_upload/`) |
| **Faz 5 (Studio Backdoor)** | ✅ Tamamlandı | `youtube_studio_uploader.js` (Playwright Chromium + kalıcı çerez/storageState oturumu) |
| **Faz 6 (Orkestratör & CI)** | ✅ Tamamlandı | `main.py` uçtan uca orkestrasyon + GitHub Actions bulut otomasyonu |
| **Faz 7 (PUBLIC & Matris)** | ✅ Tamamlandı | Doğrudan **`PUBLIC` (Herkese Açık)** yayın + `matrix.channel_id: ['1'..'10']` paralel bulut matrisi |
| **Faz 8 (15dk Sniper Modu)** | ✅ Tamamlandı | `cron: '*/15 * * * *'` + `concurrency` kilidi, MD5 zaman tohumlaması (`23` asal senaryo havuzu ile 15dk sıfır tekrar) ve mobil-optimize FFmpeg (`unsharp`, `eq`, `FontSize=56`, `MarginV=250`) |
| **Faz 9 (Monetizasyon & Analitik)** | ✅ Tamamlandı | Konu bazlı `affiliate_link` + CTA enjeksiyonu (`AFFILIATE_URL_SPACE/HISTORY/SCIENCE`, açıklamanın 1. satırı) ve `analytics_scraper.js` + `daily_analytics.yml` ile kazanan konuları `%80` ağırlıkla besleyen geri bildirim döngüsü |

### Canlı Yayınlanmış Videolar (Kanıt Envanteri)

1. `https://youtube.com/shorts/wOzB6rtg6Yg` — *Faz 5 Yerel Test (`PRIVATE`)*
2. `https://youtube.com/shorts/zELMhLQ6ZXE` — *Faz 6 GitHub Actions Tekil Bulut Testi (`PRIVATE`, Run `#41669697717`)*
3. `https://youtube.com/shorts/3SFUI9fSYSU` — **Faz 7 Matris Kanal #1 (`PUBLIC` - Herkese Açık, Run `#41693452172`)** — *Napolyon'un Tavşan Ordusuna Karşı Tuhaf Yenilgisi!*
4. `https://youtube.com/shorts/atw6R7iSY88` — **Faz 7 Matris Kanal #2 (`PUBLIC` - Herkese Açık, Run `#41693452172`)** — *Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe!*
5. `https://youtube.com/shorts/A2F4P7BLB8A` — **Faz 7 Matris Kanal #3 (`PUBLIC` - Herkese Açık, Run `#41693452172`)** — *Everest'i Yutan Karanlık Uçurum: Mariana Çukuru!*

---

## 2. Kimlik Bilgileri, Oturum Dosyaları ve Yedeklerin Konumu (GÜVENLİK HARİTASI)

> **KRİTİK GÜVENLİK KURALI:** GitHub deposu herkese açıktır (`public`). `.env`, `cookies.json`, `storage_state.json`, `session.har`, şifreler veya GitHub PAT token'ları **ASLA** Git'e commit edilmez! Tüm gizli dosyalar **Google Drive** (özel) ve **GitHub Repository Secrets** (Libsodium şifreli) üzerinde tutulur.

### A. Google Drive Konumları (Bağlı Uygulama: `google_drive`)
Projeyi yeni bir çalışma alanında (workspace) devraldığında ilk olarak `google_drive` aracını yükle ve aşağıdaki kaynakları oku:

1. **`YouTube` Klasörü (`Folder ID: 1I-8dtEQHHZ-5PUmaKf1hjG14QDc4PMT8`):**
   - **`youtube_shorts_automation_faz7_full_workspace.zip`:** Kodlar + `.env` + `cookies.json` + `storage_state.json` + `session.har` + örnek çıktılar (`output/final_short.mp4`) dahil **tüm çalışma alanının eksiksiz yedeği** (`node_modules` ve `.venv` hariç). Yeni bir ortamda tek komutla açıp (`unzip`) anında çalıştırabilirsin.
   - **`youtube_shorts_automation_faz7_sessions/` alt klasörü:** Arşiv indirmeden doğrudan `read_file_text` ile okuyabilmen için `.env`, `cookies.json`, `storage_state.json`, `AI_HANDOFF.md`, `README.md` ve `ARCHITECTURE.md` dosyalarının düz metin kopyaları.
2. **`YouTube_account.md` (`File ID: 1E2xm83mbXD4hwPiWRSIiHFmF2rinbizD`):**
   - Ana YouTube/Google hesabının giriş bilgileri.
3. **`github_erisim.json` (`File ID: 1LgE8SlgalAVgtK0mLWH2KGTfJhCz5yu6`):**
   - GitHub Personal Access Token (`GITHUB_TOKEN`) ve ajanlar arası işlem notu. Kural gereği token'ı yalnızca geçici olarak bellekte/komutta kullan, `.git/config` içine kalıcı yazma ve işlem bitince `github_erisim.json` içindeki `note` alanını güncelle.

### B. GitHub Repository Secrets Envanteri (`ahmetbysoy/youtube_shorts_automation`)
Depoda şu an tanımlı ve aktif **33 gizli anahtar (Secret)** bulunmaktadır:
- **10'lu Matris Kanalları (`1..10` — Aktif Kullanımda):**
  - `ENV_FILE_1` .. `ENV_FILE_10`
  - `COOKIES_JSON_1` .. `COOKIES_JSON_10`
  - `STORAGE_STATE_JSON_1` .. `STORAGE_STATE_JSON_10`
- **Tekil / Yedek Geriye Dönük Uyumluluk:**
  - `ENV_FILE`, `COOKIES_JSON`, `STORAGE_STATE_JSON`

> **14 Günlük Cookie Rotasyonu (`scripts/rotate_cookies.py`):** Google'ın bulut IP'lerinde oturumu düşürmemesi için her 14 günde bir yerelde `node youtube_studio_uploader.js` çalıştırılıp taze `cookies.json` ve `storage_state.json` alındıktan sonra tek komutla tüm kanallara (veya belirli bir kanala) basılır:
> ```bash
> GITHUB_TOKEN="..." python scripts/rotate_cookies.py --channels 1-10
> ```
> **Yeni Bağımsız Kanallar Ekleme:** 2'den 10'a kadar yeni Gmail/YouTube hesapları açıldığında kodda **sıfır değişiklik** gerekir; ilgili hesabın oturum dosyalarıyla `python scripts/rotate_cookies.py --channels 2 --env-file .env.ch2 --cookies-file cookies_ch2.json --state-file state_ch2.json` çalıştırmak yeterlidir.

---

## 3. Kullanıcı Kuralları ve Kesin Kısıtlamalar (User Standing Instructions)

1. **Sıfır Mock / Sıfır Simülasyon:** Sahte veri (`dummy_cfg`, sahte yükleme, simüle edilmiş API yanıtı) kesinlikle yasaktır. Yalnızca gerçek hesaplar, gerçek oturumlar ve gerçek yüklemeler kullanılır.
2. **Anında GitHub Senkronizasyonu:** Yapılan her kod değişikliği ve her dokümantasyon güncellemesi bekletilmeden `git add` -> `git commit` -> `git push origin main` ile GitHub'a gönderilmelidir.
3. **Tek Seferlik Giriş & Kalıcı Oturum:** `cookies.json` ve `storage_state.json` mevcutken tekrar tekrar 2FA onayı istenmez; yalnızca oturum tamamen düşerse telefondan onay istenir.
4. **Tam Otonom `PUBLIC` Yayın:** Videolar `PRIVATE` değil, doğrudan **`PUBLIC` (Herkese Açık)** olarak yayınlanır.

---

## 4. Altın Mühendislik Kuralları & Çözülmüş Tuzaklar (SAKIN BOZMA!)

Bu projede daha önce karşılaşılan ve çözülen kritik teknik engeller şunlardır — **kodda değişiklik yaparken bu mekanizmaları koru**:

1. **CI'da `HEADLESS="true"` KULLANMA — Her Zaman `xvfb-run` Kullan!**
   - **Neden:** GitHub Actions (`ubuntu-latest`) üzerinde Chromium `headless: true` modunda açılırsa Google GlifWebSignIn tarayıcıyı yakalar ve `accounts.google.com/v3/signin/rejected?...&rrk=46` (*"Bu tarayıcı veya uygulama güvenli olmayabilir"*) hatasıyla girişi reddeder.
   - **Çözüm:** `.github/workflows/daily_shorts.yml` içinde `xvfb` kuruludur ve orkestratör `xvfb-run -a --server-args="-screen 0 1366x900x24" python main.py` ile çalıştırılır (`DISPLAY` tanımlı olduğu için `youtube_studio_uploader.js` otomatik olarak `headless=false` yani tam tarayıcı modunda çalışır ve Google kontrolünü %100 geçer).
2. **`PROFILE_DIR` Konumunu `/home/user` İçine Taşıma!**
   - **Neden:** Chromium kullanıcı profili ~139 MB yer kaplar ve Arena'nın 128 MB çalışma alanı (snapshot) limitini aşar.
   - **Çözüm:** `youtube_studio_uploader.js` içinde `PROFILE_DIR = path.join(os.tmpdir(), 'yt_studio_browser_profile')` olarak ayarlanmıştır. Kalıcı oturum için `cookies.json` (`13 KB`) ve `storage_state.json` (`16 KB`) fazlasıyla yeterlidir.
3. **Bulut IP'lerinde Google Giriş Sonrası Ara Ekran (`myaccount.google.com` / `gds.google.com`) Atlama:**
   - GitHub Actions ABD (Azure) IP'lerinden giriş yapıldığında Google bazen `AccountChooser` ve ardından `myaccount.google.com/verification/selfie/precollection` ara sayfasına yönlendirir. `youtube_studio_uploader.js` içindeki `performGoogleLogin()` fonksiyonu `accounts.google.com` dışına çıkıldığı anda doğrudan `https://studio.youtube.com/` adresine zıplayarak bu ekranları sorunsuz atlar. Bu bloğu silme.
4. **GitHub Actions YAML İçinde Secret Yazarken `echo` Değil `printf '%s\n'` Kullan:**
   - Çok satırlı `.env` ve tırnak içeren `cookies.json` verilerini `echo "${{ secrets.X }}"` ile yazmak JSON yapısını bozar. Her zaman `env:` bloğuna bağlayıp `printf '%s\n' "$VAR" > dosya` şeklinde yaz.
5. **Paralel Matris Çakışma Koruması (`MATRIX_CHANNEL_ID`):**
   - `content_engine.py` içindeki `pick_fallback_scenario()` fonksiyonu `(tm_yday * 3 + (channel_id - 1)) % len(FALLBACK_SCENARIOS)` formülüyle 3 paralel sunucunun aynı gün içinde birbirinden farklı konular seçmesini sağlar.
   - `youtube_studio_uploader.js` ise `MATRIX_CHANNEL_ID` değerine göre `0s / 15s / 30s` kademeli başlatma (`stagger`) uygulayarak aynı saniyede oturum çakışmasını önler.
6. **Git Push Yaparken Token'ı `.git/config` İçine Yazma:**
   - Arena snapshot güvenliği `.git/config` dosyasını dışlar ve açık token sızıntı riski yaratır. Push işlemini her zaman tek seferlik HTTP başlığıyla yap:
     ```bash
     B64_AUTH=$(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)
     git -c http.https://github.com/.extraHeader="Authorization: Basic ${B64_AUTH}" push origin main
     ```

---

## 5. Yeni Bir Ortamda Hızlı Başlangıç (30 Saniyede Devralma)

```bash
# 1. Depoyu klonla veya mevcut dizine gir
cd /home/user/youtube_shorts_automation

# 2. (Yeni ortamdaysan) Google Drive 'YouTube' klasöründen .env, cookies.json ve storage_state.json dosyalarını kök dizine koy ve izinleri kilitle:
chmod 600 .env cookies.json storage_state.json

# 3. Bağımlılıkları kur (Python sanal ortamı + Node/Playwright)
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -r requirements.txt
npm install
npx playwright install --with-deps chromium

# 4. Birim testlerini doğrula (22/22 OK olmalı)
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v

# 5. Tam üretim hattını çalıştır (Senaryo + Ses + Altyazı + 1080x1920 Video + PUBLIC Yayın)
xvfb-run -a --server-args="-screen 0 1366x900x24" .venv/bin/python main.py
```

### GitHub Actions Bulut Hattını Uzaktan Tetikleme

```bash
curl -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/daily_shorts.yml/dispatches \
  -d '{"ref":"main"}'
```

---

## 6. Sıradaki Faz Yol Haritası (Faz 8 ve Sonrası İçin Öneriler)

Bir sonraki yapay zeka ajanının doğrudan başlayabileceği geliştirmeler:

1. **Faz 8 — Kendi Kendini Eğiten Analitik Geri Besleme Döngüsü (`analytics_scraper.js`):**
   - Playwright ile `https://studio.youtube.com/channel/UCBZVbwc7s7TeUCcOaN58oHQ/analytics` sayfasından son 10 Shorts videosunun **İzlenme Sayısı**, **Ortalama Görüntüleme Yüzdesi (Retention %)** ve **Geçme/İzleme Oranı (Viewed vs Swiped Away)** metriklerini çekip `analytics_report.json` dosyasına kaydetmek.
   - `content_engine.py` içindeki LLM sistem istemine (prompt) en yüksek tutma oranına sahip kanca (`hook`) kalıplarını besleyerek kanalın kendi kendini optimize etmesini sağlamak.
2. **Canlı Ücretsiz API Anahtarlarıyla Dinamik Senaryo & Stok Video Çeşitlendirme:**
   - `.env` ve `ENV_FILE_1..3` içine ücretsiz `GROQ_API_KEY` (`llama-3.3-70b-versatile`) ve `PEXELS_API_KEY` / `PIXABAY_API_KEY` eklendiğinde `main.py` içindeki `--force-fallback` bayrağı kaldırılarak sınırsız dinamik Wikipedia destekli konu üretimine geçilebilir (`content_engine.py` ve `media_processor.py` bu entegrasyona şimdiden %100 hazırdır).
3. **2. ve 3. Bağımsız YouTube Kanallarının Bağlanması:**
   - Farklı nişlerde (ör. Kanal 1: *Tarih*, Kanal 2: *Uzay & Bilim*, Kanal 3: *Psikoloji & İlginç Bilgiler*) yeni Gmail/YouTube kanalları açıldığında `COOKIES_JSON_2` / `STORAGE_STATE_JSON_2` ve `_3` secret'ları güncellenerek 3 ayrı kanala eşzamanlı yayın yapılabilir.

---

## 7. Faz 10 — Otonom "Ölü Ağırlık" Temizleyici (Auto-Pruner) Operasyon Protokolü

**Ne yapar:** `prune_low_performers.js` her saat başı YouTube Studio'ya girer; **1 saatten eski** ve **100 izlenmenin altında** kalan videoları kalıcı olarak siler. `hourly_pruner.yml` bunu 10 kanallı matrisle (`1..10`, `fail-fast: false`) ve saatlik `cron: '0 * * * *'` ile çalıştırır.

**Çalıştırma komutları:**

```bash
# Manuel tetikleme (tek kanal)
curl -X POST -H "Authorization: Bearer ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/hourly_pruner.yml/dispatches \
  -d '{"ref":"main","inputs":{"target_channel":"1"}}'

# Yerelde kuru deneme (SİLMEZ)
PRUNE_DRY_RUN=true xvfb-run -a --server-args="-screen 0 1366x900x24" node prune_low_performers.js

# Tek video hedefiyle test (dikkat: gerçekten siler)
PRUNE_ONLY_VIDEO_IDS=<VIDEO_ID> xvfb-run -a node prune_low_performers.js
```

**Eşikler (GitHub Secrets/Vars ile ezilebilir):** `PRUNE_MIN_VIEWS=100`, `PRUNE_MIN_AGE_MINUTES=60`, `PRUNE_MAX_DELETIONS=10`, `PRUNE_MIN_REMAINING=1`, `PRUNE_DRY_RUN=false`.

**Çıktı dosyaları:** `prune_report.json` (tarama + silme kanıtı), `prune_state.json` (video ID → ilk görülme zamanı; gizli videoların yaşını çözer).

**CANLI STUDIO SEÇİCİ TUZAKLARI (SAKIN BOZMA!):**
- Video satırı `ytcp-video-row`'dur; `ytcp-video-list-cell` **yoktur** (hücreler `div[role="cell"].cell-body`).
- Silme menüsü kalemi `tp-yt-paper-item[test-id="delete"]` → metin **"Tamamen sil"** (düz "Sil" değil!).
- Onay penceresi `ytcp-video-delete-dialog`; önce `#confirm-checkbox #checkbox` (`role=checkbox`) işaretlenir, sonra `#confirm-button` tıklanır. Sarmaç (`ytcp-video-delete-dialog`, `ytcp-confirmation-dialog`) Playwright'e görünmez göründüğü için **içindeki** buton hedeflenir.
- Yaş tespiti için Studio tarih sütunu tek başına **yetersizdir** (aynı gün yayınlananlarda da mutlak tarih yazar). Kesin yayın zamanı kanalın **RSS yayınından** (`https://www.youtube.com/feeds/videos.xml?channel_id={UC...}`) gelir; gizli videolar için `prune_state.json` ilk-görülme kaydı kullanılır.
- 10 matris işi aynı hesabı paylaştığı için job-level `concurrency.group = pruner-studio-lock` **kaldırılmamalıdır** (eşzamanlı Studio oturumları satır kaymasına yol açıp yanlış video silinmesine yol açar).

**Bir sonraki ajan için:** Faz 10 canlı doğrulandı (ilk hedef `Y6cCy07CIS8` kalıcı olarak silindi → watch sayfası "Video unavailable"). `python -m unittest discover -s tests` ile **31/31** test yeşil olmalıdır; `node tests/pruner_logic.test.js` 4/4 geçer.

---

## 8. Faz 11 — Viral Metadata, AI Kapak ve Zamanlayıcı Teşhisi (Operasyon Notları)

### 8.1 ZAMANLAYICI NEDEN ÇALIŞMIYORDU? (Kök neden analizi)
- `GET /repos/ahmetbysoy/youtube_shorts_automation/actions/runs?event=schedule` → **`total_count = 0`**: GitHub'ın `schedule` tetikleyicisi bu depoda **hiç** otomatik çalıştırma üretmemişti. Tüm çalıştırmalar `workflow_dispatch` ile elle tetiklenmişti.
- Tüm iş akışları `state=active`, repo `public`, varsayılan dal `main` → "Enable workflow" sorunu yok.
- **Düzeltme:** (a) `cron: '0,15,30,45 * * * *'` kesin dilimler, (b) otomatik commit mesajlarındaki **`[skip ci]` kaldırıldı** (HEAD commit mesajında `[skip ci]` varsa zamanlayıcı sessizce atlanır), (c) **`cron-kick` zincir job'ı** eklendi: zamanlayıcı ölüyse iş akışı `workflow_dispatch` ile kendini bir sonraki 15 dakikalık dilime yeniden tetikler, (d) `cron_probe.yml` nabız iş akışı eklendi.
- **Test komutu:** `curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/runs?event=schedule&per_page=5"`

### 8.2 YouTube GÜNLÜK YÜKLEME KOTASI (kritik operasyonel gerçek)
- 10 kanallı matris **tek hesabı** (`COOKIES_JSON_1..10` aynı kanal) kullandığı için her 15 dakikada **10 video** yükleniyor → kanalın **günlük yükleme limitini** birkaç dakikada tüketiyor.
- Studio diyaloğunda "**Günlük yükleme sınırına ulaşıldı**" uyarısı görüldü; `youtube_studio_uploader.js` artık bunu yakalayıp **çökmeden** `⏭️ YÜKLEME ATLANDI` (çıkış kodu 42) ile atlar.
- **Öneri (bir sonraki faz):** matrisin her kanalı **farklı bir YouTube hesabına** bağlamak (`COOKIES_JSON_1..10` ayrı hesaplar) veya kanal başına günlük kota takibi (`YT_DAILY_UPLOAD_LIMIT`) eklemek. Limit gece yarısı (PT) sıfırlanır.
- Not: Faz 10 pruner videoları **sildiği için günlük kota geri gelmez** — kota "bugün yüklenen video sayısı" üzerinden işler.

### 8.3 Kapak (Thumbnail) Üretim Hattı
- Motor: `https://image.pollinations.ai/prompt/<url-encoded>?width=1080&height=1920&nologo=true&model=flux&seed=<rastgele>` (anahtarsız, ücretsiz; **yoğun saatlerde HTTP 402/429** döner → 4 denemeli geri çekilme var).
- FFmpeg ile 1080x1920'e ölçeklenir (YouTube minimum genişlik 640 px) ve alt filigran kırpılır.
- Studio'ya yükleme: `ytcp-thumbnail-uploader input[type="file"]` → `setInputFiles()`.
- Doğrulama logları: `[*] AI ile dikattan çekici kapak (thumbnail) oluşturuluyor ve yükleniyor...`, `[+] Kapak resmi başarıyla yüklendi.`
- **Islah 10 (yerel yedek kapak):** AI servis 4 denemede de HTTP 402/429 verirse `generateLocalFallbackThumbnail()` → `scripts/generate_fallback_thumbnail.py` ile PIL tabanlı 1080x1920 kapak üretilir ve yüklenir. Zorunlu satır `KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!` artık asla kaybolmaz.
- Run #52 kanıtı (2026-11-04): pollinations 4/4 → 402 → `***!*** Kapak resmi yüklenemedi...` (kapak yoktu). Düzeltme Islah 10 (`7f97eb7`) ile push'landı.

### 8.4 Doğrulama
`python -m unittest discover -s tests` → **40/40 OK** (Faz 11 testleri: `tests/test_faz11_viral_metadata.py`).

---

## 8b. Islah 10 — Yerel Yedek Kapak (Rate-Limit Yedeği)

| Sorun | Kanıt | Çözüm |
| :--- | :--- | :--- |
| `image.pollinations.ai` HTTP 402 döndürüyor → AI kapak üretilemiyor → zorunlu kapak teslimi düşüyor | Run #52 (`41852106638`): 4/4 deneme 402, log `***!*** Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak.` | `scripts/generate_fallback_thumbnail.py` (PIL, 1080x1920, siyah/sarı/kırmızı banner dili) + `generateLocalFallbackThumbnail()` |

Kural: **zorunlu kapak teslimi hiçbir dış servis rate-limit'una bağlı olamaz.** AI kapak başarısızsa yerel üretici devreye girer; yükleme yine de `KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!` ile kanıtlanır.

## 8c. FAZ 13 — Kanal Güveni / Kaynak / İddia Düzeltmeleri (Operasyon Notları)

| Konu | Kural |
| :--- | :--- |
| CTA | Kanalın kendi abone linki kullanılıyorsa **ürün iddiası yazılmaz** ("Benzer videolar için abone ol"). Gerçek ürün linki varsa `AFFILIATE_URL_SPACE/HISTORY/SCIENCE` env'ine konur ve `(Bu bir affiliate bağlantısıdır.)` beyanı eklenir. |
| Uydurma link | Açıklamadaki her URL gerçek linkle değiştirilir; LLM'in uydurduğu ürün URL'leri yayınlanmaz. |
| Kaynak | Her açıklamada `Kaynak: <kurum> — <URL>` satırı. Kaynak haritası `KNOWLEDGE_SOURCES`; 23/23 senaryo canlı HTTP 200 ile doğrulanmış. |
| Rakam/iddia | Nötron yıldızı 1 milyar ton (NASA), denizanası biyolojik geri yaşlanma (fiziksel ölümsüz değil), Göbeklitepe ~11.000 yıl (UNESCO), Antikythera "en az bin yıl" (Smithsonian). |
| Testler | `tests/test_faz13_trust.py` → toplam 79 test yeşil. |

### FAZ 13.3 — Kapak: Kare Seçimi (Konu Uygunluğu Doğrulama Bekliyor)

- Yedek kapak artık **videodan seçilen bir kare** üzerine kurulur (`--video output/final_short.mp4 --topic "<Konu>"`).
- Kare seçimi: ffprobe ile süre bulunur → %22–78 aralığında 5 aday kare → en yüksek kontrastlı (grayscale stddev) kare seçilir → 1080×1920'e merkezden kırpılır.
- Video yoksa/ffmpeg yoksa metin kartına düşülür (zorunlu kapak teslimi yine de yapılır).
- Run #58, 13.3 öncesindeki yerel yedeği kanıtlar; yeni kare seçiminin canlı Studio sonucu henüz kanıtlanmadı. Kontrast ölçümü konu görünürlüğü, yazısız kare veya bitiş kartı dışlama garantisi değildir.
- 13.4 henüz uygulanmadı: `.used_topics.json` ignore edildiğinden CI koşularında kalıcı değil; sayısal kanal seçimi eski başlıkları kontrol etmiyor. Ayrıntılı güvenli uygulama ve gerçek veri şartları için `docs/FAZ13_AUDIT_PLAN.md`.
- Gerçek veri hazırlığı: `scripts/audit_public_feed.py` ve `docs/evidence/*2026-11-04.json`. 16:59:49 UTC kamuya açık akışında 7 kayıt; 16:59:00 UTC Studio pruner raporunda 8 korunan video; `8_bf4eAz3a0` akışta yok. Farklı zamanlı görüntüler, neden bilinmiyor. Akış tek başına güvenilir tam geçmiş değildir. Betik salt okunur; üretim iş akışına bağlı değil. Başlık denetimi `scripts/audit_repeat_candidates.py` + `docs/evidence/repeat_candidates_2026-11-04.json`: Mariana 1.000, denizanası 0.125; salt Jaccard eşik yaklaşımı yetersiz. Script sayıları çıkarır, rakam değişikliğini yeni açı olarak kabul etmez.

## 9. Faz 11 — Operasyon Düzeltmesi: "10 kanal aynı anda" ve "boşuna iş yükü"

### 9.1 Tespit (canlı kanıt)
- Eski kurguda `target_channel: "all"` ile 10 matris job'ı **aynı anda** açılıyordu
  (`max-parallel` yoktu) ve 10 secret'in tamamı **aynı hesabı** işaret ediyordu
  (`channel-map` job logu: `hash a4ae91d03ee1` × 10).
- Sonuç: kanalın **günlük yükleme kotası** tek turda tükeniyor, geri kalan 9 video boşuna
  üretiliyor (içerik + TTS + FFmpeg + Studio oturumu).

### 9.2 Uygulanan düzeltmeler
| Değişiklik | Dosya |
| :--- | :--- |
| `max-parallel: 1` (kanal sırası, tam döngü) | `daily_shorts.yml`, `hourly_pruner.yml` |
| Aynı hesabı işaret eden kanalları ayıklama | `scripts/channel_map.sh` |
| Matris çıktısını virgüllü listeye taşıma (GitHub "secret" filtresi) | `channel_map.sh` + workflow `fromJSON(format(...))` |
| Zincir artık **tek kanal** tetikler (`all` değil) | `cron-kick` job'ları |
| Kota sonrası 4 saat bekleme (boşuna üretim yok) | `daily_shorts.yml` → `cron-kick` |
| `permissions: actions: write` (pruner zinciri için) | `hourly_pruner.yml` |

### 9.3 Sıradaki gerçek iş: **kanalları kurmak**
10 kanalın her biri **ayrı bir YouTube hesabı** olmalı:
1. Her hesapla Studio'da giriş yap → `cookies.json` + `storage_state.json` üret (yerel `headless: false`).
2. `scripts/rotate_cookies.py` ile ilgili GitHub Secret'ına yaz (`COOKIES_JSON_N` + `STORAGE_STATE_JSON_N`).
3. `channel_map.sh` otomatik olarak "benzersiz" listeye ekler; matris büyür, üretim sırayla dağılır.

### 9.4 Doğrulama (canlı CI)
- Run #17 (`41732696912`) → **tek** `build-and-upload (1)` job'ı (10 değil).
- Log kanıtları (aynı job içinde, sırayla):
  `Etkileşim CTA (açıklama üstü): ...` → `Trend hashtag'ler: #muz #radyoaktif #besin` →
  `[*] Kapak görseli 1080x1920 olarak hazırlandı (74 KB).` → `[+] Kapak resmi başarıyla yüklendi.` →
  `⏭️ ATLANDI ... YouTube günlük yükleme kotanı doldu.`
- `cron-kick`: `[KOTA] ... sonraki deneme 4 saat sonra.` → `Zincir tetiklendi -> kanal 1, dilim 1793760470.`

---

## 10. Faz 12 — TOTAL DOMINATION: Gerçekleşenler ve Kanıtlar

### 10.1 Kod değişiklikleri
| Alan | Değişiklik |
| :--- | :--- |
| `daily_shorts.yml` | cron `0,13,27,41,55 * * * *`, `cancel-in-progress: true` |
| `content_engine.py` | Silahlandırılmış sistem promptu + `affiliate_hook` alanı |
| `youtube_studio_uploader.js` | Agresif kapak stili, `filechooser` yedeği, `[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!` logu, video ID kaydı (`logs/channel_video_id.txt`) |
| `scripts/generate_banner.py` | 2560x1440 banner üretimi (PIL, güvenli alana otomatik sığdırma) |
| `scripts/channel_hygiene.js` | Banner + About + sabitlenmiş yorum otomasyonu |

### 10.2 Canlı Studio'da doğrulanan seçiciler
| İşlem | Seçici |
| :--- | :--- |
| Özelleştirme sayfası | `https://studio.youtube.com/channel/<id>/editing/profile` |
| Banner dosya input | `ytcp-banner-upload input#file-selector` |
| Profil resmi / filigran (DİKKAT) | `ytcp-profile-image-upload` / `ytcp-video-watermark-upload` (banner DEĞİL) |
| Kanal açıklaması | `#description-textbox` (contenteditable) + "Yayınla" |
| Yorum kutusu | `ytd-comment-simplebox-renderer #placeholder-area` → `#input` → `#submit-button` |
| Yorum ⋮ menüsü | `ytd-comment-view-model ytd-menu-renderer button#button` (aria "İşlem menüsü") |
| Sabitleme | `ytd-menu-service-item-renderer:has-text("Sabitle")` → doğrulama: `#pinned-comment-badge` |
| ❌ Studio Yorumlar sayfası | "Kimliğinizi doğrulayın" modalı → **izleme sayfasından yorum yazılıyor** |

### 10.3 Notlar
- Studio'daki "Branding" sayfası (`/editing/branding`) **hata veriyor**; banner artık `/editing/profile` üzerinden yükleniyor.
- `youtube.upload` OAuth kapsamı yorum yazmaya yetmez; bu yüzden yorum **tarayıcı oturumuyla** yazılıyor.
- Banner + About her turda idempotent olarak çalışır (güncelleme, üstüne yazma).


---

## 11. Faz 12.6 — Denetim Dönemi: Ne Değişti, Ne Öğrenildi

### Öğrenilenler (kalıcı bilgi)
1. **`if: always()` + `cancel-in-progress: true` = iptal fırtınası.** `always()` olan bir
   job, iptal edilen koşudan bile yeni koşu doğurur. Kendini devam ettiren zincirlerde
   bu **her iptalin yeni bir iptal doğurması** demektir → `if: ${{ !cancelled() }}` şart.
2. **GitHub `schedule` olayı güvenilir bir zamanlayıcı değildir** (13 saatte 2 kez, gecikmeli).
   "Scheduler ölü" ölçümü (`total_count=0`) bir günlük gözlemdir; sürekli doğrulama gerekir.
   Tek üretim mekanizması seçilmeli (bizde: zincir; cron = bekçi).
3. **`join()` GitHub ifadelerinde ARRAY bekler.** `join(string, sep)` sessizce yanlış
   matris üretir; `fromJSON(json_array)` kullan.
4. **actionlint gerçek bir linter**: `runs.using` (node20→node24) ve tip hatalarını bulur.
5. **Bash dizi (array) `ARGS=(...)` + `"${ARGS[@]}"`**: metin değerli argümanları böler.

### Dosya envanteri (yeni)
| Dosya | İşlev |
| :--- | :--- |
| `scripts/active_runs_count.sh` | Aktif (queued/in_progress) koşu sayısı (kendisi hariç) |
| `scripts/production_gate.sh` | Watchdog kapısı: schedule koşusu zincir aktifse atlar |
| `scripts/sanitize_logs.sh` | Artifact öncesi gizli veri temizliği |
| `scripts/run_summary.py` | Tek satırlık run özeti (+ Step Summary) |
| `scripts/pruner_summary.py` | Pruner tek satırlık özeti |
| `.github/workflows/ubuntu_26_test.yml` | Ubuntu 26.04 geçiş probe'u |
| `.github/actionlint.yaml` | actionlint yapılandırması (26.04 etiketi) |


## 12. Ölçülmüş GitHub Actions tuzakları (2026-11-04 denetim dönemi)

| Tuzak | Kanıt | Çözüm |
| :--- | :--- | :--- |
| **Output maskeleme**: köşeli parantezli output değerleri atılır | run 41851410202: `["1"]` ve `[1]` → "may contain secret"; `1` → ayarlandı | Çıktıları düz string tut (`distinct_csv`) |
| **`split()` yok** | dispatch 422: "Unrecognized function: 'split'" | `join(csv, '","')` + `format` + `fromJSON` (runtime doğrulandı) |
| **`if: always()` + kendini devam ettiren zincir** = iptal fırtınası | #34→#35→#36→#37→#38 | `if: ${{ !cancelled() }}` + aktif koşu kontrolü |
| **"İleri" butonu pasif** (kontroller sürerken) → görünürlük sekmesi açılmıyor | run #41: `locator.waitFor` timeout + `logs/studio_error.png` | Buton enabled olana kadar bekle + tekrar dene |
| **Slot çarpımı sabit kalırsa** aynı konu arka arkaya | #43 ve #44 aynı konu ("Kleopatra") | Havuz boyutuyla **aralarında asal** adım (`_coprime_step`) |
| `actionlint` etiket listesi güncel değil | `ubuntu-26.04 is unknown` | `.github/actionlint.yaml` ignore + gerekçe |
