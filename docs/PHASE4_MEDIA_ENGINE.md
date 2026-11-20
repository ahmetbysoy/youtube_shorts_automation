# Faz 4 — Sahne medya sözleşmesi ve güvenlik sınırı

> **Güncel Faz 4C — 2026-11-18: Faz4B NOT_ACCEPTED, Faz5 başlamadı.** Kaynak [`14f7896`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/14f78962f2444e9d03fe0d0caf9b22efff06d927); yeni CI [44313713933](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313713933) **361 Python + 16 alt test**, hedefli tekrar **35/182/8**, **16 Node** geçti. Kullanıcının yeni cookies’i **API kullanılmadan** [44313751238](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44313751238) Actions koşusunda test edildi: preflight **8 Pexels + 7 Pixabay eşleşen cookie kaydı**, iki ayrı browser araması **HTTP403 / blocked_unverified**. Commons iki CC BY videoda source/deed/download **200**, tam byte/SHA256 ve container probe geçti; **full_decode_failed**, render/final QC not_reached. API/ENV_FILE bu run’da okunmadı; API key eksikliği cookie testi için blocker değildir. Yeşil CI/offline fixture veya eski yerel Commons, yeni canlı kabul yerine geçmez. Önceki iki-run history/gerçek409 proof’unun üç blob’u aynı; cleanup dört404 ile salt-okur tekrar doğrulandı, yeniden dispatch edilmedi. **22 protected blob, 26 topic/0pending** korundu; üretim/yayın/silme yok. [12 başlıklı yeni rapor](evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) · [JSON](evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json).

> **Tarihsel Faz4B snapshot’ı:** Kaynak `59e2c79`, CI44301070745 **301+16/35/122/8/11Node**; eski yerel canlı Commons tam zinciri geçti, eski Actions44301095341 stock403 ve generic Commons download/decode failure verdi. Bu eski kayıtlar yeni koşu değildir; [Faz4B raporu](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) ve [JSON](evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json) değiştirilmeden korunur.

Başlangıç davranışı ve sağlayıcı/Playwright sırası: [PHASE4_MEDIA_BASELINE.md](PHASE4_MEDIA_BASELINE.md). Bu belge uygulanmış kodun tasarımını açıklar; [canlı kanıt raporu](evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md) **tam Faz 4 kabulünün geçmediğini** kaydeder. Storyboard bulunmayan payload'ların eski davranışı korunur; eski yolun lisans/uygunluk açıkları yeni kod tarafından doğrulanmış sayılmaz.

> **2026-11-20 politika güncellemesi: API anahtarı kullanılmaz — cookie-only / keyless public.** `PEXELS_API_KEY`/`PIXABAY_API_KEY` rotası kaldırılmıştır. Pexels/Pixabay ve benzeri sağlayıcılar **yalnızca Playwright + cookie** rotasıyla çalışır; cookie gerektirmeyen sağlayıcılar (NASA, Internet Archive, Wikimedia Commons) doğrudan HTTPS public API üzerinden çalışır. Hiçbir koşulda API key/ücretli servis kullanılmaz. Referans mimari: Pexels Playwright+cookie zincirinin stock-cookie-probe run #11'de (44773494574) başardığı arama→CDN MP4 indirme→SHA256→ffprobe→tam decode akışıdır (bkz. [Faz5 sertleştirme raporu](evidence/FAZ5_HARDENING_REPORT_2026-11-16.md)). CAPTCHA/Cloudflare bot koruması asla bypass edilmez.

## 1. Akış

`media_processor.run_media_pipeline` içinde **storyboard anahtarının varlığı** strict yolu seçer. Boş/bozuk storyboard generic legacy aramaya düşmez. `run_storyboard_pipeline` → `scene_plan` → ortak sağlayıcı katalogları → hard gates/puanlama → bounded download/tam decode → yeniden ölçüm/gates + en fazla dört indirilen adayda measured rerank → her sahne için manifest → tam atıf + atomik script JSON → mevcut ASS/FFmpeg tüketicisi → mevcut sert teknik QC. Başarısız sahne varken montaj başlatılmaz. `output/scene_media_manifest.json` başarısızlığı da kaydeder.

Sahne planı: `visual_query`, sonra sırası korunmuş en fazla **3** benzersiz `alternative_queries`. Otomatik ilk-kelimeye/genel doğa görüntüsüne genişletme yok. En fazla 12 sahne, 180 karakter sorgu, sahne başına en fazla 4 dosya indirme denemesi. Narration ile primary query arasında bilinen terim desteği yoksa güvenli ret; bilinmeyen çeviri/parafraz doğrulanmış sayılmaz.

