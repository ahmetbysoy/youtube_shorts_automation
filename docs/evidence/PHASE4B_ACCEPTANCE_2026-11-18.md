# Faz4B — canlı medya, gerçek tüketici ve kalıcı history kabul raporu

**2026-11-18 · NOT ACCEPTED / TAM KABUL GEÇMEDİ.** Yerel aynı-source canlı Commons video/CC BY ve izin verilen fixture zinciri, gerçek iki-Actions history ve CI geçti. Stock erişimi geçmedi; Actions canlı Commons da download/decode’da bloklandı. Yerel başarı remote failure’ı değiştirmez. **Faz5 başlamadı.** [Makine okunur bütün kanıt](PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json).

## 1. Başlangıç ve final SHA

- Başlangıç clean local/GitHub main: `316ae2e3e1aff89483d367a5d7ea2e82f0f68665`.
- Ana kod/test/probe commit’i [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472) (`5c883f4ded05df896309274ed6e5a368eb178472`).
- Final test edilmiş kod/workflow kaynağı [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106) (`59e2c79ae10ff38c297130d5b775a10427e64106`). Aradaki tek dosya `.github/workflows/phase4_media_probe.yml`: provider’lara ulaşmadan yavaş Ubuntu apt indirmesi nedeniyle dependency kurulumu düzeltildi, provider erişim kapıları değiştirilmedi.
- Final CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745), final media [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341) ve aşağıdaki yeni yerel canlı Commons zinciri **59e2c79** üzerindedir. History write [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963), verify [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849), önceki CI [44297771082](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297771082) ve iptal edilen media [44297831876](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297831876) **5c883f4** üzerindedir. History kod/probe/workflow blob’ları final kaynakla aynı olduğu bağımsız karşılaştırıldı; tüm koşular aynı head diye sunulmaz.
- Belgeler ayrı docs-only teslim commit’inde kaydedilir; teslim HEAD’i son yanıtta/Git main’de verilir. Docs-only HEAD’in henüz çalışmamış CI’sı yeşil diye iddia edilmez.
- Tarihsel e4d1144, CI44288761602/live44288761461 ve233+16/62/5 snapshot’ı kısmi/başarısız kabul olarak korunur; eski JSON’un SHA’sı yeni kanıtta kayıtlıdır.

## 2. Değişen dosyalar

### Kod/test/yayınsız workflow (17)
- `.github/workflows/phase4_media_probe.yml`
- `.github/workflows/phase4b_history_probe.yml`
- `.github/workflows/ubuntu_26_test.yml`
- `scripts/media_probe_security.py`
- `scripts/phase4_media_probe.py`
- `scripts/phase4b_consumer_chain.py`
- `scripts/phase4b_history_probe.py`
- `scripts/phase4b_live_evidence.py`
- `scripts/phase4b_media_probe.py`
- `scripts/stock_media_catalog.cjs`
- `scripts/uploader_metadata_probe.cjs`
- `src/media_processing/media_history.py`
- `src/media_processing/media_providers.py`
- `src/media_processing/scene_media.py`
- `tests/test_phase4b_consumers.py`
- `tests/test_phase4b_media.py`
- `tests/uploader_metadata_probe.test.cjs`

### Belge/kanıt (10)
- `README.md`
- `AI_HANDOFF.md`
- `docs/ARCHITECTURE.md`
- `docs/GEMINI_AUTONOMOUS_SHORTS_PLAN.md`
- `docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md`
- `docs/PHASE1_SCRIPT_JSON_INVENTORY.md`
- `docs/PHASE4_MEDIA_ENGINE.md`
- `docs/evidence/PHASE4_ACTIONS_EVIDENCE_2026-11-18.md`
- `docs/evidence/PHASE4B_ACCEPTANCE_2026-11-18.md`
- `docs/evidence/PHASE4B_ACTIONS_EVIDENCE_2026-11-18.json`

## 3. Fiilî kod değişiklikleri

