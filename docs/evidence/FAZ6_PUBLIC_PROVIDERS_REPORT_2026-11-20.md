# Faz6: Cookie-free public media providers (NASA, Internet Archive)

**Tarih:** 2026-11-20
**Durum:** IMPLEMENTED + LOCALLY_VERIFIED (sandbox full decode pass), CI probe pending dispatch.
**Politika:** Cookie-only/keyless-public mimari — API key YOK.

## 1. Kapsam

Kullanicinin 2026-11-20 karari uyarinca, tum yeni medya saglayicilari cookie'siz
kamu endpoint'leri veya cookie ile calisan siteler olarak eklenecek; API key
kullanimi KALICI OLARAK YASAK. Bu fazi ilk olarak cookie gerektirmeyen iki
kamu kaynagini ekler:

- **NASA Image and Video Library** (`images-api.nasa.gov`, `images-assets.nasa.gov`)
  - BDH federal hukumet eseri → genelde public domain.
  - JSON API uzerinden arama, asset manifest (collection.json) uzerinden MP4
    varyantlarini listeleme, HEAD ile Content-Type ve Content-Length kontrolu.
  - En kucuk MP4 varyantini (<64 MB) secer (mobile > preview > small > medium > orig).
- **Internet Archive** (`archive.org/advancedsearch.php`, `archive.org/download/...`)
  - Public domain + CC0 lisansli medya; mediatype:movies filtreli.
  - Alaka skoru cok dusuk oldugu icin tam-metin yerine title/description phrase
    search ve küratörlü koleksiyonlar (Prelinger, NASA, US Gov Films) ile sinirli.
  - MP4 derive URL'ine HEAD atarak varligi ve 64 MB sinirini dogrular; ana
    .mp4 yoksa `{ident}_512kb.mp4` alternatifini dener.

## 2. Referans mimari (dogrulandi)

Pexels ile CI'da kanitlanan zincir referans alindi. Cookie'siz saglayicilar
Playwright adimini atlar ama ayni guvenlik kapilarindan gecer:

```
search (HTTP JSON)
  → candidate list
  → [NASA] manifest/HEAD → en kucuk MP4 sec
  → [IA] HEAD MP4 derive → alt MP4 fallback
  → download_url host allowlist (DOWNLOAD_HOSTS)
  → HTTP GET, stream, byte-siniri (MAX_BYTES=64 MB)
  → SHA256
  → ffprobe (codec, width, height, duration)
  → ffmpeg -f null - (tam decode)
  → MediaLicense (NASA=verified PD, IA=per-item pending)
```

## 3. Kod değişiklikleri

### src/media_processing/media_providers.py

- `SOURCE_HOSTS` ve `DOWNLOAD_HOSTS` sozluklerine `nasa` ve `archiveorg`
  alanlari eklendi.
- `NasaProvider` sinifi: `images-api.nasa.gov/search` ile video arar, her aday
  icin `collection.json` manifest'ini ceker, MP4 varyantlari arasinda HEAD ile
  64 MB altinda en kucuk olani secer. URL'leri `urllib.parse.quote` ile encode
  eder (nasa_id bosluk/ozel karakter icerebiliyor).
- `InternetArchiveProvider` sinifi: `archive.org/advancedsearch.php` uzerinden
  mediatype:movies + title/description phrase search yapar, collection filtresi
  ile Prelinger/NASA/usgovfilms ile sinirlar, licenseurl:publicdomain ile
  CC/PD filtreler. Her aday icin MP4 derive URL'ine HEAD atarak dosya
  varligi ve Content-Type dogrular.
- `StockTerms.check()` icine NASA (verified PD) ve archiveorg (per-item
  pending) icin ozel davranis eklendi; HTTP/cookie/canonical fallback
  zinciri bu saglayicilar icin atlanir.
- `default_providers()` listesine `NasaProvider` ve `InternetArchiveProvider`
  eklendi (sira: pexels, pixabay, nasa, archiveorg, wikimedia).

### scripts/public_providers_probe.py

- Yeni keyless probe scripti: search → stream indirme → SHA256 → ffprobe →
  full decode → JSON raporu. Coklu aday deneme (ilk gecerli olani sec).