Yeni strict yolun provider önceliği: **Pexels API → Pixabay API → Pixabay metadata Playwright → Pexels metadata Playwright → Wikimedia Commons**. Her sorguda bütün sağlayıcılar sorgulanır, ortak sınırlı aday havuzu global puanla sıralanır; bu sıra ilk-başarıda-duran hiyerarşi değildir, eşit puanda önceliktir. Önceki sağlayıcının başarısızlığı sonraki sağlayıcıyı engellemez. Commons video ardından bitmap API sorgularını korur. Legacy yolun Playwright-first sırası değiştirilmedi.

## 2. Ortak sözleşme

`media_providers.MediaProvider.search(query) -> list[MediaCandidate]`:

| Alan | Kaynak / anlam |
|---|---|
| provider, media_id | Gerçek API kimliği; browser'da kaynak sayfası ID'si |
| media_url, download_url | Sağlayıcının verdiği dosya URL'si; raporlarda query/fragment temizlenir |
| source_url | Sağlayıcının gerçek asset/File sayfası; arama sayfası değil |
| media_type | video veya image |
| width, height, duration, aspect_ratio | Önce sağlayıcı metadatası; kabul öncesi gerçek dosya ölçümü. Bilinmeyen değer null, uydurma süre yok |
| title, description, tags | Yalnız gerçek aday metadatası. Arama sorgusu adayın kanıtına eklenmez |
| license | ad, gerçek URL (bilinmiyorsa boş), doğrulama yöntemi/kanıt URL'si/tarih/hash, koşullar ve ret gerekçesi |
| attribution_required / attribution / creator | Lisans içinde korunur; zorunlu atıf tam metin olarak açıklamaya da eklenir |
| download_status | not_downloaded → downloaded_and_decoded; yalnız indirmek kabul değildir |
| catalog_transport | api veya playwright |

API anahtarları mevcut `PEXELS_API_KEY` / `PIXABAY_API_KEY`; cookie ayarları mevcut dosyalardır. Browser strict metadata modu `video_fetcher.js --metadata --provider ...` üzerinden ayrı katalog modülüne gider; eski indirme CLI'si korunur. Sadece CDN URL'si ve search rank'i yeterli değildir: kaynak sayfasında JSON-LD VideoObject kimliği ve lisans linki aranır. Bulunamazsa sonuç boş/kanıtsızdır. Stock browser context'ine yalnız Pexels/Pixabay cookie'leri alınır; Google/YouTube session taşınmaz.

## 3. Lisans kapısı

- **Pexels/Pixabay:** resmi lisans/tam şartlar URL'si HTTP ile alınır; izin VE kısıtlama cümleleri tanınmadan provider-wide lisans kabul edilmez. HTTP/challenge/şart değişikliği güvenli ret. API veya gerçek browser asset sayfası kimliğiyle birlikte değerlendirilir. Pexels/Pixabay CC0 diye etiketlenmez.
- **Commons:** per-file `extmetadata` gerekir. Sürümü ve URL'si uyuşan CC BY 2.0/2.5/3.0/4.0 (adı jurisdiction belirtiyorsa o da URL ile aynı olmalı), gerçek CC0 declaration veya açık `License=pd-*` + Public domain + AttributionRequired=false desteklenir. Çelişkili sürüm, sürümsüz/NC adıyla permissive URL, user-info veya standart dışı port içeren lisans linki izin varsayılarak uzlaştırılmaz; güvenli ret. Public domain kaydında LicenseUrl yoksa CC0 URL'si uydurulmaz; kaynak File sayfası kanıt olarak saklanır.
- **CC BY:** creator, dosya adı, kaynak URL, lisans adı/URL ve planlanan değişiklik bildirimi tam atıfta korunur. Eksik creator/atıf ret. Açıklama 4900 UTF-16 birime sığmazsa atıf kesilmez; üretim durur. Uploader aynı açıklamaya affiliate/CTA/hashtag ekleyip yeniden `.slice(0,4900)` uyguladığı için strict yol bu alanların tamamı için konservatif ek bütçe de ayırır; gerekirse geçmiş yazılmadan/render başlamadan ret. Uploader değiştirilmez; mevcut iki saf metadata fonksiyonu ayrı, ağsız VM testinde çalıştırılır, uploader entrypoint’i asla import/execute edilmez.
- **BY-SA/NC/ND/diğer:** downstream lisans yükümlülüklerini mevcut YouTube yayın yolu yerine getirmiş varsayamayız. Otomatik strict seçim reddeder; izin/uygun politika olmadan standart YouTube lisansı altında yeniden etiketleme yok. Commons tamamen kaldırılmaz, uyumlu diğer dosyalar denenir. Legacy policy'yi sessizce değiştirmez.
- Bu kapı telif lisansı **metadata/şart kontrolüdür**; model/property release, marka, özel hayat, kişilik hakları ve endorsement uygunluğu otomatik doğrulanmış değildir. Bunlar restrictions içinde açık kalır. Stock dosyaları bağımsız ham dosya olarak artifact'e yeniden dağıtılmaz.

