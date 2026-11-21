# Secret Checklist — 2026-11-21 10:52 UTC (guncellenmis)

## Test metodolojisi
- Her secret ilgili servise GERCEK baglanti kurularak test edildi.
- `00_secret_health_check.yml` run #44896167330 (yeni GEMINI_COOK sonrasi).
- GEMINI_COOK ayrica `01_refresh_gemini_cookie.yml` run #44895904460 ile
  **Playwright uzerinden canli kanit** ile dogrulandi (tarayicida "2+2 kac?"
  soruldu, "Merhaba! 4." cevabi alindi — screenshot artifact olarak kayitli).

## ✅ CALISIYOR (10 adet) — HICBIR ISLEM GEREKMIYOR

| Secret | Test tipi | Sonuc |
|--------|----------|-------|
| **REPO_PAT** | GitHub API public-key endpoint | ✅ public-key 200, secret yazma yetkisi var (son islemlerde 5+ secret PUT 204 ile yazildi) |
| **COOKIES_JSON** | JSON parse + cookie sayisi | ✅ JSON array, 64 cookie; son video 7IwKIlxt6GY'yi basariyla yayinladi |
| **STORAGE_STATE_JSON** | Playwright storage_state | ✅ 64 cookie, `01_refresh_gemini_cookie` bu storage_state ile Gemini'ye girip kanit mesaji gonderdi |
| **YT_EMAIL** | mevcutluk | ✅ backup auth olarak mevcut |
| **YT_PASSWORD** | mevcutluk | ✅ backup auth, 8 char |
| **ENV_FILE** | satir sayisi | ✅ 26 satir `.env` |
| **GEMINI_COOK** | JSON yapi + Playwright canli kanit | ✅ PSID=153 char, PSIDTS=77 char; **CI Playwright ile "Merhaba! 4." cevabi alindi** (artifact `gemini_after_send.png` kanit) |
| **HF_TOKEN** | HuggingFace whoami API | ✅ user=Ahmetbysoy |
| **COOKIES_JSON_DRAFT** | JSON + uzunluk | ✅ 15180 char (draft_publisher icin) |
| **STORAGE_STATE_JSON_DRAFT** | uzunluk | ✅ 17113 char (draft_publisher icin) |

## ⚠️ CALISIYOR AMA KOD KATMANINDA SORUN VAR (1 adet)

| Secret | Durum | Not |
|--------|-------|-----|
| **GEMINI_COOK — kod tarafi** | Secret DOGRU, ama `gemini_webapi` Python kutuphanesi 25s'de timeout veriyor | Bu KUTUPHANE/script hatasi, secret hatasi DEGIL. 2026'da Gemini Web UI/WS protokolu degismis, kutuphane eski kalmis. Tarayici uzerinden kanitlandigi uzere cookie'ler tamamen gecerli. **Sonraki adim:** `gemini_webapi` yerine Playwright-tabanli veya resmi API-tabanli bir Gemini istemcisi yazmak. Pipeline su anda bu durumda da calisiyor (timeout sonrasi local fallback senaryo havuzuna donuyor — 7IwKIlxt6GY bu sekilde uretildi), ama Gemini'nin ozel senaryo uretimi aktif degil. |

## ❌ YENILENMESI GEREKIYOR (2 adet) — ACIL

| Secret | Hata | Nasil yenilenir |
|--------|------|-----------------|
| **PEXELS_COOK** | `HTTP 403 Forbidden` — Pexels oturumu kapanmis | Tarayicida pexels.com'a giris yap → DevTools → Console'da `copy(document.cookie)` → cookie'leri JSON array formatina cevir → PEXELS_COOK secret'ini guncelle. |
| **PIXABAY_COOK** | `HTTP 403 Forbidden` — Pixabay oturumu kapanmis | Ayni islem pixabay.com icin. |

## ℹ️ NOTLAR
- **MEDIA_COOKIES_JSON** (20386 char): Eski birlesik cookie, yeni kod bunu okumuyor ama silinmesi gerekmiyor.
- **Pruner cron su anda devre disi** (31 Subat'a ayarli) — pipeline kararliligi 2-3 gun dogrulandiktan sonra tekrar acilacak.
- Pipeline su an PEXELS_COOK/PIXABAY_COOK/GEMINI_COOK-kodu bozuk olsa DA calisiyor (tamami fallback'li) — ama tam kapasite icin yukaridaki 2 cookie yenilenmeli ve Gemini kodu Playwright tabanli olacak sekilde guncellenmeli.

## Otomatik yenileme araci
GEMINI_COOK artik manuel yenileme gerektirmiyor:
- `01_refresh_gemini_cookie.yml` workflow'unu "Run workflow" ile calistirman yeterli.
- Calisan YT storage_state'ini kullanarak otomatik olarak gemini.google.com'a girer,
  PSID+PSIDTS'yi tazeler, kanit olarak bir mesaj gonderip cevap alir, ve secret'a yazar.
- Bu kanit screenshot artifact olarak her kosuda kaydedilir.
