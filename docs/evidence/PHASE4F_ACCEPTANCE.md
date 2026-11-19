# FAZ 4F — Kabul Raporu (KISMİ / BİRİNCİ AŞAMA: KOD + STATİK KANIT)

**Tarih:** 2026-11-19 (Europe/Istanbul)
**Repo:** `ahmetbysoy/youtube_shorts_automation`
**İncelenen referans koşular:**

| Run ID | Workflow | Commit SHA | Sonuç |
|---|---|---|---|
| `44446675653` | Faz 4E storyboard-cookie-probe | `8b777ab` | ✅ success (kanıt olarak korunur) |
| `44449610436` | Daily Shorts (15-Min Blitz) | `4f55feaa` (empty commit from 8b777ab) | ❌ failure (setup step 4, exit 254) |
| `44449762264` | Draft Publisher | `4f55feaa` | ❌ failure (setup step 3, exit 254) |
| `44449524679` | Hourly Pruner | `8b777ab` | ❌ failure (setup step 4, exit 254) |

> **PARTIAL NOT:** Kod tarafı tamamlandı ama GitHub push yetkisi/kredisi olmayan sandbox ortamında gerçek Actions koşusu tetiklenemedi. Bu raporda yalnızca **kod düzeyinde kanıtlar ve kök neden analizi** var. Gerçek cache hit/miss kanıtı push sonrası koşulmalarda doldurulacaktır.

---

## 1. Setup Hatalarının Kök Nedeni

Üç üretim workflow da aynı adımda (Araçları Kur) aynı exit code `254` ile 8–43 saniye içinde patlıyordu. Annotation hatası tek satır:

> `Process completed with exit code 254.`

### Kökneden kanıt

Commit `8b777ab` (ve empty-child `4f55feaa`) üzerindeki `.github/actions/setup-tools/action.yml`:
- Repoda **`package.json` yoktu** (GitHub API `contents/package.json` → 404).
- Aksiyonda `nm-cache` (node_modules cache) miss ise:
  ```yaml
  - name: "npm bağımlılıkları (önbellek yoksa)"
    run: |
      if [ -f package-lock.json ]; then npm ci ...; else npm install ...; fi
  ```
- `npm install`, package.json olmayan dizinde exit code **254** ile fail olur.

Yerel doğrulama:
```bash
$ mkdir /tmp/npm-test && cd /tmp/npm-test
$ npm install --no-audit --no-fund --loglevel=error
npm error enoent Could not read package.json: ENOENT
$ echo $?
254          # ← tam olarak koşulardaki exit code
```

Aynı hata zinciri:
1. `package.json` repoda yok.
2. `nm-cache` miss (daha önce node_modules cache'i oluşturulmamıştı).
3. `npm install` 254 ile fail.
4. Sonraki Playwright/Cookie/Pipeline adımları skip.
5. Job failure.

### Neden Daily Shorts 43s, Pruner/Draft 8s?
- Daily Shorts Python+pip adımına da giriyor (pip birkaç paket indirdikten sonra npm install aşamasına gelip patlıyor).
- Pruner/Draft Python=false, doğrudan npm install'a düşüyor, daha hızlı patlıyor.

### Düzeltme

- Repoya `package.json` eklendi (`playwright: "1.64.1"` devDep; Python Playwright 1.64.1 ile aynı sürüm → v1248/v1255 browser sürüm çakışması biter).
- `package-lock.json` üretildi ve commit'e hazır (cache key'in kararlı olması için zorunlu).
- `setup-tools/action.yml` içine koruma: `node_playwright=true` iken package.json yoksa açık hata verir (exit 1, anlaşılır mesaj).
- Eski `npm install` (package.json yoksa patla) davranışı yerine:
  - `package-lock.json` varsa `npm ci` (deterministik kurulum, CI için doğru).
  - Yoksa `npm install`.
- `node_modules` cache hit gelse bile `require('playwright')` smoke modül doğrulaması yapılır; bozuk/kısmi cache ise `npm ci` yeniden çalışır.
- Playwright binary cache hit gelse bile chrome/chrome-headless-shell binary varlığı kontrol edilir; eksikse yeniden indirilir.
- APT `.deb` cache stratejisi düzeltildi: `Dir::Cache::archives` override'ı yerine kullanıcı dizininde (`~/.apt-debs`) güvenli arşiv + apt-get sonrası cp; dpkg -i bağımlılıkları daima apt-get ile doğrulanır.

---

## 2. Değiştirilen / Eklenen Dosyalar

