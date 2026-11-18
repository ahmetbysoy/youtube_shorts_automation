# Faz 4 — İlk Actions denemesi (tarihsel, kabul değildir)

Kaynak `eb9910914dfff018e202d9ce467dbe15ce2e0c5a`.

- Ubuntu 26 CI [44284971550](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44284971550) **success**: 218 Python test + 16 alt test; 47 hedefli Faz 4 testi, 35 Faz 3 testi ve 5 Node katalog parser testi başarılı.
- Ayrı yayınsız canlı medya koşusu [44285033824](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44285033824) **failure**. Bu koşu kabul kanıtı değildir.
- Commons gerçek API/source license + download + decode + sahne manifesti başarılı oldu: `NASA Apollo 17 Lunar Roving Vehicle.jpg` ve `Louis-Emile Durandelle, The Eiffel Tower - State of the Construction, 1888.jpg`, per-file Public domain kanıtı. Ancak FFmpeg consumer çıktısı `yuvj420p` full-range işareti taşıdı; mevcut `validate_output` doğru biçimde reddetti. İndirilen Actions MP4'ünde bağımsız ffprobe ile doğrulandı. QC gevşetilmedi.
- Pexels/Pixabay bu koşuda üç sınırlı sorguda kabul edilebilir katalog adayı vermedi; maskeli credential değeri/eksik anahtar/oturum bozukluğu gibi alt nedenler bu ilk genel sonuçtan çıkarılamaz. Sonraki düzeltme güvenli API/cookie-presence ve HTTP/katalog sayaçlarını ekler. Gerçek sağlayıcı entegrasyonu başarılı ilan edilmez.
- Sonraki düzeltme: yalnız strict storyboard render'ında `scale out_range=tv`, limited-range metadata, explicit 30 FPS CFR; legacy filtreler ve sert final QC korunur. Sentetik JPEG+test tone dosyalarıyla **gerçek FFmpeg** ve bozuk gerçek MP4 decode regresyonları eklendi. Bunlar gerçek sağlayıcı testleri değildir.
- Düzeltmeler sonrası yerel tam suite **222 passed + 16 subtests**, hedefli Faz 4 **51 passed**, 5 Node parser testi başarılı. Yeni commit'in CI ve canlı sonucu ayrıca doğrulanmalıdır.

Yayın, silme, taslak yayınlama veya production history değişikliği yapılmadı. Güvenli workflow'un yetkisi `contents: read`; stock kaynak dosyaları artifact'e konmadı. JSON kanıt dosyaları secret denetiminden geçti. İlk koşu kaynak artifact ID `14418123218`; kanıt dosyaları `output/phase4_actions_44285033824/` altında incelendi (üretim çıktıları Git'e eklenmedi).