- Hash-only recent hit, gerçek çözünürlük/süre ve dedup ölçümü seçimden önce **en fazla dört indirilen uygun aday** arasında rerank edilir. Tüm metadata havuzu sınırsız indirilmez; seçilen ve eligible-not-selected adayların gerçek ölçüm/puan/kararı manifestte ayrıdır.
- Public transport prepared-request aşamasında session/netrc auth/Cookie/custom-key başlıklarını her allowlisted hop’ta siler. Authenticated catalog redirect kapalıdır. Browser child API/GitHub/Gemini/ENV_FILE env alamaz; yalnız temel env ve provider-specific stock cookies alır, 403’te durur.
- Probe ENV_FILE data-only/interpolate=False parse eder; yalnız exact iki stock key, direct değer öncelikli, kendi API constructor’ına gider; yeniden os.environ export veya shell source/eval/disk kopyası yoktur. Production `.env` hazırlığı değiştirilmedi.
- Commons GETID3 playtime_seconds advertised duration olarak okunur; gerçek full decode/ölçüm yine zorunlu. Attribution=false/CC BY çelişkisi, malformed port ve query/fragment lisans URL’si reddedilir; eksik izin tahmin edilmez.
- Media-history corrupt base64/eksik SHA fail-closed; incoming batch aynı key+generation’ı bir kez ekler. Local atomic/flock ve bounded Contents SHA-CAS korunur; kayıp update azaltımı distributed reservation değildir.
- Actual fixture/live consumer helper’ları, unchanged uploader’dan iki gerçek saf fonksiyonu kısıtlı ağsız VM’de çıkaran helper, minimum-permission isolated history workflow’u ve güvenli artifact audit’i eklendi. Paid medya/görsel/metin API’si eklenmedi.
- İptal edilen run’ın logu yavaş regional Ubuntu mirror indirmesini gösterdi. Yalnız probe runner’ında Python-first, çalışan resmî Ubuntu aynası/no-recommends ve step/apt timeout’ları eklendi. Provider host/403/license/decode kapıları gevşetilmedi; production setup action’ı değişmedi.

## 4. Test sayıları ve CI

| Kontrol | Yerel | Ubuntu26 CI [44301070745](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301070745) |
|---|---|---|
| Tam Python | 301 passed+16 subtests, 1 mevcut warning,32.30sn; workflow-fix sonrası tekrar301+16/28.42sn | **301+16**,14.01sn |
| Faz3 hedefli tekrar | 35 | **35**,0.96sn |
| Faz4+4B hedefli tekrar | 122 (62 eski+60 yeni) | **122**,1.18sn |
| Actual fixture consumer hedefli tekrar | 8 | **8**,3.11sn |
| Node catalog+actual pure metadata | 5+6=11 | **11 passed,0fail** |
| Mevcut pruner pure-logic | 7 yerel | Bu satır yalnız yerel; gerçek pruner/deletion yok |
| Syntax/IO | Python compile/Node --check/3 workflow YAML/27 shell block syntax; offline FFmpeg/Pillow | Python/Node syntax, Chromium, ASS/FFmpeg, pre-post schema ve UTF16 credit geçti |

Hedefli Python sayıları ana301’in altkümelerinin ayrı tekrarlarıdır, toplam test gibi toplanmaz. CI actual writer/wrapper/renderer/cover/saf metadata çalıştırır, **provider/download girdisi offline fixture’dır**; canlı provider kanıtı değildir. Önceki source CI [44297771082](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297771082) de301+16/122/8 geçti.

Boundary: URL/providerID değişse de aynı bytes ve iki scene; hash-only/measured-quality rerank; local multiprocess lost-update; mocked Contents403/404/409/422/5xx/corrupt payload/retry exhaustion; license yok/çelişkili; UTF16/CTA/affiliate/hashtag; redirect allowlist/credential forwarding; missing/partial/truncated/full decode. Mocks/live ve local flock/distributed lock ayrımı korunur.

Geliştirme hataları gizlenmedi: ilk yeni test import collection hatası `tests.` nitelemesiyle, exact-byte fail-closed testindeki snapshot newline farkı actual writer bytes kopyasıyla düzeldi. Mevcut asyncio deprecation warning’i durur. Bunlar ilk kaynak commit’inden önceki test hatalarıdır; aşağıdaki gerçek Actions failures ayrıca saklanır.