| Dosya | Değişiklik |
|---|---|
| `package.json` | YENİ — `playwright@1.64.1` devDep, `private: true` (CI-only) |
| `package-lock.json` | YENİ — npm ci için kararlı lock |
| `.github/actions/setup-tools/action.yml` | YENİDEN YAZILDI — 5 katmanlı cache, ayrı npm/py pw key, pip çoklu requirements + pip_extra, node sürüm parametresi, apt kullanıcı dizini cache, binary smoke, cache bozulma fallback, `setup_duration_ms` ve 5 adet cache-hit output |
| `.github/workflows/daily_shorts.yml` | setup-tools yeni API'ye geçirildi (python 3.11 + node 20 + playwright_chromium + python_playwright + node_check; node_check: youtube_studio_uploader.js, video_fetcher.js, analytics_scraper.js) |
| `.github/workflows/draft_publisher.yml` | setup-tools yeni API + node_check: youtube_studio_uploader.js |
| `.github/workflows/hourly_pruner.yml` | setup-tools yeni API + node_check: youtube_studio_uploader.js |
| `.github/workflows/daily_analytics.yml` | setup-tools yeni API + node_check: analytics_scraper.js |
| `.github/workflows/backfill_short_thumbnails.yml` | setup-tools yeni API |
| `.github/workflows/stock_cookie_probe.yml` | setup-tools yeni API (node + pw + apt ffmpeg) |
| `.github/workflows/free_gemini_probe.yml` | setup-tools (python-only, pip_extra Pillow) |
| `.github/workflows/free_gemini_frame_rejection_probe.yml` | setup-tools (python + apt ffmpeg + pip_extra Pillow) |
| `.github/workflows/free_gemini_text_probe.yml` | setup-tools (python) |
| `.github/workflows/topic_history_persistence_probe.yml` | setup-tools (python + pip_extra requests) |
| `.github/workflows/phase4b_history_probe.yml` | setup-tools (python + pip_extra requests+dotenv) |
| `.github/workflows/phase4_media_probe.yml` | APT azure-mirror fix setup-tools öncesi + setup-tools yeni API |
| `.github/workflows/phase4e_storyboard_pipeline.yml` | setup-tools yeni API; Faz 4E'nin başarılı davranışı korunur (apt ffmpeg+libass+fonts, python+requirements.txt/test.txt, node+pw+pw-chromium, node_check video_fetcher+analytics_scraper) |
| `.github/workflows/ubuntu_26_test.yml` | setup-tools yeni API + step summary'de setup süresi ve 5 cache hit durumunun raporu |
| `.github/workflows/cache_verification.yml` | YENİ — 4 senaryo: prime(miss)/hit/invalidation/corrupted-fallback |
| `tests/test_phase3_entrypoints.py` | `test_probe_installs_its_pinned_requests_dependency` yeni setup-tools pip_extra pattern'ini de kabul eder |
| `docs/evidence/PHASE4F_ACCEPTANCE.md` | Bu rapor |
| `docs/evidence/PHASE4F_ACTIONS_EVIDENCE.json` | JSON kanıt şablonu (koşular sonrası güncellenecek) |

---

## 3. Cache Mimarisi Özeti

| Katman | Cache Path | Key | Smoke |
|---|---|---|---|
| APT .deb arşivi | `~/.apt-debs/*.deb` | `apt-debs-{REL}-{ARCH}-{ImageVersion}-{pkgs-hash}` | `dpkg -s` her paket; eksikse apt-get |
| pip (setup-python v7) | `~/.cache/pip` | setup-python cache + `cache-dependency-path` | pip install her koşu çalışır; cache sadece wheel/source |
| node_modules | `node_modules/` | `node-modules-{OS}-node{ver}-{hash(pkg-lock,pkg.json)}` | `require('playwright')`; bozuksa npm ci |
| PW Chromium (npm) | `~/.cache/ms-playwright/` | `pw-chromium-npm-{OS}-node{ver}-{pkg-hash}` | `chrome-headless-shell` binary varlığı + `chromium.launch()` smoke |
| PW Chromium (py) | `~/.cache/ms-playwright/` | `pw-chromium-py-{OS}-py{ver}-{requirements-hash}` | Binary varlığı; eksikse `python -m playwright install` |

### Güvenlik
Cache path'leri (`~/.apt-debs`, `node_modules`, `~/.cache/ms-playwright`, `~/.cache/pip`) hiçbir zaman şu yolları içermez:
- `cookies.json`, `storage_state.json`, `.env`
- Cookie/API secret env dosyaları
- `topic_history.json`, `.used_topics.json`, `media_history.json` (state)
- `output/`, `generated/`, `final_videos/` (üretim videoları)
- Log dosyaları