### .github/workflows/public_providers_probe.yml

- `workflow_dispatch` ile tetiklenen, HICBIR SECRET kullanmayan probe workflow.
- Tooling: Python 3.11 + ffmpeg + requests/bs4.
- Artifact olarak JSON rapor + log yukler.

### tests/test_phase6_public_providers.py

- 7 birim testi (mock HTTP session ile dis ag cikmadan):
  - host allowlist NASA/IA
  - default_providers() wiring
  - StockTerms NASA=PD verified; IA=pending
  - NASA search → manifest → en kucuk MP4 sec
  - IA search → HEAD filter (404 ve buyuk dosya elenir)

## 4. Kanit (yerel sandbox)

Sandbox'ta gercek HTTP cagrilari ile end-to-end test edildi:

**NASA — keyword "solar flare":**
- 15 aday bulundu, ilk aday `GSFC_20170403_Trio_m12563_SolarFlares~mobile.mp4`.
- Content-Type: video/mp4, 3,428,132 bytes (3.3 MB).
- ffmpeg: h264+AAC, Duration 00:01:22, bitrate 332 kb/s.
- `ffmpeg -f null -` full decode: exit 0 (OK).

**Internet Archive — keyword "solar flare":**
- 4 aday (publicdomain/Prelinger/NASA/usgovfilms filtreli), ilk aday
  `flare_soh_2003301.mp4`.
- Content-Type: video/mp4, 467,228 bytes (467 KB).
- ffmpeg: h264, 480×480, 5.20s, 715 kb/s.
- `ffmpeg -f null -` full decode: exit 0 (OK).

## 5. Bilinen sinirlar

- **IA lisans dogrulamasi:** Search asamasinda `licenseurl:publicdomain` filtresi
  ve küratörlü koleksiyonlar kullaniliyor, ama per-item lisans indirme sonrasi
  metadata (metadata/ identifier sayfasi) uzerinden tekrar dogrulanmali. Bu
  yuzden `StockTerms.check("archiveorg")` `verified=False` donuyor; lisans
  kontrolden gecmeden IA video'lar "secilmis" addedilmez.
- **IA alaka skoru:** title/description phrase search ile eskiye gore buyuk
  olcude duzeldi ama halen konu disi eski film/trailer donebilir. Scene media
  secicinin relevance skoru bu durumda dogru adayi sececektir.
- **NASA video boyutu:** Bircok NASA videosu 100+ MB (briefing, long-form
  dokumanter). Manifest HEAD filtrelemesi ile 64 MB alti adaylar kaliyor; bu
  da b-roll, kisa klipler ve animasyonlari seciyor.
- **IA video cozunurlugu:** Bircok eser arsiv niteliginde, dusuk cozunurluklu
  (480×480 vb). Mevcut min-height/min-resolution filtresi bunlari dikey shorts
  icin yetersiz bulabilir; bu durumda selector NASA/Pexels/Pixabay'a duser.

## 6. Siradaki adaylar (Faz6C+)

1. **Mixkit** (mixkit.co) — cookie gerektiriyor mu, lisans acik mi arastirilacak.
2. **Videvo** (videvo.net) — lisans/ticari kullanim kontrol edilecek.
3. **Openverse** (openverse.org) — CC search, keyless API, image fallback olarak dusunulebilir.
4. **Pixabay cookie yenileme** — kullanicidan yeni PIXABAY_COOK istenecek (daha sonra).

## 7. Guvenlik kontrol listesi

- [x] API key yok (NASA API kodu kaldirildi, DEMO_KEY bile kullanilmaz).
- [x] Host allowlist hem search hem download URL'leri icin.
- [x] Content-Type video/ dogrulamasi.
- [x] Byte siniri (64 MB) — stream sirasinda da kontrol edilir.
- [x] SHA256 hash hesaplamasi.
- [x] ffprobe cozunurluk/kodek/dogrulama.
- [x] ffmpeg -f null tam decode.
- [x] CAPTCHA/Cloudflare bypass YOK (bu kaynaklar bot korumasi kullanmiyor).
- [x] Hicbir secret kullanmiyor (public_providers_probe workflow).
- [x] Yukleme/yayinlama/veri silme YOK.