## 5. Her provider canlı sonucu ve exact konfigürasyon izi

**İlk attempt [44297831876](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297831876): cancelled, provider testine ulaşmadı.** Apt yaklaşık996sn boyunca çok yavaş bölgesel Ubuntu indirmesi yaptı; teşhis için yalnız bu izole run durduruldu. Sonraki audit adımı pip henüz çalışmadığı için dotenv import edemedi; artifact/audit pass iddiası yok. İptal POST202 bir kez kabul edildi; helper’ın202’yi tanımadığı hata yeniden POST’a yol açmadı. Bu run için provider403 veya Commons başarı sonucu çıkarılmaz.

**Düzeltilmiş tek yeni run [44301095341](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44301095341): failure / partial_provider_evidence_full_acceptance_failed.** Bağımlılıklar kuruldu, üç provider gerçekten denendi, güvenli JSON artifact yüklendi. Hiçbiri iki-scene seçim/son consumer zincirini tamamlayamadı.

| Provider | Bu run’daki gözlem | Gerçek sonuç |
|---|---|---|
| Pexels | api_key_present=false; media_cookie_file_present=true; direct/env exact-name booleans false | API çağrısı yok; browser queryID q-377953d30900 HTTP403/BrowserHTTPBlocked; 0 selected scene; **blocked_unverified** |
| Pixabay | api_key_present=false; media_cookie_file_present=true; direct/env exact-name booleans false | API çağrısı yok; browser aynı queryID HTTP403/BrowserHTTPBlocked; 0 selected scene; **blocked_unverified** |
| Commons Actions | Anahtarsız gerçek API katalog adayları döndürdü | SA/teknik/tür retleri uygulandı; uygun video174336538 ve83680173 **download_or_decode_failed/RuntimeError**; 0 selected scene; **blocked_unverified** |
| Commons ayrı yerel aynı-SHA | Aynı fixture, aynı gerçek provider/strict wrapper | Video174336538 + still83667454; gerçek HTTP/source/license/download/full decode/consumer **passed**; **Actions success değildir** |

Exact isim/çağrı zinciri:

1. `daily_shorts.yml:138–166`: CHANNEL_ENV_FILE ← secrets[ENV_FILE_kanal], fallback ← secrets.ENV_FILE; seçilen içerik üretimde `.env` yazılır. MEDIA_COOKIES_JSON mevcut stock cookies’i production cookies.json’a birleştirir. Bu production davranışı/secret’lar değiştirilmedi, workflow dispatch edilmedi.
2. `media_processor.py:49,72,107` mevcut .env yüklemesi ve exact **PEXELS_API_KEY / PIXABAY_API_KEY** okuması; `config/settings.py:30–31` aynı adları okur. Yeni strict PexelsProvider/PixabayProvider aynı isimleri destekler. Eski Python/adaptör akışı korunur.
3. `video_fetcher.js` **API key gerektirmeyen cookie tabanlı browser yoludur**; cookies.json/storage_state.json okur. Metadata CLI branch’i `stock_media_catalog.cjs` kullanır; yalnız ilgili Pexels veya Pixabay cookie domain’leri context’e eklenir. Browser child API key veya ENV_FILE alamaz. Legacy keyless downloader değiştirilmedi.
4. Yeni manual probe yalnız secrets.ENV_FILE → **PHASE4_PROVIDER_ENV** ve direct exact iki stock adı alır; consume_provider_configuration dotenv DATA/interpolate=False parse eder, allowlisted iki değeri bellekte ayrı tutar, her biri yalnız ilgili provider constructor’ına gider. ENV_FILE disk/shell’e çıkmaz; başka/alias isim tahmini yapılmaz. Bu run’da ENV_FILE supplied=true fakat iki exact-name nonempty allowed stock değeri gözlenmedi.
5. MEDIA_COOKIES_JSON yalnız izinli stock domain’lerini **0600**, exclusive geçici cookies.json’a yazar; Google/YouTube session taşınmaz ve job sonunda silinir. Cookie file varlığı oturumun çalıştığını kanıtlamaz.