Resmi inceleme bağlantıları (2026-11-18): [Pexels License](https://www.pexels.com/license/), [Pixabay full terms](https://pixabay.com/service/terms/), [Pixabay summary](https://pixabay.com/service/license-summary/), [Commons reuse guidance](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia). Doküman URL'si tek başına runtime provider/lisans kanıtı değildir; ilgili dosyanın manifest gözlemi gerekir.

## 4. Açıklanabilir uygunluk ve teknik kapılar

Hard gates: kaynak/download allowlist HTTPS, lisans kanıtı, zorunlu atıf, same-video duplicate, desteklenen medya türü; primary query/narration subject anchor'ları ve gerçek aday metadata overlap. Sorgu coverage en az 0.5; query+narration iki ayrı bilinen anchor taşıyorsa ikisi de gerekir. Küçük TR/EN sözlüğü vardır; bilinmeyen çevirileri modelle tahmin etmez.

Puanlar: query metadata 0–30, narration metadata 0/20, çözünürlük 0–15, oran 0/6/10, süre 0/10, sağlayıcı provenance 0/5 (bilinen sağlayıcı kimliği proxy’si; ölçülmüş uptime/başarı olasılığı değil), lisans kanıtı 0/10; yakın dönem aynı ID/kaynak veya gerçek byte-hash kullanımına **−25**. Hash-only hit download sonrası seçimden önce bounded measured havuzda yeniden sıralanır; tüm metadata havuzu indirilmiş sayılmaz. Puanlar hard gate'i geçersiz kılamaz. Kaynak metadatasında comparison/slideshow/credits ve belirli hassas terimler konservatif ret sebebidir.

Minimum kısa kenar **720 px**, uzun kenar **1080 px**; oran **0.4–2.2**. Extreme panorama/çok uzun dar dosya ret. Geçen landscape/square dosyalar **contain/letterbox** ile bütünü korunarak montaja gider; nesnenin merkezde olduğu varsayılarak kör crop/zoom yapılmaz. Gerçek dosya ölçümleri reklam edilen boyutların yerine geçer.

Video süresi geçici planlanan segmenti karşılamalıdır; strict video loop ile uzatılmaz. Stiller açıkça image olarak belirtilen süre boyunca gösterilir. Her download HTTPS allowlist + sınırlı redirect zinciri (en fazla 4 HTTP denemesi) / **64 MiB**, kontrollü partial-file cleanup; gerçek Pillow decode veya ffprobe + tüm görsel stream'in FFmpeg decode testi. Video uzunluğu 0'dan büyük ve en fazla 120 sn olmalıdır. HTML/challenge sayfası, kırık/truncated dosya, bozuk stream kabul edilmez.

`assessment.relevance_status=metadata_supported`, **`visual_verification=not_performed`**. Bu, bağımsız görsel model/insan onayı değildir; black-frame/estetik kalite veya gerçekten anlatılan olayı gösterme garantisi verilmez. Belirsiz relation/subject ret; metadata destekli ancak yanıltıcı adaylar yine mümkün olduğundan bütünleşik kalite kapısı sonraki fazdadır.

## 5. Scene-media kaydı

`scene_media[]` içinde scene_id, selected_provider, selected_media_id, source_url, license, attribution, **gerçek** duration (image için null), resolution, aspect_ratio, selection_score, rejection_reason, fallback_used, tried queries, reddedilen adaylar, safe provider diagnostics, file SHA-256/decode sonucu ve score components bulunur. `planned_duration` bundan ayrıdır.

JSON Schema yeni alanları opsiyonel ve geriye uyumlu tanımlar. Mevcut validator medya sonrası çıktı varsa storyboard ile **sıralı birebir kapsama**, unique scene IDs/clip identity ve tam zorunlu atıf kontrol eder; yarım manifest geçemez. Üretim sırası/uploader/PUBLIC varsayılanı değiştirilmedi, yeni genel yayın kalite kapısı tamamlandı denmez.

## 6. Tekrar ve ayrı kalıcı geçmiş

Aynı videoda provider:ID, normalize source/download URL ve gerçek dosya SHA-256 tekrarları hard-block. Bütün sahnelere aynı genel klip atanamaz.

Ayrı `.media_history.json` şeması `{version:1, entries:[...]}`: son 200 seçimi saklar, son 100 seçim recency penalty için kullanılır. Bu **medya seçimi geçmişidir**, yayın geçmişi değildir; sonraki render hatası seçimi publication yapmış saymaz. Faz 3 `.used_topics.json` dosyasına veya topic reservation'a dokunmaz.

Yerel lock+fsync+atomic replace. Actions env’de repository+token birlikteyse Contents blob SHA-CAS ile bounded6 reread/merge/retry; eksik config/corrupt base64/eksik SHA/API hatası fail-closed; 404 boş history, 409/422 reread/merge. Aynı incoming key+generation batch tekrarı bir kez eklenir. Hash-only recency artık seçimden önce en fazla dört indirilen uygun aday arasında measured rerank yapar. Bu distributed reservation değildir; paralel run’lar aynı yeni klibi seçebilir. Byte hash transcode/crop near-duplicate değildir. Gerçek iki-run proof [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963) → [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849) üç synthetic sentinel, controlled gerçek HTTP409/reread/merge, distinct remote read ve file/ref cleanup içerir; production history ve selection/publication kaydı değildir.

## 7. Faz 5 ve yayın sınırı

Süreler narration word count ağırlıklı **geçici** bölünür; gerçek TTS word timestamp hizalaması yoktur. Strict render limited-range yuv420p/30 FPS CFR'yi açıklar; legacy filtreler ve mevcut sert final QC korunur. Bu küçük teknik düzeltme Faz 5 sahne/ses/altyazı senkron kabulü değildir.

Canlı probe sabit iki-scene test girişi + sentetik test tonu kullanır. Gerçek Gemini üretimi/TTS diye sunulmaz. Güvenli `phase4_media_probe.yml` yalnız public/provider HTTP, indirme, lisans, decode, JSON ve consumer smoke çalıştırır; `contents:read`, production history write ve YouTube adımı yoktur. Artifact'ler credential denetimi sonrası metadata/kanıt ve yalnız Commons kompozit örneği içerir; cookie/ENV_FILE/ham stock dosyası yüklenmez. `daily_shorts.yml`, pruner ve draft publisher bu görevde test amacıyla çalıştırılmaz.

## 8. Faz4B güvenlik, gerçek tüketici ve canlı kanıt sınırı

- get_public prepared request’te yalnız User-Agent/Accept bırakır; session auth/netrc/Cookie/custom-key her allowlisted hop’ta silinir. Authenticated catalog redirect kapalıdır; HTTPS/host/byte/license/decode kapıları gevşetilmez.
- Probe exact PEXELS_API_KEY/PIXABAY_API_KEY’yi kendi API constructor’ına bellekte verir; ENV_FILE DATA/interpolate=False, disk kopyası/source/eval yoktur. Browser child yalnız temel env allowlist’i ve provider-domain stock cookie’si alır; Google/YouTube/Gemini/API key yoktur. 403’te durur, tanılama provider/status/queryID/safe class’tır. Üretim ENV_FILE→.env ve cookie kurulum kodu korunur.
- CC BY attribution=false çelişkisi, malformed port ve query/fragment lisans URL ret; eksik izin tahmin edilmez. Kabul helper’ı canonical File HTML creator/lisans ve official CC BY deed HTTP’sini ayrıca kontrol eder. Selector evidence metodu commons_per_file_extmetadata’dır; ekstra HTML/deed kanıtı ayrı stage’dir.
- phase4b_consumer_chain gerçek root writer/ara dönüşüm/pre-post validator/strict wrapper/persist-reload/no-AI cover JSON reader/unchanged uploader’dan iki gerçek saf işlevi kullanır. Scenario/TTS sınırları explicit fixture/synthetic tone’dur. Entry-point/Studio yoktur.
- Aynı final kaynak [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106) ile **yerel** canlı Commons video174336538 CC BY4.0 + still83667454 CC BY3.0 ve bütün zincir geçti. Motion cover dışı decoded source-content sample değişimidir; general visual-action/era/relationship onayı değildir. İkinci still downstream kanyon/akarsu, belirgin falling-water yüzeyi kanıtı değildir; narration değiştirilmedi.
- **Actions [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) failure:** stock no nonempty allowlisted API key/cookie file var/browser403; Commons katalog adayları174336538/83680173 download/decode RuntimeError. Bu generic code HTTP/download/full decode nedenini ayırmaz; local pass remote pass değildir. CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745) actual chain’i offline fixtures ile geçti (**301+16**, targeted tekrar35/122/8,11 Node).
- İlk media [44297831876](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297831876) provider testinden önce 996 saniyelik yavaş regional apt indirmesinden sonra iptal edildi. Yalnız izole workflow’da Python-first, resmî çalışan Ubuntu aynası, no-recommends ve bounded step/timeouts düzeltildi; sonra tek gerekçeli yeni media dispatch yapıldı. Provider host/403 kısıtı değişmedi.
- Tarihsel phase4_media_probe.py selector/assembler smoke olarak durur. Yeni manual workflow actual-chain probe çağırır; eksik zorunlu provider evidence exit1, safe staged JSON upload-öncesi audit sonrası always artifact. Bu run’ın Actions artifact’i yalnız JSON’dır; gerekli Commons composite/kareler ayrı **yerel** 11 dosyalı staging’dedir. History dışında yeni write izni yoktur.