Cache key'leri hiçbir secret içermez.

### Fallback (cache miss/bozuk)
- APT: dpkg -i başarısız → apt-get update+install.
- pip: setup-python cache sadece indirme cache'i; pip install her koşu çalışır, bozuk cache sonucu etkilemez.
- node_modules: cache hit ama playwright require fail → npm ci yeniden.
- Playwright binary: cache hit ama binary dosyası yok → yeniden indir; chromium.launch() smoke fail → install-deps çalıştır; o da fail → exit 1.

### Node kullanılmayan workflow'lar
- `free_gemini_probe`, `free_gemini_text_probe`, `free_gemini_frame_rejection_probe`, `topic_history_persistence_probe`, `phase4b_history_probe` → `node: false`; Node kurulumu/cache'i hiç çalışmaz.

---

## 4. Cookie Tabanlı Medya Sistemi

Faz 4E koşusu `44446675653`'de (commit `8b777ab`) başarılı olan medya pipeline'ı korunmuştur. İncelenen kanıt:
- Cookie preflight adımı başarılı.
- Cookie-only storyboard medya seçimi başarılı (2:37 sürede, gerçek indirme + ffprobe + decode + manifest).
- Consumer FFmpeg montajı başarılı.
- Artifact güvenliği başarılı.

Bu fazda (4F) şunlar doğrulandı:
- Production `daily_shorts.yml` pipeline'ı **yalnızca** `PEXELS_COOK` ve `PIXABAY_COOK` secret'larını kullanır; `PEXELS_API_KEY`/`PIXABAY_API_KEY` environment olarak production orchestrator'a geçirilmez.
- API anahtarları yalnızca `phase4_media_probe.yml`'nin `auto` modunda kullanılır (production değil, cookie-only probe `cookie_only` modunda boş geçirilir).
- `scripts/media_probe_security.py`'nin `STOCK_KEYS` sözlüğü yalnızca probe preflight raporlaması için kullanılır, production pipeline'da API'ye çağrı yapmaz.
- `video_fetcher.js`, `main.py`, `scripts/gemini_web_story.py` dosyalarında `api.pexels.com`, `pixabay.com/api`, `Authorization: Bearer` pattern'leri bulunmaz (cookie-based Playwright scraping korunur).
- Wikimedia Commons sağlayıcısı `scripts/phase4c_commons_diagnostics.py`'de mevcut haliyle korunur; host allowlist ve lisans doğrulaması değişmedi.

### API provider kullanmama garantisi (test ile)
- `tests/test_phase4d_cookie_isolation.py`'de 16 test geçti (cookie parse/domain/izolasyon).
- Production ana yolda `PEXELS_API_KEY`/`PIXABAY_API_KEY` sembolik olarak hiç kullanılmıyor.

---

## 5. Test Sonuçları (Yerel)

```
tests/ altında (ffmpeg gerektiren consumer/render testleri hariç):
  297 passed, 4 skipped, 8 deselected
```
- `tests/test_phase4d_cookie_isolation.py` → 16 passed (cookie domain + parse + normalization)
- `tests/test_phase4_media.py`, `test_phase4b_media.py`, `test_phase3_fact_checks.py`, `test_topic_history.py`, `test_script_json_schema.py`, `test_repeat_protection.py`, `test_gemini_web_*`, `test_cover_frame.py` → geçti.
- `tests/test_phase4b_consumers.py` ve `test_phase4c_media.py`'nin gerçek ffmpeg subprocess çağrısı yapan 3 testi yerelde `ffmpeg` yokluğu nedeniyle fail; CI runner'da ffmpeg kurulu olduğu için normalde geçer.
- 16 parametreli cookie izolasyon testinin hepsi geçer.

---

## 6. Kabul Kriterleri Durumu

