# Faz 4 — Sahne medya sözleşmesi ve güvenlik sınırı

Başlangıç davranışı ve sağlayıcı/API/Playwright sırası: [PHASE4_MEDIA_BASELINE.md](PHASE4_MEDIA_BASELINE.md). Bu belge uygulanmış kodun tasarımını açıklar; [canlı kanıt raporu](evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md) **tam Faz 4 kabulünün geçmediğini** kaydeder. Storyboard bulunmayan payload'ların eski davranışı korunur; eski yolun lisans/uygunluk açıkları yeni kod tarafından doğrulanmış sayılmaz.

## 1. Akış

`media_processor.run_media_pipeline` içinde **storyboard anahtarının varlığı** strict yolu seçer. Boş/bozuk storyboard generic legacy aramaya düşmez. `run_storyboard_pipeline` → `scene_plan` → ortak sağlayıcı katalogları → hard gates/puanlama → bounded download/tam decode → yeniden ölçüm/gates → her sahne için manifest → tam atıf + atomik script JSON → mevcut ASS/FFmpeg tüketicisi → mevcut sert teknik QC. Başarısız sahne varken montaj başlatılmaz. `output/scene_media_manifest.json` başarısızlığı da kaydeder.

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

Puanlar: query metadata 0–30, narration metadata 0/20, çözünürlük 0–15, oran 0/6/10, süre 0/10, sağlayıcı provenance 0/5 (bilinen sağlayıcı kimliği proxy’si; ölçülmüş uptime/başarı olasılığı değil), lisans kanıtı 0/10; yakın dönem aynı ID/kaynak kullanımına **−25**. Puanlar hard gate'i geçersiz kılamaz. Kaynak metadatasında comparison/slideshow/credits ve belirli hassas terimler konservatif ret sebebidir.

Minimum kısa kenar **720 px**, uzun kenar **1080 px**; oran **0.4–2.2**. Extreme panorama/çok uzun dar dosya ret. Geçen landscape/square dosyalar **contain/letterbox** ile bütünü korunarak montaja gider; nesnenin merkezde olduğu varsayılarak kör crop/zoom yapılmaz. Gerçek dosya ölçümleri reklam edilen boyutların yerine geçer.

Video süresi geçici planlanan segmenti karşılamalıdır; strict video loop ile uzatılmaz. Stiller açıkça image olarak belirtilen süre boyunca gösterilir. Her download HTTPS allowlist + sınırlı redirect zinciri (en fazla 4 HTTP denemesi) / **64 MiB**, kontrollü partial-file cleanup; gerçek Pillow decode veya ffprobe + tüm görsel stream'in FFmpeg decode testi. Video uzunluğu 0'dan büyük ve en fazla 120 sn olmalıdır. HTML/challenge sayfası, kırık/truncated dosya, bozuk stream kabul edilmez.

`assessment.relevance_status=metadata_supported`, **`visual_verification=not_performed`**. Bu, bağımsız görsel model/insan onayı değildir; black-frame/estetik kalite veya gerçekten anlatılan olayı gösterme garantisi verilmez. Belirsiz relation/subject ret; metadata destekli ancak yanıltıcı adaylar yine mümkün olduğundan bütünleşik kalite kapısı sonraki fazdadır.

## 5. Scene-media kaydı

`scene_media[]` içinde scene_id, selected_provider, selected_media_id, source_url, license, attribution, **gerçek** duration (image için null), resolution, aspect_ratio, selection_score, rejection_reason, fallback_used, tried queries, reddedilen adaylar, safe provider diagnostics, file SHA-256/decode sonucu ve score components bulunur. `planned_duration` bundan ayrıdır.

JSON Schema yeni alanları opsiyonel ve geriye uyumlu tanımlar. Mevcut validator medya sonrası çıktı varsa storyboard ile **sıralı birebir kapsama**, unique scene IDs/clip identity ve tam zorunlu atıf kontrol eder; yarım manifest geçemez. Üretim sırası/uploader/PUBLIC varsayılanı değiştirilmedi, yeni genel yayın kalite kapısı tamamlandı denmez.

## 6. Tekrar ve ayrı kalıcı geçmiş

Aynı videoda provider:ID, normalize source/download URL ve gerçek dosya SHA-256 tekrarları hard-block. Bütün sahnelere aynı genel klip atanamaz.

Ayrı `.media_history.json` şeması `{version:1, entries:[...]}`: son 200 seçimi saklar, son 100 seçim recency penalty için kullanılır. Bu **medya seçimi geçmişidir**, yayın geçmişi değildir; sonraki render hatası seçimi publication yapmış saymaz. Faz 3 `.used_topics.json` dosyasına veya topic reservation'a dokunmaz.

Yerel lock+fsync+atomic replace. Actions env'de repository + token birlikteyse GitHub Contents API blob SHA-CAS ile bounded 6 reread/merge/retry; eksik konfigürasyon, bozuk geçmiş veya API hatası fail-closed. Bu distributed reservation değildir; paralel iki yeni run aynı klibi okuyup seçebilir. CAS lost-update'i önler; yakın dönem tekrarı azaltma tüm concurrency yarışlarını önleme garantisi değildir. Yeni kimlik/URL altında aynı hash ancak download sonrası tespit edilir; bu recency puanı indirilmiş adayı global yeniden sıralamaz. Byte-hash dedup transcode/crop gibi near-duplicate algılama değildir. Gerçek media-history iki-run persistence testi ayrıca yapılmadıkça mock CAS testleri canlı kanıt diye sunulmaz.

## 7. Faz 5 ve yayın sınırı

Süreler narration word count ağırlıklı **geçici** bölünür; gerçek TTS word timestamp hizalaması yoktur. Strict render limited-range yuv420p/30 FPS CFR'yi açıklar; legacy filtreler ve mevcut sert final QC korunur. Bu küçük teknik düzeltme Faz 5 sahne/ses/altyazı senkron kabulü değildir.

Canlı probe sabit iki-scene test girişi + sentetik test tonu kullanır. Gerçek Gemini üretimi/TTS diye sunulmaz. Güvenli `phase4_media_probe.yml` yalnız public/provider HTTP, indirme, lisans, decode, JSON ve consumer smoke çalıştırır; `contents:read`, production history write ve YouTube adımı yoktur. Artifact'ler credential denetimi sonrası metadata/kanıt ve yalnız Commons kompozit örneği içerir; cookie/ENV_FILE/ham stock dosyası yüklenmez. `daily_shorts.yml`, pruner ve draft publisher bu görevde test amacıyla çalıştırılmaz.
