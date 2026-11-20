# FAZ C — Otonom Uretim Durumu (2026-11-20 21:43 UTC)

## ✅ DURUM: CANLI — İLK PIPELINE VIDEOSU PUBLIC YAYINDA
- **Video:** https://youtube.com/shorts/R_EfF7h8JIM  
- **Başlık:** Fatih Sultan Mehmet Gemileri Karadan Nasıl Yürüttü? #Shorts  
- **Run:** 44821267926 (workflow_dispatch)  
- **Tüm fazlar BAŞARILI**, 12 dakikada tamamlandı.

## Kanıtlanmış Çalışma Zinciri
1. Safety gate (cookie/sağlık/kota/aralık/stop) — ✅
2. Faz 2: Gemini Web (180s hard timeout) + local fallback + edge-tts — ✅
3. Faz 2.5: script.json şema doğrulaması — ✅
4. Faz 3: 6 sağlayıcıdan medya seçimi + FFmpeg montaj (BGM+altyazı) — ✅
5. Faz 3.5: Kapak karesi gömme (AI görsel + başlık) — ✅
6. Faz 4: QC (dosya + içerik) — ✅
7. Faz 5: Playwright ile YouTube Studio PUBLIC yükleme — ✅
8. Kanal hijyeni (banner/about/pin) — ✅
9. Artifact + logların repo'ya otomatik commitlenmesi — ✅

## Aktif Cron Tablosu (UTC)
| Saat     | Workflow                | Islem                                           |
|----------|-------------------------|-------------------------------------------------|
| 05:00    | `01_healthcheck.yml`    | Cookie + EMERGENCY_STOP + public probe          |
| 06:00    | `daily_analytics.yml`   | Analytics                                       |
| :13/2 saat | `daily_shorts.yml`    | Uretim (gate 8/gun + 60dk spacing ile denetler) |
| :25      | `draft_publisher.yml`   | Taslaklari yayinla                              |
| :07,:37  | `hourly_pruner.yml`     | Dusuk izlenme temizligi                         |
| 23:30    | `06_daily_summary.yml`  | Gunluk ozet                                     |

## Guvenlik Kapisi (scripts/production_gate.py)
Her uretimden once 5 kontrol:
1. **EMERGENCY_STOP**: env/stop-file/GitHub issue label "EMERGENCY_STOP"
2. **Cookie saglik**: GEMINI/PEXELS/PIXABAY/YT min uzunluk
3. **Gunluk kota**: 8/gun (varsayilan, `DAILY_VIDEO_LIMIT` ile ayarlanabilir)
4. **Aralik**: Son yayindan 60+ dk gecmis olmali
5. **Ardisik hata freni**: 3 hata ust uste → 2sa dur

## Duzeltilen Kritik Hatalar (2026-11-20)
1. **Gemini client.init() tamamen takiliyordu** — asyncio.wait_for(25s) eklendi,
   auto_refresh=False, per-topic 80s timeout, total 180s hard timeout.
2. **youtube_studio_uploader.js dotenv MODULE_NOT_FOUND** — try/catch ile opsiyonel.
3. **Faz 2 timeout 600s → 360s** düşürüldü (fallback'e daha hizli donus).
4. **REPO_PAT secret güncellendi** → cookie refresh 401 hatasi duzeltildi.
5. **Print buffer flush** sorunları giderildi (loglar anında gorunuyor).

## Bilinen Notlar
- Gemini Web ara ara 80s timeout'a düşüyor (cookie oturumu/rate-limit kaynakli);
  bu durumda fallback yerel senaryo havuzu devreye girer ve video uretimi devam eder
  (R_EfF7h8JIM'in senaryosu bu sekilde uretildi).
- Analytics → konu ağırlıklandırma feedback loop'u henuz yapilacak.
- BGM/QC/thumbnail polish itemleri temel zincir stabil calistikca gelecek.

## Durdurma Mekanizmasi
- Repo'da `EMERGENCY_STOP` etiketiyle issue ac → tum uretim bir sonraki cron'da DURUR
- Issue'u kapat → uretim otomatik devam eder
- Healthcheck basarisiz olursa otomatik EMERGENCY_STOP issue acilir
