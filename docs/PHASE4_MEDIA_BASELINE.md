# Faz 4 — Başlangıç medya envanteri (2026-11-18)

Başlangıç local/remote `main`: `98392fa97f9cb7916ea2f03833913e9566e09ce7`; çalışma ağacı temiz, GitHub ref API ile aynı SHA doğrulandı. Faz 3 kaynak kodu `0dee88e`, CI `44279794329`, iki-run kalıcılık `44280024395` / `44280111635` korunur.

## Mevcut davranış (değişiklik öncesi)

- `main.py`: içerik → JSON Schema → `media_processor.py` → medya sonrası JSON Schema → mevcut kapak → Studio uploader. Uploader/yayın kapısı bu görevde çalıştırılmaz/değiştirilmez.
- `get_visual_search_queries`: storyboard `visual_query` alanlarını düz liste yapar; yoksa legacy `visual_keywords`, sonra history/nature/cinematic varsayılanları.
- `run_media_pipeline`: süreyi sorgu sayısına böler (en az 8 sn), sorguları modulo ile tekrarlar, en fazla 8 klip. Bir sahne başarısızken diğerleriyle devam edebilir. Gerçek narration/sahne eşleştirmesi yoktur.
- Gerçek arama sırası: **Playwright → Pexels API → Pixabay API → Wikimedia Commons**. Python docstring'inin Pexels-first ifadesi bu operasyonel sıra için yanıltıcıdır.
- Playwright `video_fetcher.js`: mevcut `cookies.json` / `storage_state.json`, önce Pixabay sonra Pexels. CDN `_tiny`→`_large`→`_medium` URL denemeleri ve Pexels sayfa/video kaynakları. HTTP indirme, dosya >50 KB. Python bunu her zaman `playwright-pixabay` olarak etiketleyebilir. Source-page/creator/license/duration/dimensions sözleşmesi yoktur; sorgu metni gerçek video metadata'sı değildir.
- Pexels: `PEXELS_API_KEY` Authorization başlığı, portrait search, 8 sonuçtan rastgele bir video, dosya varyantı seçimi. Yalnız URL/duration/provider/kind döner; source-page/ID/creator/license kaybolur.
- Pixabay: `PIXABAY_API_KEY` query parametresi; redirect kapalı ve hata metni değil exception türü loglanır. Rastgele hit, large/medium dosya. Yalnız URL/duration/provider/kind döner; source-page/tags/license kaybolur.
- Commons: ücretsiz resmi API, önce video sonra bitmap, sorguyu sadeleştirip ilk kelimeye kadar genişletebilir. Dosya title exclusion listesi ve boyut/mime kontrolleri var. Video/bitmap duration 10.5 sn varsayılır; duration kaynak kanıtı değildir. Extmetadata'dan kısaltılmış credit çıkarılır ama eksik license otomatik engellenmez; credit helper bazı durumlarda lisans adı varsayabilir. **Commons kaldırılmayacak.**
- İndirme `requests` stream; >1 KB ve ffprobe video stream/width kontrolü. Tam decode/gerçek boyut-süre karşılaştırması yoktur. Render videoyu loop ederek 1080×1920 crop/zoompan + ASS + ses; teknik final ffprobe QC ayrı.
- Commons credit `script.json.description` ve `media_credits` içine eklenir, fakat 4900 karakter kesmesi atfı kesebilir. Sağlayıcı metadata'sı ve sahne bazlı lisans manifesti yoktur.
- İlgili testler: `tests/test_faz3_media.py` (eski medya faz numarası), `test_faz13_trust.py`, `test_script_json_schema.py`; gerçek sağlayıcı doğrulaması yerine geçmez.

## Faz 4 sınırı ve tasarım

Storyboard mevcutsa yeni ayrı selector: bounded primary/alternatives, narration+metadata relevance, lisans kanıtı, açıklanabilir teknik puanlar, provider fallback, tam download/decode, bir scene→bir dosya, ID/URL/content-hash dedup ve ayrı medya geçmişi. Storyboard yoksa yukarıdaki legacy yol korunur; legacy yolun eski eksikleri Faz 4 tarafından doğrulanmış sayılmaz. Scene süreleri narration ağırlıklı **geçici** plan; TTS timestamp alignment Faz 5.

Pexels/Pixabay resmi servis şartları dosya/API metadata kimliğiyle birlikte kontrol edilir; siteye ait bir CDN URL'si tek başına lisans değildir. Commons per-file extmetadata korunur. Bilinmeyen lisans veya share-alike/ND/NC gibi downstream politikası karşılanmayan koşullar güvenli ret. Ücretli model/API eklenmez; cookie/API secret yapılandırması korunur. Sağlayıcı metadata eşleşmesi görsel/uzman doğrulaması diye etiketlenmez.

Gerçek HTTP/download/probe kanıtı ve mock/regresyon testleri ayrı raporlanacak. Bu envanterin kendisi Faz 4 kabul kanıtı değildir. Phase 1 ek JSON tüketici taraması ve gerçek tüketici entegrasyon işi hâlâ açıktır.