REST secret-name metadata ve runtime config yalnız booleans olarak JSON’da. Secret değerleri API’den alınmadı; key prefix/length/hash loglanmadı. Sonuç bu repository/probe/run kapsamındadır: **account-wide API key yok/cookie expired** çıkarımı yapılmaz. Yeni key/secret/refresh/stealth/proxy/CAPTCHA/bypass yoktur. Commons generic RuntimeError’dan HTTP403 veya codec nedeni uydurulmaz; bu ayrımı sağlayacak daha güvenli tanılama açık iştir. Aynı stock403 körlemesine tekrar denenmedi.

## 6. Commons hareketli video ve zorunlu CC BY — yerel canlı kanıt

**Kanıt sınıfı: aynı final source 59e2c79 ile ayrı YEREL gerçek provider zinciri; Actions artifact’i değildir.** `output/phase4b_local_verified_59e2c79/provenance.json`, chain/manifest/script ve gerekli composite/kareler ayrı 11 dosyalı güvenli staging’dedir. İki kaynak ve lisans deed’i gerçek HTTP ile kontrol edildi; aşağıdaki başarı başarısız Actions run’ına atanmaz.

### Scene 1 — video, ID 174336538

- Provider wikimedia; [source File sayfası](https://commons.wikimedia.org/wiki/File:Strong_waves_from_hurricane_Erin_at_white_crest_beach,_Wellfleet,_MA_august_22,_2025.webm).
- Query-free download URL: `https://upload.wikimedia.org/wikipedia/commons/8/87/Strong_waves_from_hurricane_Erin_at_white_crest_beach%2C_Wellfleet%2C_MA_august_22%2C_2025.webm`.
- SHA256: `59521adeb0585c6734e9187501765130e420465a8df92f676d0c199ad7451340`.
- Lisans **CC BY 4.0**, `https://creativecommons.org/licenses/by/4.0`; attribution_required=true; creator **Magpieturtle**.
- Selector evidence metodu **commons_per_file_extmetadata**; ayrıca canonical File identity/aynı creator/lisans linki HTTP200, official CC BY deed HTTP200. Body evidence hash’leri JSON’da; third-party rights verified=false.
- Ölçülen **1920×1080**, oran **1.777778**, süre **16.933** (image null). Download/full decode/actual consumer passed.
- Kabul gerekçesi: source/provenance/license/full decode/ölçülen teknik gates + metadata-supported relevance. Genel visual semantic approval değildir.
- **Tam zorunlu atıf:** Strong waves from hurricane Erin at white crest beach, Wellfleet, MA august 22, 2025.webm — Magpieturtle — CC BY 4.0 (https://creativecommons.org/licenses/by/4.0); https://commons.wikimedia.org/wiki/File:Strong_waves_from_hurricane_Erin_at_white_crest_beach,_Wellfleet,_MA_august_22,_2025.webm; değişiklikler: ölçekleme/kadraj, süre ve altyazı montajı.

### Scene 2 — image, ID 83667454

- Provider wikimedia; [source File sayfası](https://commons.wikimedia.org/wiki/File:Kolufoss_waterfall_water_flowing_downstream,_July_2019.jpg).
- Query-free download URL: `https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cf/Kolufoss_waterfall_water_flowing_downstream%2C_July_2019.jpg/1920px-Kolufoss_waterfall_water_flowing_downstream%2C_July_2019.jpg`.
- SHA256: `b1856b8e0986a993d194b910494e5ce8c8f5d94c88117edc8ec6881922ee64e0`.
- Lisans **CC BY 3.0**, `https://creativecommons.org/licenses/by/3.0`; attribution_required=true; creator **Alexander Grebenkov**.
- Selector evidence metodu **commons_per_file_extmetadata**; ayrıca canonical File identity/aynı creator/lisans linki HTTP200, official CC BY deed HTTP200. Body evidence hash’leri JSON’da; third-party rights verified=false.
- Ölçülen **1920×2893**, oran **0.663671**, süre **null** (image). Download/full decode/actual consumer passed.
- Kabul gerekçesi: source/provenance/license/full decode/ölçülen teknik gates + metadata-supported relevance. Genel visual semantic approval değildir.
- **Tam zorunlu atıf:** Kolufoss waterfall water flowing downstream, July 2019.jpg — Alexander Grebenkov — CC BY 3.0 (https://creativecommons.org/licenses/by/3.0); https://commons.wikimedia.org/wiki/File:Kolufoss_waterfall_water_flowing_downstream,_July_2019.jpg; değişiklikler: ölçekleme/kadraj, süre ve altyazı montajı.

Video scene1’de cover dışı source-content alanından decoded örnekler **[0.9538, 2.3152]sn**; ortalama mutlak RGB farkı **33.031227/255**, farklı sample SHA’ları. Gerçek temporal değişim gözlendi; constant-frame MP4 negatif fixture bunu geçmez. Pixel değişimi action modeli/fact onayı değildir.

İnceleme kareleri scene1’de kıyı/dalga ve belirgin portrait letterbox, scene2’de downstream kanyon/akarsu gösterir. Belirgin düşen şelale yüzeyi doğrulanmadı; narration buna göre yeniden yazılmadı. `visual_verification=not_performed` ve action/era/relationship açığı korunur. PD dosyaları CC BY veya gerçek video yerine sayılmaz.

**Yerel** consumer: 6.000000sn,1080×1920,H264/AAC,yuv420p,30FPS/180frame, **1804923byte**, SHA256 `92db77fa49a1c8d931ffa676a663d6a1bb4e5cd579500cf49f8513390d17b5b2`. Mevcut QC + bağımsız ffprobe + tam ses/görüntü decode geçti. MP4 Git’e/YouTube’a yüklenmedi; Actions’ta böyle bir başarılı composite üretildiği iddia edilmez.

## 7. Üretici–tüketici zinciri

**Yerel canlı Commons’ta tamamlandı; CI aynı gerçek bileşenleri offline provider/download fixture ile geçti. Actions canlı probe pre-validator’dan sonra selection’da bloklandı; sonraki adımlara ulaşmadı.**

`explicit draft fixture → actual draft_to_script_metadata → ROOT run_content_pipeline writer(v2 UUID) → pre-validator CLI → SAME JSON actual run_media_pipeline → strict selector/per-scene manifest/credits/description → atomic persist/reload → post-validator CLI → actual embed_cover_frame.main --no-ai JSON read-only → actual extracted readScenarioField/buildFinalDescription VM`.

- Root writer gerçekten çalıştı; yalnız scenario-generation ve speech-synthesis girişleri explicit fixture/synthetic-tone adaptörüdür. Ayrı eski src/content_generation/engine.py root wrapper sanılmadı ve bu zincirde çalıştırılmadı.
- Yerel generation UUID `3db59da2-1079-4f90-b539-a33980bfbfca`; pre/post storyboard/narration birebir aynı; fact_check.status=unavailable değişmedi. Partial/fixture verified diye etiketlenmedi.
- Pre/post schema ve gerçek validator CLI0 hata. Post-media JSON SHA `dafc80c3f20bbca23ddc7982ff5d0c58ea76fa4550670265b2ff9676e6e12929` cover/saf JS sonrasında aynı.
- Cover için yalnız best-effort exit0 değil, gerçek cover ve değişen izole MP4/aynı JSON arandı. No-AI; paid/free vision/Gemini çağrısı yok; cover sistemi değiştirilmedi.
- Uploader unchanged source’tan yalnız iki gerçek saf işlevi çıkarılır, entrypoint import/require/evaluate edilmez; VM network/process/require içermez. Final açıklama **858 UTF16**, konservatif üst sınır **858≤4900**. İki mandatory CC BY atfı description+media_credits+actual builder’da tam; bağımsız tekrar hesaplaması birebir aynı.
- İzin verilen **fixture-tabanlı gerçek tüketici entegrasyonu** kanıtlandı. Canlı Gemini/TTS, Studio form kalıcılığı, dinamik bütün caller’lar ve otomatik PUBLIC hazırlığı kanıtlanmadı.

## 8. İki ayrı Actions medya-history ve cleanup

- Her iki history koşusu da [`5c883f4`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/5c883f4ded05df896309274ed6e5a368eb178472) üzerinde çalıştı. History core/probe/workflow blob’ları final [`59e2c79`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/59e2c79ae10ff38c297130d5b775a10427e64106) ile birebir aynı; koşular final SHA’da çalışmış gibi gösterilmez.
- ProbeID `p4b-20261118-34bcd240392c`; ref `phase4b-media-history/p4b-20261118-34bcd240392c`; özel path `.phase4b-probes/p4b-20261118-34bcd240392c/media_history.json`. Production main history hedeflenmedi.
- Run1 [44297836963](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44297836963): GET404 → seed PUT201; primary GET sonrası ayrı competing client PUT200; stale primary PUT **409**. Core remember gerçek GET200/reread → merged PUT200 ile seed+competing_writer+primary_writer üç synthetic sentinel’ı korur. Final blob **04fb90a1a33f9e74bbbc0a73b62afab54e089930**.
- Run2 [44298014849](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44298014849): farklı Actions runID, artifact/local cache değil gerçek Contents GET200 ile aynı blob ve üç entry birebir okunur.
- Cleanup: probe dosyası DELETE200, ref silinmeden dosya GET404; ref DELETE204, ref/path GET404. Bağımsız authenticated salt-okur ref/path/main-probe/main-media-history GET’leri de404. **Cleanup failure yok.** Git object’lerinin güvenli fiziksel silinmesi iddia edilmez.
- Çatışma run1 içindeki controlled gerçek iki-client interleaving’idir; persistence ayrı sıralı iki Actions arasındadır. Spontane cross-Actions race/distributed lock/reservation değildir. Sentinellar gerçek selection/publication history kaydı değildir; local flock dağıtık kilit diye sunulmaz.

## 9. Secret ve artifact güvenliği

- Repository secret değerleri API’den alınmadı/yazılmadı/değiştirilmedi. İzinli mevcut stock ENV/cookie materyali probe belleğinde parse edildi; değer/prefix/length/hash/log/artifact yok. Her API key yalnız kendi provider’ına; browser’a key yok.
- Checkout credential persistence kapalı. Media contents:read; history workflow root permissions{}, yalnız dedicated job contents:write; repository provider/Google/YouTube/Gemini secret’ı veya actions:write yok.
- **Altı** tamamlanmış yeni job logunda supplied GitHub credential ve unmasked GitHub/Google-key pattern0. Maskelenmiş, erişilemeyen stock secret değerleri log taraması için alınmadı. Sekiz eski audit tarihsel JSON’da korunur; hepsi yeni koşu diye sayılmaz.
- Üç Actions artifact’inin upload-öncesi audit’i, o workflow’da erişilebilen izinli secret materyaliyle bellekte karşılaştırır. Bağımsız indirmelerde supplied credential/pattern/JSON query-fragment-userinfo URL/allowlisted dosya/byte/SHA manifest kontrolleri0; upload audit listesi gerçek dosyalarla eşleşti. İptal edilen run audit’i geçmedi/artifact üretmedi.
- **Bu final media Actions artifact’i yalnız safe JSON’dır**; render/cover’a ulaşmadığı için başarılı Commons MP4/kare içerdiği iddia edilmez. Gerekli Commons composite/kareler ayrı **yerel**11 dosyalı staging’de audit edildi. Cookie/storage_state/ENV_FILE/signedURL/raw stock yok; MP4 Git’e eklenmedi. Geçici ham Commons kaynakları wrapper temp cleanup’ında silinir.
- Ignored credential untracked, origin credential-free. Bu tarama erişilemeyen her secret’ın matematiksel yokluk ispatı değildir.

| Actions artifact | ID | Arşiv byte |
|---|---|---|
| phase4b-media-evidence-44301095341 | 14424224647 | 15904 |
| phase4b-history-write-44297836963 | 14424741945 | 1723 |
| phase4b-history-verify-44298014849 | 14423942369 | 1513 |

## 10. Korunan üretim davranışları

Başlangıç 316ae2e / final kaynak 59e2c79 / remote main Git blob karşılaştırmasında **19 korunan dosya aynı**. main/root ve bağımsız eski producer/Gemini dönüşümü/Studio-API uploader/kapak helpers/production-pruner-publisher workflows/schema-validator/media_processor/legacy video_fetcher/settings/samples/topic history korunur. Tam blob listesi JSON’da.

Gemini cookie-only ve GEMINI_COOK/GEMINI_API_KEY isimleri/mevcut yerel fallback/no-paid-text-fallback; onaylı partial publication policy; PUBLIC doğrulaması, kanal sırası/concurrency/quota/upload idempotency/kapak sistemi değişmedi. `.used_topics.json` **25 başlık/0pending**, blob e5a987fccba23d6d37f1aed76e560cd0647e8f26, title-list SHA `7eca291fbb7b1f462b92210afce9c0c328971d78ef98413a45a3e0644184176d`. Production media-history main404, main probe path404. Testlerin local topic dosyası mutasyonları exact bytes geri alındı.

main.py/gerçek uploader/YouTube/production-pruner-publisher workflows test-dispatch veya run edilmedi; upload, PUBLIC/draft publication, video/draft deletion yok. Kabul edilmiş Faz3 probe’ları tekrar dispatch edilmedi. Media CLI --help parse etmez: önceki Faz4 kazası/restore/quarantine tarihsel raporda korunur; Faz4B’de tekrarlanmadı.

## 11. Açıklar ve riskler

- Pexels/Pixabay live source/license/download/consumer coverage is unverified in Actions: no nonempty exact-name allowlisted API key observed, cookie file present, browser403. No account-wide absence or cookie-expiry inference.
- Actions Commons catalog returned candidates, but eligible videos174336538/83680173 were rejected with download_or_decode_failed/RuntimeError. The evidence cannot separate HTTP/download/full-decode causes. The same-source LOCAL chain passed; it does not convert failed Actions into a pass.
- General visual action/era/relationship verification is not implemented; pixel motion and lexical metadata are not semantic approval. Scene2 is downstream canyon/river flow, not an established falling-water face; narration was not rewritten.
- Explicit scenario fixture and synthetic tone are NOT live Gemini/TTS evidence; Phase5 timing/audio and publication readiness remain open.
- CAS preserves observed concurrent writes but is not distributed reservation; parallel runs may select the same fresh clip. Perceptual/transcoded dedup is not implemented.
- Independent legacy producer, dynamic external callers and backup API/actual Studio consumers are not a complete runtime-inventory acceptance.

## 12. Kabul kararı

| Ölçüt | Sonuç |
|---|---|
| Gerçek Commons moving video+mandatory CC BY/source/deed/download/full decode/actual consumer | **YEREL aynı-SHA geçti; Actions zinciri GEÇMEDİ** |
| İzin verilen explicit-fixture actual writer→same JSON strict wrapper→post-validator→cover→saf metadata | **Yerel canlı Commons ve CI offline fixture geçti; canlı Gemini/TTS/Studio değil** |
| İki distinct Actions history+gerçek HTTP409/reread/merge+cleanup | **GEÇTİ; controlled interleaving, distributed reservation değil** |
| Ubuntu26 CI/temiz scoped scans/korunan üretim | **GEÇTİ** |
| Pexels/Pixabay canlı kabul | **GEÇMEDİ: exact-name nonempty allowed API key gözlenmedi/cookie file var/browser403** |
| Faz4B full acceptance | **NOT ACCEPTED / GEÇMEDİ** |
| Faz5 / otomatik PUBLIC hazırlığı | **BAŞLAMADI / DOĞRULANMADI** |

Stock zorunlu koşulu eksikken teşhis kabulün yerine geçmez. Commons yerel başarı/Actions failure ayrımı da zorunludur. Mevcut izinli erişimle güvenli çözüm yoksa blokaj açık kalır; yeni secret/cookie yenileme veya403 bypass yapılmaz, aynı probe körlemesine tekrar tetiklenmez. **Faz5’e geçilmedi.**