| # | Kriter | Durum | Kanıt |
|---|---|---|---|
| 1–3 | Daily Shorts / Draft Publisher / Hourly Pruner setup | 🟡 KOD DÜZELTİLDİ, KOŞU BEKLENİYOR | Exit 254 kök nedeni bulundu ve düzeltildi (package.json + lock + npm ci korumaları); push sonrası tekrar koşulmalı |
| 4 | Pexels cookie canlı erişim | 🟢 FAZ 4E'DE KANITLANDI | run `44446675653` step 9 "Cookie-only storyboard medya secimi" success |
| 5 | Pixabay cookie canlı erişim | 🟢 FAZ 4E'DE KANITLANDI | Aynı koşu |
| 6 | API kullanılmadığının kanıtı | 🟢 KOD DOĞRULAMASI | grep: production yolda PEXELS_API_KEY/PIXABAY_API_KEY geçmiyor; ortamdan da geçirilmiyor |
| 7 | Wikimedia gerçek medya | ⏳ PROBE KOŞUSU BEKLENİYOR | `phase4c_commons_diagnostics.py` korundu; ubuntu_26_test workflow cache sonrası koşmalı |
| 8 | Lisans doğrulama | 🟢 KORUNDU | Mevcut canonical snapshot + canlı lisans kontrol kodunda değişiklik yok |
| 9 | ≥2 sahne gerçek medya | 🟢 FAZ 4E'DE KANITLANDI | run `44446675653` iki farklı keyword (cat+dog) ile seçim yapıldı |
| 10 | FFprobe kontrolü | 🟢 FAZ 4E'DE KANITLANDI | Aynı koşu |
| 11 | FFmpeg decode | 🟢 FAZ 4E'DE KANITLANDI | Aynı koşu |
| 12 | Consumer pipeline | 🟢 FAZ 4E'DE KANITLANDI | "Consumer FFmpeg hattini test et" success |
| 13 | Video QC | 🟢 FAZ 4E'DE KANITLANDI | Aynı koşu |
| 14 | Media history korundu | 🟢 KOD İNCELEMESİ | `topic_history.py`, `.used_topics.json` cache'e yazılmıyor; workflow hiçbir history dosyasını silmiyor/değiştirmiyor |
| 15 | Testler | 🟢 297 passed (yerel) | bkz. §5 |
| 16 | Secret leak kontrolü | 🟢 | Cache path'leri secret/cookie içermez; cookie değerleri hiçbir adımda loglanmıyor (mevcut davranış korundu) |
| 17 | YouTube upload/publication/silme yok | 🟢 | Hiçbir workflow tetiklenmedi; güncellemeler yalnızca kodsaldır |
| 18 | Production davranışı izinsiz değişmedi | 🟢 | Yalnızca setup katmanı değiştirildi; orchestrator/uploader/pruner/publisher betiklerine dokunulmadı |
| 19–32 | Cache altyapısı (13 kriter) | 🟡 KOD HAZIR, GERÇEK KOŞU BEKLENİYOR | Bkz. §3; cache_verification workflow ile senaryolar koşulduktan sonra kanıtla doldurulacak |

---

## 7. Push Sonrası Koşulacak Doğrulama Adımları

1. Değişiklikleri `main` branch'ine (veya bir PR'a) pushla.
2. `Actions → Cache Doğrulama (setup-tools) → Run workflow`:
   - `hit_miss` senaryosu → prime'da miss, hit job'da 5 katman için fail-closed hit kontrolü.
   - `invalidation` senaryosu → Node 22'de node_modules/pw-npm miss, pip/py-pw hit.
   - `corrupted_fallback` senaryosu → binary'leri sil, yeniden kurulum ve chromium smoke.
3. Zamanlanmış/schedule production workflow'ların (Daily Shorts, Draft Publisher, Hourly Pruner) bir sonraki otomatik koşusunu bekle veya workflow_dispatch ile kuru koşu (`dry_run`/benzeri bir kapı) tetikle; setup step 4'in success olduğunu gör.
4. Faz 4E benzeri medya probe koşusu (`phase4e_storyboard_pipeline.yml`) workflow_dispatch ile tetikle; cookie-only medya seçimi + consumer montajın cache'li kurulumda da çalıştığını kanıtla.
5. Bu koşuların URL'lerini ve süre/sahne/cache-hit kanıtlarını `PHASE4F_ACTIONS_EVIDENCE.json` içine doldur.

## 8. Yasaklara Uyum

- `main.py` ile production pipeline çalıştırılmadı.
- YouTube upload/publication/silme yok.
- Hiçbir secret/cookie değeri okunmadı, yazdırılmadı.
- Cookie değerleri artifact/JSON raporlarına yazılmadı.
- Gemini API veya ücretli API kullanılmadı.
- Pexels/Pixabay API sistemine geçilmedi, API kullanımı cookie kullanılmış gibi raporlanmadı.
- 403/CAPTCHA/bot koruması bypass edilmedi.
- Mevcut YouTube kanal sıralaması/concurrency/quota/idempotency/topic reservation/media history/politikalarına dokunulmadı.
- `GEMINI_COOK` ve `GEMINI_API_KEY` secret'ları korunur.
- Mevcut thumbnail/uploader/kanal yönetimi/scheduling sistemlerine dokunulmadı.
- Cache'e hiçbir secret/cookie/state/topic reservation/media history/video yazılmaz.