**NOT ACCEPTED:** Stock canlı erişimi ve Actions Commons zinciri eksik. [12 başlıklı rapor](evidence/PHASE4B_ACCEPTANCE_2026-11-18.md) · [JSON](evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json). Faz5 başlamadı; TTS/audio/timing/PUBLIC hazırlığı iddia edilmez.

## 9. Faz4C cookie-only preflight ve ayrık IO kanıtı

Manual `phase4_media_probe.yml` varsayılanı explicit `stock_access_mode=cookie_only`’dir. Bu mod yalnız BrowserStockProvider üretir; ENV_FILE parser ve stock API constructor’ı kullanılmaz. Exact API/ENV_FILE secret referansları yalnız ayrı açık legacy auto seçeneğinde korunur; cookie-only step’lerine bu değerler yüklenmez. Preflight’a yalnız direct-secret presence booleans + güncel MEDIA_COOKIES_JSON gelir; field/domain/type/duplicate ve iki provider grubu doğrulanmadan canlı provider adımı başlamaz. Cookie kayıtları private0600 geçici dosyadadır, alan/domain allowlist’i hem Python hem browser transferinde uygulanır; context’ler provider-specific’dir.

`get_public(trace=...)` yalnız public allowlisted host/hop/status tutar; arbitrary URL/header/body veya exception saklamaz. `MediaIOError` sabit safe class + ayrı HTTP, redirect/finalhost, Content-Type, Content-Length, received bytes, file SHA, container/probe ve full-decode alanlarını taşır. Gerçek default selector download/probe aynı trace’i paylaşır; injected offline adapter kendiliğinden canlı download kanıtına dönüşmez. Full-probe başarısızsa download başarısı kaybolmaz; tam decode başarısızsa file lisansı geçse de seçilmez. FFmpeg/ffprobe file,pipe whitelist dışındaki protokolleri kullanamaz.

`phase4c_commons_diagnostics.py` bağımsız bounded iki aday teşhisidir; scene assignment veya consumer yerine geçmez. File ve official deed HTTP ayrı kontrol edilir; download/probe/full decode bağımsız stage’lerdir. Gerçek consumer stage’i ancak aynı ID+dosya SHA ile ilişkilendirilir; source/license veya full-chain başarısı salt render’dan çıkarılmaz. Yeni Actions44313751238’de iki CC BY video download200/bytes/SHA/probe’u geçti, full_decode_failed ile reddedildi; source/metadata/license success, decode/consumer success değildir. Exact stderr/codec kök nedeni tutulmadı.16JSON artifact’te başarılı MP4 yoktur.

Yeni CI44313713933 @14f7896 **361+16/35/182/8 ve16Node** geçti; fixture sınırları korunur. Pexels/Pixabay yeni cookies ile ayrı403 aldı, API test edilmedi. Yeni sonuçlar [Faz4C raporu](evidence/PHASE4C_ACCEPTANCE_2026-11-18.md) ve [JSON](evidence/PHASE4C_ACTIONS_EVIDENCE_2026-11-18.json)’dadır. **Faz4B NOT_ACCEPTED, Faz5 başlamadı.**
