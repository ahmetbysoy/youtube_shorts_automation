# Faz6C: Mixkit Free Stock Video provider (cookie-free)

**Tarih:** 2026-11-20
**Durum:** IMPLEMENTED, locally verified (1080p download + full-decode pass), CI probe pending.

## Özet
Mixkit (mixkit.co) cookie/API key gerektirmeyen, Free License ile ticari kullanıma
izinli, attribution gerektirmeyen bir stok video sitesidir (Envato sahibi).
Kategori sayfaları (`/free-stock-video/{keyword}/`) doğrudan HTML içinde MP4
URL'leri gömülüdür; Playwright/cookie gerekmez.

## Kanıt (yerel sandbox)
- URL: https://assets.mixkit.co/videos/1779/1779-1080.mp4 ("Pet owner playing with a cute cat")
- 1920×1080, 15.08s, h264 Main @ 24 Mbps, 45.4 MB
- ffmpeg -i: stream + duration OK
- ffmpeg -f null - tam decode: exit 0
- Content-Type: video/mp4, HTTP 200, browser User-Agent ile sorunsuz

## Mimari
- `MixkitProvider` sınıfı eklendi (keyless public HTTP).
- Host allowlist: `SOURCE_HOSTS = {mixkit.co, www.mixkit.co, assets.mixkit.co}`
  `DOWNLOAD_HOSTS = {assets.mixkit.co}`
- Arama: `GET https://mixkit.co/free-stock-video/{slug}/?page=1,2` (slug: lowercase+dash).
- Parse: BeautifulSoup ile HTML içinden MP4 URL'leri regex ile toplanır.
- Free tier çözünürlük seçimi: 1080 > 720 > 360. 4K (2160) premiumdur ve atlanır.
- Restricted License klipleri: sayfada "premium" veya restricted olarak
  işaretlenmişlerse ve yalnızca 360p seçeneği sunuluyorsa filtrelenir.
- Content-Type ve byte-sınırı (64 MB) HEAD ile doğrulanır.
- License: StockTerms Mixkit Free License (canonical snapshot) → verified=True,
  attribution_required=False, no_standalone_redistribution.
- `default_providers()` sırası: pexels-browser, pixabay-browser, **mixkit**,
  nasa, archiveorg, wikimedia.

## Test
- `tests/test_phase6_public_providers.py` içinde 5 yeni test: host allowlist,
  StockTerms Mixkit license, slug normalizasyonu, kategori sayfası parse
  (1080p seçimi, 2160p atlama), search HEAD filtreleme.
- Toplam 12 birim testi, 12/12 geçiyor.

## Lisans (doğrulanan)
- Mixkit Free License: kişisel + ticari kullanım, YouTube monetization dahil.
- Attribution gerekmez (takdir edilir).
- Düzenleme/modifikasyon serbest.
- Yasak: tekrar stok dosya olarak dağıtmak, rakip stok platformlarına yüklemek.
- Restricted License klipler ticari kullanımda yasak; sadece bu etiketi olmayan
  free klipler seçilmelidir.
- Bireysel videolardaki marka/şahıs hakları kullanıcı sorumluluğunda.
