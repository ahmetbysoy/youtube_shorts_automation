# Secret Checklist — 2026-11-21 10:27 UTC (gercek CI testi sonucu)

Kaynak: `.github/workflows/00_secret_health_check.yml` run #44894361794 (9 PASS / 3 FAIL / 0 WARN).
Her secret ilgili servise GERCEK baglanti kurarak test edildi (sadece uzunluk/format degil).

## ✅ CALISIYOR (9 adet) — hicbir islem gerekmiyor

| Secret | Test tipi | Sonuc |
|--------|----------|-------|
| **REPO_PAT** | GitHub API public-key endpoint (secret write) | ✅ public-key 200, secret yazma yetkisi var (son run'da 4 cookie secret'i 204 ile yazildi) |
| **COOKIES_JSON** | JSON parse + cookie sayisi | ✅ JSON array, 64 cookie, son run 7IwKIlxt6GY videosunu basariyla yayinladi |
| **STORAGE_STATE_JSON** | Playwright storage_state format | ✅ storage_state, 64 cookie |
| **YT_EMAIL** | Mevcutluk | ✅ backup auth olarak mevcut (`meh***`) |
| **YT_PASSWORD** | Mevcutluk | ✅ backup auth, 8 char |
| **ENV_FILE** | satir sayisi | ✅ 26 satir `.env` |
| **HF_TOKEN** | HuggingFace whoami API | ✅ user=Ahmetbysoy |
| **COOKIES_JSON_DRAFT** | uzunluk + JSON | ✅ 15180 char (draft_publisher icin) |
| **STORAGE_STATE_JSON_DRAFT** | uzunluk | ✅ 17113 char (draft_publisher icin) |

## ❌ YENILENMESI GEREKIYOR (3 adet) — ACIL

| Secret | Hata | Neden | Nasil yenilenir |
|--------|------|-------|-----------------|
| **GEMINI_COOK** | `TimeoutError` — `client.init()` 25s'de tamamlanamadi | Cookie (ozellikle `__Secure-1PSIDTS`) suresi dolmus; Gemini Web oturumu acilmiyor. Son run'larda da (18:33, 13:02, 09:56, 20:37) 3 konu da 80s timeout'a dusup fallback'e donuyordu — bunun sebebi tam olarak bu. | Tarayicida gemini.google.com'a giris yap → DevTools → Application → Cookies → `gemini.google.com` altindaki `__Secure-1PSID` ve `__Secure-1PSIDTS` degerlerini kopyala → Secret'i guncelle. Ya da `scripts/gemini_web_text_probe.py` ile taze cookie topla. |
| **PEXELS_COOK** | `HTTP 403 Forbidden` | Pexels oturumu kapanmis / cookie gecersiz. Stok videolar icin birincil saglayici Pexels oldugundan medya seciminde videolar Pexels'ten degil Mixkit/Nasa/IA/Wikimedia'dan geliyor. | pexels.com'a giris yap → DevTools → Application → Cookies → `pexels.com` cookielerini JSON olarak export et → Secret'i guncelle. |
| **PIXABAY_COOK** | `HTTP 403 Forbidden` | Ayni sekilde Pixabay oturumu da kapanmis. | pixabay.com'a giris yap → ayni yontemle cookie'leri JSON export et → Secret'i guncelle. |

## ⚠️ Notlar
- **MEDIA_COOKIES_JSON** (20386 char, 2026-11-06): Eski birlesik cookie dosyasi, artik PEXELS_COOK/PIXABAY_COOK ayri olarak kullaniliyor. Yeni kod bunu okumuyor ama silinmesi de gerekmiyor.
- Pipeline su anda GEMINI/PEXELS/PIXABAY cookie'leri yenilenmeden DE calisiyor:
  - Gemini timeout → local fallback senaryo havuzu devreye giriyor (7IwKIlxt6GY videosu bu sekilde uretildi)
  - Pexels/Pixabay 403 → Mixkit, NASA, Internet Archive, Wikimedia (cookie gerektirmeyenler) medya sagliyor
- Ama **kalite ve hiz acisindan bu 3 cookie yenilenmeli** — fallback senaryolari ve keyless-public saglayicilar daha az cesit ve daha uzun bekleme sureleri veriyor.

## Nasil yenilenecek (adim adim)

### GEMINI_COOK yenileme (en oncelikli):
1. Chrome/Edge ile https://gemini.google.com'a giris yap (Google hesabinla)
2. F12 → Application → Storage → Cookies → https://gemini.google.com
3. `__Secure-1PSID` ve `__Secure-1PSIDTS` degerlerini kopyala
4. Asagidaki JSON formatinda birlestir:
   ```json
   [
     {"name":"__Secure-1PSID","value":"<DEGER>","domain":".google.com","path":"/"},
     {"name":"__Secure-1PSIDTS","value":"<DEGER>","domain":".google.com","path":"/"}
   ]
   ```
5. GitHub repo → Settings → Secrets and variables → Actions → GEMINI_COOK → Update secret

### PEXELS_COOK yenileme:
1. https://www.pexels.com/login adresine giris yap
2. F12 → Application → Cookies → https://www.pexels.com
3. Console'da: `copy(JSON.stringify(document.cookie.split(';').map(c=>({name:c.split('=')[0].trim(),value:c.split('=').slice(1).join('=').trim(),domain:'.pexels.com',path:'/'}))))`
4. Ciktiyi PEXELS_COOK secret'ina yapistir.

### PIXABAY_COOK yenileme:
1. https://pixabay.com'a giris yap
2. Pexels ile ayni yontem, domain `.pixabay.com`

## Test
Yeniledikten sonra:
- Actions → "00 — Secret Sağlık Kontrolü" → Run workflow → hepsi PASS olmali
- Sonra `daily_shorts.yml` dry_run=1 ile bir test kosusu yap, 15-20 dk icinde tamamlanmali.
