# FAZ C — Otonom Uretim Durumu (2026-11-20)

## Hedef
Minimum insan mudahalesiyle, gunde 8 Shorts, surekli calisan pipeline.

## Aktif Cron Tablosu (UTC)
| Saat     | Workflow                | Islem                                           |
|----------|-------------------------|-------------------------------------------------|
| 05:00    | `01_healthcheck.yml`    | Cookie saglik + EMERGENCY_STOP kontrolu         |
| 06:00    | `daily_analytics.yml`   | Analytics toplama                               |
| 13,33,53,73,... her 2 saat | `daily_shorts.yml` | 8/gun video uretim (guvenlik kapisindan gecerse) |
| :25      | `draft_publisher.yml`   | Taslaklari yayinla                              |
| :07,:37  | `hourly_pruner.yml`     | Dusuk izlenme temizlik                          |
| 23:30    | `06_daily_summary.yml`  | Gunluk uretim ozeti                             |

## Guvenlik Kapisi (scripts/production_gate.py)
Her uretimden once otomatik calisir, 5 kontrolden biri RED ise uretim ATLANIR:
1. **EMERGENCY_STOP**: `EMERGENCY_STOP=1` veya `EMERGENCY_STOP` etiketli acik issue.
2. **Cookie saglik**: GEMINI_COOK/PEXELS_COOK/PIXABAY_COOK/YT min uzunlukta.
3. **Gunluk kota**: `DAILY_VIDEO_LIMIT` (varsayilan 8) bugunki yayin sayisi.
4. **Aralik**: Son yayindan `MIN_UPLOAD_SPACING_MINUTES` (varsayilan 60 dk) gecmis olmali.
5. **Ardisik hata freni**: Ust uste 3 hata olursa uretim durur, 2 saat sonra otomatik tekrar dener.

Kayitlar `logs/published_log.json` ve `logs/error_log.json` repo icinde tutulur,
GitHub Contents API ile her uretim sonrasi otomatik commitlenir.

## Durdurma ve Iyilestirme
- Repo'da `EMERGENCY_STOP` etiketiyle acik issue acmak uretimi DURDURUR.
- Issue kapatmak uretimi otomatik olarak devam ettirir (healthcheck sabah kontrol eder).
- Healthcheck basarisiz olursa otomatik olarak `EMERGENCY_STOP` + `HEALTHCHECK_FAILURE` etiketli issue acilir.
- Manuel test: `daily_shorts.yml` workflow_dispatch ile `dry_run=1` secilerek
  SKIP_UPLOAD modunda calistirilabilir (YouTube'a yuklemez, tum asamalari test eder).

## Bilinen Sorunlar / Izleniyor
- **Gemini Web timeout**: Bazen `gemini_webapi` istemcisi 10 dakika timeout'a dusuyor
  (600 saniye Faz 2 timeout'u). Bu durum ard arda 3 kez olursa guvenlik kapisi
  uretimi 2 saatligine durdurur; sonraki cron denemesinde devam edilir.
- **REPO_PAT 401**: Secret yenilenmesi gerekiyor (cookie geri-yazma islemi),
  uretimi durdurmaz (sadece cookie refresh islevi atlanir).

## Kanitlar
- Healthcheck run (2026-11-20 20:36): tum cookie'ler OK, public provider probe OK
- Safety gate dry_run (2026-11-20 20:37): gate ALLOW=true, loglar repo'ya islendi
- Son basarili uretim: `p1d5EPUQuQE` (run 44655900502)
