> **Güncel — 2026-11-18 (Faz4D TAM KABUL ✅): Cookie-only stok medya kanıtı.** Kullanıcı GitHub Repository Secrets içine `PEXELS_COOK` ve `PIXABAY_COOK` ekledi. `video_fetcher.js` tamamen yeniden yazıldı: **her sağlayıcı için ayrı Playwright context** (cookie domain izolasyonu, `.pexels.com` / `.pixabay.com` katı filtreleme), HTTPS allowlist host kontrolü, maksimum 4 redirect, Content-Type/HTML reddi, SHA256 hash, ffprobe (codec/çözünürlük/süre) + ffmpeg tam decode doğrulaması, Pexels HD/UHD önceliği + video detay sayfası fallback'i, Pixabay `_large`/`_medium` kalite seçimi (`_tiny` asla). Cloudflare stealth (Mac UA, webGL/navigator taklidi, anasayfa ısınma, 403 retry, headless `--disable-blink-features=AutomationControlled`). `--portrait`, `--metadata`, `--min/width/height/duration/bytes`, `--diag-file` argümanları. **Canlı CI probe kanıtı [44380726215](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44380726215) HER İKİ SAĞLAYICI DA GEÇTİ:** Pexels 1920×1080 9.7s 6.0 MB h264 tam decode; Pixabay 1920×1080 11.1s 3.2 MB h264 tam decode. Güvenlik: `MEDIA_COOKIES_JSON` birleştirme adımı kaldırıldı; `cookies.json` SADECE YouTube oturumu; medya cookie'leri `PEXELS_COOK`/`PIXABAY_COOK` env'lerinden yalnız `safe_names` üzerinden Node child'a geçilir (YouTube/Gemini/GitHub/API key'leri ASLA); indirme yapmaz metadata alır; host validasyonu; cookie değerleri hiçbir log/artifact/committe görünmez (URL query'leri sansurlenir). 16 cookie izolasyon birim testi + 145 Faz4 testi geçti. `stock_cookie_probe.yml` manuel workflow eklendi (keyword/min/max_duration parametreleri, preflight domain kontrol, her sağlayıcı ayrı adım, JSON rapor artifact'i). Kapak tarafında kullanıcı isteğiyle tüm post-process/siyah bant/crop mantığı kaldırıldı; `postProcessImage` no-op, `kapak_gemini.json` kullanıcının orijinal prompt'una döndürüldü; tüm Shorts'lar için gerçek kapak koşusu [44143330207](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44143330207) tetiklendi.
>
> **Güncel Faz 5 — 2026-11-16: UYGULANDI / KABUL BEKLİYOR.** Commit `7195e54` + sertleştirme; fail-closed timing, SRT sahne sınırları, sessizlik+clipping QC, 38 test (5'i gerçek edge-tts ağı) geçti; CI (phase4g_e2e_no_upload) bekleniyor. [Kabul raporu](docs/evidence/PHASE5_ACCEPTANCE.md). Faz6 başlatılmadı.
>
> **Tarihsel Faz 4C — 2026-11-18: Faz4B NOT_ACCEPTED.** Kaynak [`14f7896`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/14f78962f2444e9d03fe0d0caf9b22efff06d927); yeni CI [44313713933](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313713933) **361 Python + 16 alt test**, hedefli tekrar **35/182/8**, **16 Node** geçti. Kullanıcının yeni cookies’i **API kullanılmadan** [44313751238](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313751238) Actions koşusunda test edildi: preflight **8 Pexels + 7 Pixabay eşleşen cookie kaydı**, iki ayrı browser araması **HTTP403 / blocked_unverified**. Commons iki CC BY videoda source/deed/download **200**, tam byte/SHA256 ve container probe geçti; **full_decode_failed**, render/final QC not_reached. API/ENV_FILE bu run’da okunmadı; API key eksikliği cookie testi için blocker değildir. Yeşil CI/offline fixture veya eski yerel Commons, yeni canlı kabul yerine geçmez. Önceki iki-run history/gerçek409 proof’unun üç blob’u aynı; cleanup dört404 ile salt-okur tekrar doğrulandı, yeniden dispatch edilmedi. **22 protected blob, 26 topic/0pending** korundu; üretim/yayın/silme yok. [12 başlıklı yeni rapor](docs/evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) · [JSON](docs/evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json).

> **Tarihsel Faz4B snapshot’ı:** Kaynak `59e2c79`, CI44301070745 **301+16/35/122/8/11Node**; eski yerel canlı Commons tam zinciri geçti, eski Actions44301095341 stock403 ve generic Commons download/decode failure verdi. Bu eski kayıtlar yeni koşu değildir; [Faz4B raporu](docs/evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) ve [JSON](docs/evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json) değiştirilmeden korunur.

> **TARİHSEL FAZ3 DEVİR NOTU — 2026-11-18:** **Gemini Faz 3 yayınsız kabul kapısı geçti.** Feature `c2729cc`, CI ortam düzeltmeleri `28e1d6e` / `0dee88e` main’e push edildi. Doğrulanmış kaynak commit’i `0dee88e18e05269e7d4f7360614123eb890f4e80`; Ubuntu 26 CI [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) **success**, **171 passed + 16 subtests**, ayrı hedefli suite **35 passed**. Sonraki iki bot commit’i yalnız `.used_topics.json` kalıcı durumunu güncelledi (`c421f2b` reserve, `a86ab5c` release); sonraki belge commit’i kodu değiştirmez. Güncel HEAD için `git log -1` kullan.

> **TARİHSEL FAZ4 SONUCU — 2026-11-18:** **Tam kabul GEÇMEDİ; kısmi canlı provider kanıtı.** Kod `eb99109` → `c2ad1c9` → `c29f7e7` → [`e4d1144`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/e4d1144116887b31c459bb6a7e171589d214c687) push edildi. Aynı son SHA üzerinde CI [44288761602](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761602) **233 + 16 subtests**, ayrı **62 Faz 4 / 35 Faz 3**, 5 Node parser testi başarılı. Yayınsız canlı [44288761461](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44288761461) **partial_provider_evidence**: Commons 2 PD still + gerçek decode/render/QC geçti; Pexels/Pixabay bu env’de API key yok/cookie file var/üç browser query HTTP 403, dolayısıyla blocked_unverified. İlk FFmpeg `yuvj420p` hatası strict range/CFR ile, sonraki uploader-credit bütçe riski uploader değiştirilmeden UTF-16 preflight ile giderildi. [Final kanıt](docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md), [tasarım](docs/PHASE4_MEDIA_ENGINE.md). Metadata relevance ≠ görsel anlam; sentetik tone ≠ TTS. Gerçek atıf-gerektiren/hareketli provider asset ve ayrı medya-history iki-run proof açık. Faz 5 ve Faz 1 consumer işleri kapanmaz. Prod/pruner/publisher kullanma; mevcut Faz 3 kabulünü tekrar koşma.

>
> İki ayrı Actions koşusu [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395) (`reserve`) ve [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635) (`verify`) başarılı: aynı `probe_id=phase3-20261118` rezervasyonu ikinci koşuda GitHub Contents API’den okunup release edildi. `pending` **0 → 1 → 0**, legacy **25 başlık korundu**, test başlığı `used_titles` / `used_records` içine yazılmadı. [Actions kanıtı](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md) ve [makine okunur kayıt](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.json). Gerçek CAS race/conflict yalnız mock testlidir; canlı kanıt iki sıralı koşunun kalıcılığıdır.
>
> Korunacak eski gerçek Gemini Web kanıtı: [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017), SHA `57166f8`, 58 kelime/5 sahne/3 claim, `draft_only=true`, `publish=false`, fact check `partial`. Yeni Faz 3 koduyla canlı model/YouTube yayın testi değildir. Cookie-only Gemini Web, mevcut fallback, `GEMINI_COOK` ve kullanıcı onaylı `partial` publication behavior korunur; `partial`, `verified` diye yeniden etiketlenmez.
>
> Sıradaki iş: Faz 4 canlı stock erişimi/atıf-gerektiren ve hareketli asset kanıtı; ayrı medya-history persistence ve Faz 1 gerçek tüketici zinciri açık. Yeni strict source/licensing/manifest/dedup kodu var, tam kabul yok; Faz 5 timing/audio ayrı. **`daily_shorts.yml`, `hourly_pruner.yml`, `draft_publisher.yml` bu kabul için tetiklenmedi; test amacıyla tetikleme.** Gerçek üretim adımının başarılı/başarısız finalization yolu uçtan uca denenmedi; CLI import/komutları ve CAS/release davranışları test edildi. Yeni Gemini model çalışması veya yayın izni çıkarma.
>
> Güvenlik: Kullanıcının belirttiği ignore edilmiş `/home/user/repo_review/jeton/github_erisim.json` dosyasındaki geçerli credential kullanıldı; dosya adı JSON olsa da iç biçimin geçerli JSON olduğu varsayılmamalı. Değeri asla yazdırma/loglama/stage etme; token’ı remote URL veya `.git/config` içine koyma. Başarılı üç run log taraması temiz; artifact sayısı 0. Repository Secret’lar değiştirilmedi. `hourly_pruner.yml` gerçek video silebilir, `draft_publisher.yml` PUBLIC yapabilir.
> **Faz 15:** [Canlı plan ve TODO](docs/FAZ15_TAM_OTONOM_KANAL_VE_KAPAK_TODO.md). 08:39 UTC HAR Studio envanterinde 58 PUBLIC + 3 taslak; PUBLIC kapaklar ve örnek kareler, taslak önizlemeleri incelendi. Baştan sona video/ses ve iddia doğrulaması yapılmadı. Gerçek #123 yükleme işi PUBLIC başarılı, workflow geneli cron-kick iptal; günlük özel kapak kotası dolu ve hiçbir mevcut kapak değiştirilmedi. Gemini kare eşleşmesi canlı örnekte yanlış pozitif olduğundan otomatik kabul varsayılan kapalı, test amaçlı istisna dışında yerel temsili karta düşülür. Kullanıcı kota doluyken YouTube otomatik kapağıyla yayını seçti; ücretli API açma. 58 PUBLIC ID için yüklenmemiş temsili adaylar var; iki final short konusu yalnız otomatik altyazıdan alındı, ses doğrulaması gerekir. `41996283537` tek olumsuz gerçek örnekte ret success; otomatik kare kabulünü tek teste bakarak açma.

> **Güncel operasyon notu (5 Kasım 2026):** Kullanıcı önceki silme isteğini değiştirerek tüm taslakların PUBLIC yayınını seçti. 26 mevcut video Studio’da aynı ID üzerinden PUBLIC doğrulandı; silme yapılmadı. [Kanıt listesi](docs/evidence/draft_publications_2026-11-05.md). İki başlık `final short`; içerik tekrarı, görsel uyumu ve açıklamalar çözülmedi. Aktif otomasyon/pruner değiştirilmedi. Önceki bloklar tarihsel kanıttır.

> **Faz 14 uygulama:** `scripts/gemini_frame_selector.py` ücretsiz text/vision endpointini en fazla bir kez kullanır; `vars.GEMINI_FREE_VISION_ENABLED` kod varsayılanı 0; repo değişkeni şu anda 1. Yeni görsel üretmez. Gerçek CI kare incelemesi `41988709577` başarılı; Studio kapak yükleme kanıtı henüz yok; Google projesine billing bağlanırsa text API ücretli olabilir, değişkeni kapat. **(2026-11-22 GÜNCELLEME: Bu API yolu kullanıcı kararıyla tamamen kaldırıldı — `gemini_frame_selector.py`, `free_gemini_probe.yml`, `free_gemini_frame_rejection_probe.yml`, `docs/FAZ14_FREE_GEMINI_KAPAK_PLANI.md` silindi; repo değişkeni ve workflow env bağlantısı söküldü.)**

> **Faz 14:** Kullanıcı ücretli AI görsel API kullanımını reddetti; plan dokümanı (`docs/FAZ14_FREE_GEMINI_KAPAK_PLANI.md`) 2026-11-22'te API yoluyla birlikte silindi. Google API key 2026-11-22'te kullanıcı kararıyla koddan ve workflow'lardan tamamen söküldü; artık hiçbir yerde okunmaz. Şu an ücretsiz proje olduğu Studio UI üzerinden gözlendi; API görüntü üretimi ücretsiz değildir.

> **Son Güncelleme:** `2026-11-20` (Faz 5 gerçek TTS scene timing geliştirmesi — Edge-TTS WordBoundary milisaniye zaman damgalarindan sahne sinirlari hesaplaniyor, SRT sahne-kesimlerine duyarli, ses sessizlik/clipping QC eklendi; 18 yeni test, 372 toplam test gecti; [PHASE5_ACCEPTANCE.md](docs/evidence/PHASE5_ACCEPTANCE.md)). Onceki Faz 4K: Faz4G kosusu [44700976069](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44700976069) @f8a53b9 SUCCESS (39/39 QC, 0 hata); [PHASE4K_ACCEPTANCE.md](docs/evidence/PHASE4K_ACCEPTANCE.md))
> **Hedef Kitle:** Bu projeyi devralacak bir sonraki Yapay Zeka Ajanı (Arena Agent, Claude Code, Cursor, Codex vb.) veya Geliştirici.

Bu belge, projeyi devralan bir yapay zekanın **sıfır tahmin, sıfır deneme-yanılma ve sıfır güvenlik ihlali** ile 30 saniye içinde sistemi anlayıp geliştirmeye devam edebilmesi için hazırlanmıştır.

---

## 1. Projenin Anlık Durumu (Executive Summary)

Proje; Türkçe YouTube Shorts içeriklerini **senaryo -> seslendirme (`edge-tts`) -> kelime senkronlu `.ass` altyazı -> dikey `1080x1920` FFmpeg montaj -> Playwright YouTube Studio üzerinden sıfır API kotasıyla doğrudan `PUBLIC` (Herkese Açık) yayın** adımlarıyla uçtan uca otonom üreten bir içerik fabrikasıdır.

| Bileşen | Durum | Detay |
| :--- | :---: | :--- |
| **GitHub Deposu** | ✅ Aktif | `https://github.com/ahmetbysoy/youtube_shorts_automation` (`main` dalı) |
| **YouTube Kanalı** | ✅ Aktif | `@mentansiytas` — `https://studio.youtube.com/channel/UCBZVbwc7s7TeUCcOaN58oHQ` |
| **Birim Testleri** | ✅ `361 + 16 subtests` | Yeni CI 44313713933 @14f7896; ayrı altküme tekrarları 35 Faz3 / 182 medya / 8 gerçek fixture consumer, 16 Node. Mock/offline provider testleri canlı kanıt değildir; medya44313751238 failure |
| **Tarihsel motor fazları (Gemini Faz 4 kabulü değil)** | Eski kayıt | İçerik/TTS (`content_engine.py`), Montaj (`src/media_processing/media_processor.py`), OAuth/API yedek modülü (`src/youtube_upload/`) |
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
Aşağıdaki **33 secret** listesi tarihsel başlangıç envanteridir; bugünkü tam liste/anahtar geçerliliği diye kullanma. Faz 4’te read-only REST isim taraması ve probe runtime presence boolean’ları kullanıldı; değerler getirilmedi/değiştirilmedi. Probe’a iki stock API key ulaşmadı; ENV_FILE veya hesap geneli hakkında daha geniş çıkarım yapma:
- **10'lu Matris Kanalları (`1..10` — Aktif Kullanımda):**
  - `ENV_FILE_1` .. `ENV_FILE_10`
  - `COOKIES_JSON_1` .. `COOKIES_JSON_10`
  - `STORAGE_STATE_JSON_1` .. `STORAGE_STATE_JSON_10`
- **Tekil / Yedek Geriye Dönük Uyumluluk:**
  - `ENV_FILE`, `COOKIES_JSON`, `STORAGE_STATE_JSON`
- **Stok Video Cookie'leri (18 Kasım 2026 akşamı eklendi, canlı çalışıyor):**
  - `PEXELS_COOK` — Pexels oturum cookie'leri (JSON dizi veya "k=v; k=v" string). `video_fetcher.js` Playwright ile Cloudflare'i geçer.
  - `PIXABAY_COOK` — Pixabay oturum cookie'leri (aynı format).
  - Format ayrıntıları ve nasıl çıkarılacağı `.env.example` ve `README.md`'de yazılı.
- **API / AI / Hizmet Anahtarları:**
  - `GEMINI_COOK`, `GROQ_API_KEY` (LLM/Gemini Web; `GEMINI_API_KEY` 2026-11-22'te kullanıcı kararıyla tamamen kaldırıldı, artık yoktur ve okunmaz)
  - `PEXELS_API_KEY`, `PIXABAY_API_KEY` (opsiyonel; cookie varsa kullanılmaz)
  - `REPO_PAT` (artifact/secrets yönetimi)

> **14 Günlük Cookie Rotasyonu (`scripts/rotate_cookies.py`):** Google'ın bulut IP'lerinde oturumu düşürmemesi için her 14 günde bir yerelde `node youtube_studio_uploader.js` çalıştırılıp taze `cookies.json` ve `storage_state.json` alındıktan sonra tek komutla tüm kanallara (veya belirli bir kanala) basılır:
> ```bash
> GITHUB_TOKEN="..." python scripts/rotate_cookies.py --channels 1-10
> ```
> **Yeni Bağımsız Kanallar Ekleme:** 2'den 10'a kadar yeni Gmail/YouTube hesapları açıldığında kodda **sıfır değişiklik** gerekir; ilgili hesabın oturum dosyalarıyla `python scripts/rotate_cookies.py --channels 2 --env-file .env.ch2 --cookies-file cookies_ch2.json --state-file state_ch2.json` çalıştırmak yeterlidir.

---

## 3. Kullanıcı Kuralları ve Kesin Kısıtlamalar (User Standing Instructions)

1. **Güncel kabul kuralı (18 Kasım):** Mock/stub birim testleri gereklidir ama gerçek provider/Actions kanıtı diye sunulmaz. Sabit probe girdisi ve sentetik tone açık etiketlenir. **Bu doğrulama görevinde gerçek yükleme, silme ve taslak PUBLIC yayını yasaktır**; eski “yalnız gerçek yükleme” ifadesi burada test izni vermez.
2. **Anında GitHub Senkronizasyonu:** Yapılan her kod değişikliği ve her dokümantasyon güncellemesi bekletilmeden `git add` -> `git commit` -> `git push origin main` ile GitHub'a gönderilmelidir.
3. **Tek Seferlik Giriş & Kalıcı Oturum:** `cookies.json` ve `storage_state.json` mevcutken tekrar tekrar 2FA onayı istenmez; yalnızca oturum tamamen düşerse telefondan onay istenir.
4. **Mevcut `PUBLIC` davranışını koru:** Üretimin tarihsel PUBLIC politikası ve kullanıcı onaylı `partial` yolu onaysız değiştirilmez. Bu, Faz 4/5 kabulü veya test yayını izni değildir; `partial` asla `verified` olmaz. `daily_shorts.yml`, `hourly_pruner.yml`, `draft_publisher.yml` test-dispatch edilmez.

---



## Zorunlu GitHub Actions Cache Standardı

Sonraki tüm ajanlar ve geliştiriciler, workflow eklemeden veya kurulum adımlarını değiştirmeden önce [`docs/GITHUB_ACTIONS_CACHE_POLICY.md`](docs/GITHUB_ACTIONS_CACHE_POLICY.md) belgesini okumalı ve uygulamalıdır. Ortak kurulum/cache noktası `.github/actions/setup-tools/action.yml` dosyasıdır. Aynı bağımlılık kurulumunu workflow'larda kopyalamayın; ortak action'ı kullanın veya geriye uyumlu biçimde genişletin. Secret, cookie, oturum ve üretim verileri cache'e alınmaz. Cache hit/miss, smoke test ve süre ölçümü doğrulanmadan optimizasyon tamamlandı sayılmaz.

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
.venv/bin/pip install --no-cache-dir -r requirements.txt -r requirements-test.txt
npm install
npx playwright install --with-deps chromium

# 4. Tam test suite (233 test + 16 subtest; remote history credentials child process’ten kaldırılır)
env -u GITHUB_REPOSITORY -u GH_TOKEN -u GITHUB_TOKEN .venv/bin/python -m pytest -q tests
npm test
node --test tests/stock_media_catalog.test.cjs
npm run test:syntax

# 5. TARİHSEL ÜRETİM KOMUTU — Faz 4 kabul/test görevi için ÇALIŞTIRMA (PUBLIC yayınlar)
xvfb-run -a --server-args="-screen 0 1366x900x24" .venv/bin/python main.py
```

### Tarihsel üretim dispatch örneği — bu doğrulama görevinde KULLANMA

```bash
curl -X POST \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/ahmetbysoy/youtube_shorts_automation/actions/workflows/daily_shorts.yml/dispatches \
  -d '{"ref":"main"}'
```

---

## 6. Sıradaki Güvenli Adımlar (Faz 4 tam kabulü geçmedi)

1. Önce `git status`, `git log -1`, [canlı TODO](docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md) ve [Faz 4 kanıtını](docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md) oku. Son doğrulanan uygulama `e4d1144`, CI **44288761602**, live **44288761461**; sonraki docs commit'i uygulama kanıtını değiştirmez. Mevcut dört Faz 4 live probe'u veya accepted Faz 3 reserve/verify'ı körlemesine tekrar dispatch etme.
2. Stock engeli: iki sağlayıcı için bu run'da api_key_present=false, media_cookie_file_present=true ve üçer browser query 403. Süresi dolmuş cookie/anahtar yokluğu gibi daha geniş teşhis uydurma. İzinli erişim ve mevcut güvenli secret konfigürasyonu sağlanmadan yeni başarı kanıtı yok. Değerleri kullanıcıdan mesaja yapıştırmasını isteme, loglama, lisans/403 kapısını gevşetme.
3. Kodda strict `scene_media.py` + providers/IO/ayrı history var. Bütün provider'lar query başına toplanıp global puanlanır; yanlış storyboard legacy'ye düşmez. Required atıf 4900 UTF-16 bütçesine ve uploader'ın olası CTA/hashtag eklemesine sığmalı; mevcut uploader'ı değiştirmeden fail-closed. Metadata_supported, visual_verification=not_performed; iki live still'in biri rover, diğeri 1888 kule inşaatı; exact action/era garantisi verme.
4. Ayrı media history CAS'ı mock testli, gerçek cross-Actions persistence açık; probe production `.media_history.json` yazmaz. `.used_topics.json` Faz 3'e aittir (25/0, blob e5a987f); test yan etkisini commit etme. Unit child'dan GITHUB_REPOSITORY/GH_TOKEN/GITHUB_TOKEN kaldırılır, üretim fail-closed gevşetilmez. Faz 3 kabulü ve mevcut PUBLIC/partial politikası korunur.
5. Faz 1 ek [producer/consumer taraması §7](docs/PHASE1_SCRIPT_JSON_INVENTORY.md) bağımsız eski `src/content_generation/engine.py` writer'ını ve uploader metadata dönüşümünü ortaya çıkardı; tam runtime inventory ve gerçek root content/TTS → production media CLI → cover → yayınsız tüketici zinciri hâlâ açık. Probe selector+assemble gerçek, wrapper testleri kısmen mocked. Faz 5 gerçek TTS alignment/ses QC tamamlanmadı.
6. **`media_processor.py --help` çalıştırma:** bu CLI flag parse etmez ve montaj başlatır. Yerel yanlış çağrı legacy samples yolunu çalıştırdı; samples JSON geri alındı ve ignored MP4/ASS ayrıldı; strict kabul sayılmaz. Güvenli kontrol `python -m py_compile ...`, izole testler ve gerçek argparse içeren `python -m scripts.phase4_media_probe --help` / topic-history CLI'larıdır. `main.py`, gerçek uploader, prod/pruner/publisher bu test için yasak; yeni paid API ekleme.
7. [Faz 3 kanıtı](docs/evidence/PHASE3_ACTIONS_EVIDENCE_2026-11-18.md) korunur: CI 44279794329, reserve 44280024395 → verify 44280111635. Bunlar media history/TTS/YouTube publication kanıtı değildir. Sekiz Faz 4 CI/live job logu ve JSON known-credential/pattern taraması temiz; repository secret değiştirilmedi. İlk FFmpeg hatası tarihsel raporda saklandı.

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
- Tarihsel 13.4 audit: `.used_topics.json` title-only state ve eski CI gözlemleri. Gemini Faz 3 bu dosyaya CAS topic/core-claim reservations ekledi; gerçek two-run Actions proof henüz pending, ayrı Faz13 audit planı bu proof yerine geçmez.
- Gerçek veri hazırlığı: `scripts/audit_public_feed.py` ve `docs/evidence/*2026-11-04.json`. 16:59:49 UTC kamuya açık akışında 7 kayıt; 16:59:00 UTC Studio pruner raporunda 8 korunan video; `8_bf4eAz3a0` akışta yok. Farklı zamanlı görüntüler, neden bilinmiyor. Akış tek başına güvenilir tam geçmiş değildir. Betik salt okunur; üretim iş akışına bağlı değil. Başlık denetimi `scripts/audit_repeat_candidates.py` + `docs/evidence/repeat_candidates_2026-11-04.json`: Mariana 1.000, denizanası 0.125; salt Jaccard eşik yaklaşımı yetersiz. Script sayıları çıkarır, rakam değişikliğini yeni açı olarak kabul etmez. `scripts/build_verified_history.py` + `docs/evidence/observed_history_2026-11-04_1711.json` kanal eşleşmesini doğrulayarak 7 kayıtlı Atom görüntüsü ve 8 kayıtlı gerçek Studio raporunu 9 ayrı ID halinde birleştirir. Studio gözlem zamanı yayın zamanı değildir. `BlrZMXlIbU0` ve `T_yIHvyUY2Y` aynı Antikythera başlığını taşır. Bu offline gözlem geçmişi üretime bağlı/kalıcı koruma değildir.

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

## Yayın olayı — 5 Kasım 2026

- Run #90 (`41939518221`) `studio_error.png`: zorunlu çocuklara özel seçimi yanıtlanmamış, İleri pasif; PUBLIC seçicisi timeout. Sadece bu koşunun nedeni kanıtlıdır.
- `youtube_studio_uploader.js`: hedef radyo görünür olana kadar bekler, seçimi `aria-checked` ile doğrular; PUBLIC için de aynı kontrol. Yayın sonrası yeni video ID'sinin Studio satırında PUBLIC ikon ve etiketi aranır; yoksa `publish_unverified`, yeniden yükleme öncesi insan kontrolü. Yerel eski video ID temizlenir.
- Studio'da gerçek taslakta çocuk seçimi `true`; eski PUBLIC video `1IAgNqsjgvQ` üzerinde görünürlük seçicisi doğrulandı. Yeni versiyonla uçtan uca yayın henüz kanıtlanmadı.
- Tarihsel 5 Kasım notu: o tarihte CI `--force-fallback` kullanıyordu. Gemini Web cookie-only route'unun gerçek, yayın yapmayan başarılı run'ı 44262444017'dir. Yeni Faz 3 code için Ubuntu 26 CI/two-run persistence proof pending. `docs/AI_VIDEO_HERO_PROMPT.md` ayrı medya arama yönergesidir; scene-to-media semantic suitability hâlâ açık.
- Cleanup sırasında `daily_shorts.yml` geçici durduruldu; run #96 iptal edildi ve workflow tekrar etkinleştirildi. Studio 25 taslak/0 başka kayıt seçimine rağmen kimlik doğrulaması istedi; hiçbiri silinmedi.
- Run #97 (`41948576364`): build-and-upload başarılı, `7DULxjp6PsQ` Studio PUBLIC doğrulandı ve girişsiz player OK. Cron-kick yeni 01:45 UTC zincirini tetiklerken run geneli cancelled.
- Tarihsel 13.4/kalite bulgusu: canlı videodaki uçak, yan dönmüş kıyı ve alakasız yazılı grafik Zanzibar savaşına uymuyordu; kalite başarısızdı. `WKYwF96hQzg` aynı başlığın başka PUBLIC videosu. Sonraki Gemini Faz 3 kodu tekrar korumasını ekledi; topic-history gerçek cross-Actions proof 44280024395→44280111635 ile tamamlandı. Bu eski video kalite başarısızlığı giderildi veya yeni Faz 4 medya-history persistence kanıtlandı demek değildir.

## Faz 4J — Cookie-first medya entegrasyonu (19 Kasım 2026)

### Tamamlanan
- `_synthesize_storyboard()` greedy keyword ataması: zor sahnelere öncelik veriyor, rebalancing swap yapıyor
- ALIASES 1092 TR→EN eşleşme (vücut/hayvan/bilim/tarih/doğa/sayı/renk/fiil)
- scene_plan overlap koşulu primary+alternatifleri kapsıyor
- Content QC: sahne sayısı dinamik, 8 içerik kontrolü + metadata-only disclaimarı
- Tüm 383 Python testi geçiyor, 17 Node testi geçiyor, 126/126 fallback senaryosu scene_plan'dan geçiyor

### Kalan (canlı CI gerektirir)
- GitHub Actions `phase4g_e2e_no_upload.yml` tetiklenmeli (PEXELS_COOK/PIXABAY_COOK ile)
- Cookie diagnostics gerçeği yansıtmalı
- Tam no-upload uçtan uca kanıt
- Kod commit: `fbca2e3` + faz4j devam commitleri
- Detaylı rapor: `docs/evidence/PHASE4J_ACCEPTANCE.md`

### Bilinen sınırlamalar
- GitHub remote/push bu workspace'te yapılandırılmadı; commitler yerel
- Canlı cookie search+download CI'da doğrulanmalı

## Faz6 — Cookie-free public providers (20 Kasım 2026)

### Politika (kalıcı)
- API key YOK (`PEXELS_API_KEY`/`PIXABAY_API_KEY`/`NASA_API_KEY` vb. tamamen yasak).
- Mimari: ya cookie ile Playwright (Pexels/Pixabay) ya da cookie'siz kamu HTTP (NASA, Internet Archive, Wikimedia).
- CAPTCHA/Cloudflare bypass YOK.

### Tamamlanan
- `NasaProvider` (keyless public): `images-api.nasa.gov/search` → manifest HEAD → en küçük MP4 (<64 MB).
- `InternetArchiveProvider` (keyless public): mediatype:movies + publicdomain + title/description phrase + küratörlü koleksiyonlar (prelinger/nasa/usgovfilms) → MP4 derive HEAD + 512kb fallback.
- `StockTerms`: NASA=verified public domain; IA=per-item verification pending.
- `default_providers()` sırası: pexels, pixabay, nasa, archiveorg, wikimedia.
- Yeni probe: `.github/workflows/public_providers_probe.yml` (HİÇ SECRET YOK).
- Probe scripti: `scripts/public_providers_probe.py` (search→download→SHA256→ffprobe→full-decode).
- Yeni birim testleri: `tests/test_phase6_public_providers.py` (7 testin 7'si geçiyor, mock HTTP).
- Dokumantasyon: `docs/evidence/FAZ6_PUBLIC_PROVIDERS_REPORT_2026-11-20.md`.

### Yerel kanıt (sandbox)
- NASA solar flare → 3.3 MB mobile.mp4 (82 saniye h264+AAC) → ffprobe OK → full decode OK.
- IA solar flare → 467 KB mp4 (5.2 saniye h264 480×480) → ffprobe OK → full decode OK.

### CI için beklenen
- `public_providers_probe.yml` workflow_dispatch ile tetiklenip NASA+IA için gerçek indirme+decode kanıtı üretecek.
- Pixabay cookie preflight 12 cookie görüyor ama `browser_exception` ile başarısız oluyor (run #11, dc8b1e6 sonrası); kullanıcı yeni PIXABAY_COOK verene kadar IA/NASA/Wikimedia fallback olarak görev yapacak.

### Kalan / Sıradaki
- Faz6C: Openverse (CC image fallback, keyless).
- Faz6D: Mixkit/Videvo cookie mi, lisans uygun mu arastirmasi.
- Pixabay cookie yenileme (kullanıcıya daha sonra sorulacak).
- IA per-item license verification indirme sonrası (şu anda search'te `verified=False`).
- Içerik seçiciye yeni sağlayıcıları dahil eden senaryo testleri.

## Faz6C — Mixkit Free Stock Video (20 Kasım 2026)

- `MixkitProvider` eklendi (keyless public HTTP).
- URL: `mixkit.co/free-stock-video/{keyword}/` → HTML parse → `assets.mixkit.co` CDN MP4.
- Free-tier çözünürlük: 1080 > 720 > 360 (4K atlanır).
- Mixkit Free License: ticari kullanım + YouTube, attribution zorunlu değil.
- 4K/premium ve Restricted License klipler filtrelenir.
- 5 yeni birim testi (toplam 12 testin 12'si geçiyor).
- CI probe pending.
