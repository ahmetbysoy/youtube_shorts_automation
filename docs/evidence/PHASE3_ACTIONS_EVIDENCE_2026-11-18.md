# Faz 3 — Actions kabul kanıtı

**Tarih:** 18 Kasım 2026 · **Sonuç:** yeni-kod CI + iki ayrı Actions koşusunda kalıcılık şartları **GEÇTİ**.

**Doğrulanmış kaynak commit’i:** [`0dee88e18e05269e7d4f7360614123eb890f4e80`](https://github.com/ahmetbysoy/youtube_shorts_automation/commit/0dee88e18e05269e7d4f7360614123eb890f4e80)

**Makine okunur gözlem kaydı:** [PHASE3_ACTIONS_EVIDENCE_2026-11-18.json](PHASE3_ACTIONS_EVIDENCE_2026-11-18.json)

## 1. Kapsam ve sınır

Bu kabul; deterministik kaynak/iddia kontrolü, konu tekrar koruması, yeni kodun Ubuntu 26 CI uyumu ve reservation state’in iki **farklı** Actions koşusu arasında kalması içindir. Canlı YouTube üretim/yayın/silme, yeni Gemini model taslağı, kanal geneli geçmiş taraması veya sahne-medya kalite kabulü değildir. Önceki gerçek Gemini Web run’ı [44262444017](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44262444017) korunur; o koşu önceki kodda `draft_only=true`, `publish=false`, `fact_check=partial` idi.

`daily_shorts.yml`, `draft_publisher.yml` ve `hourly_pruner.yml` tarafımızdan dispatch edilmedi. Var olan bağımsız schedule/cron ayarları değiştirilmedi; bu rapor onların tüm eş zamanlı işlemlerini denetlediğini iddia etmez. Repository Secret’lar değiştirilmedi. Kullanıcı onaylı `partial` yayın politikası ve cookie-only/fallback davranışı korundu; `partial`, `verified` diye etiketlenmez.

## 2. Yeni-kod Ubuntu 26 CI

| Alan | Kanıt |
|---|---|
| Koşu | [44279794329](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44279794329) |
| Event / branch | `push` / `main` |
| Kaynak SHA | `0dee88e18e05269e7d4f7360614123eb890f4e80` |
| Runner | `ubuntu-26.04` |
| Sonuç | **success** |
| Hedefli Faz 3 suite | **35 passed in 0.84s** |
| Tam Python suite | **171 passed, 16 subtests passed in 9.80s** |

Başarılı adımlar: FFmpeg/font/Xvfb kurulumu; Python ve Node kurulumu; uploader JS syntax; Python bağımlılıkları; iki Phase 3 CLI module-import/`--help` smoke testi; Playwright Chromium/dependency kurulumu; FFmpeg 1080×1920 metin bindirme smoke testi; hedefli ve tam Python testleri. FFmpeg bindirme smoke testi tüm ASS/sahne-ses senkronunun uçtan uca kanıtı olarak sunulmaz.

Yerel ek doğrulama: **171 Python testi + 16 alt test**, **7 Node testi**, üç Node syntax kontrolü, YAML ve bash syntax, `git diff --check`. Yerelde bir mevcut asyncio event-loop deprecation uyarısı var. Temiz venv’de yalnız pinned `requests` kurulu halde iki CLI import/help başarılı. Probe ile oluşan gerçek v2 geçmiş üzerinde tam yerel suite de tekrar geçti (171 + 16 alt test); test yan etkisi geri alınarak 25 başlık/25 record/0 pending korundu. Güncellenen Markdown dosyalarının yerel bağlantılarında kırık hedef yok.

## 3. İki ayrı Actions koşusunda gerçek kalıcılık

Ortak kimlik: `probe_id=phase3-20261118`

Rezervasyon: `phase3-probe-phase3-20261118`

| Aşama | Actions / gözlem | Sonuç |
|---|---|---|
| Önce | 09:52:39 UTC, legacy title array | 25 used title, 0 pending |
| Reserve | [44280024395](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280024395), checkout `0dee88e`, 09:52:41 UTC | **success**; Contents API’ye pending reservation yazıldı |
| Ara gözlem | 09:53:13 UTC, yeni runner dışından Contents API GET | v2, 25 used title / 25 legacy-derived record, **1 pending**, probe used history’de yok |
| Verify | [44280111635](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44280111635), checkout `c421f2b`, 09:53:14 UTC | **success**; ikinci koşu reservation’ı GitHub’dan okuyup `commit=false` ile serbest bıraktı |
| Sonra | 09:53:31 UTC, Contents API GET | v2, 25 used title / 25 record, **0 pending**, probe used history’de yok |

İki koşu farklı run ID’lerine ve ayrı runner checkout’larına sahiptir; bu bir retry veya aynı job içindeki iki komut değildir. Verify checkout’u CI kaynağından yalnız `.used_topics.json` açısından farklıdır; API compare sonucu makine kaydındadır.

Gerçek log satırları:

```text
[OK] reservation persisted; id=phase3-probe-phase3-20261118; run this probe with phase=verify and the same probe_id
[OK] second Actions run observed and released reservation phase3-probe-phase3-20261118; cross-run CAS persistence confirmed
```

### Blob ve geçmiş bütünlüğü

| Durum | `.used_topics.json` blob SHA |
|---|---|
| Önce | `163221d96e7c9cbbf35e444637d67e8d961369dc` |
| Reserved | `9e1425b241f97e0245d35b0fb083df0ba98afc24` |
| Released | `e5a987fccba23d6d37f1aed76e560cd0647e8f26` |

Üç gözlemde `used_titles` listesinin UTF-8 JSON SHA-256 değeri aynıdır:

```text
7eca291fbb7b1f462b92210afce9c0c328971d78ef98413a45a3e0644184176d
```

Böylece eski 25 başlığın içeriği ve sırası korundu; probe title kalıcı kullanılan başlıklara veya used record’lara eklenmedi. Gerçek runtime commit’leri `c421f2b` (reserve/migration) ve `a86ab5c` (release) yalnız `.used_topics.json` dosyasını değiştirdi; çalışma ağacı bu bot commit’lerine fast-forward edildi, geçmiş reset/force-push yapılmadı.

## 4. Bulunan sorunlar ve düzeltmeler

- Feature commit `c2729cc`: exact quote’tan ayrı muhafazakâr deterministik relation/subject/negation ve sayı/tarih/birim kontrolleri, kaynak HTTP/canonical kimliği, legacy-compatible v2 statüler, topic/claim/scenario fingerprint ve Contents SHA-CAS state eklendi.
- İlk CI [44276350403](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44276350403): GitHub’ın varsayılan `GITHUB_REPOSITORY` değeri testlerde remote mode seçti; token process’e verilmediğinden fail-closed doğru biçimde durdu (7 failed, 158 passed).
- `28e1d6e` denemesi [44276864442](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44276864442): reserved `GITHUB_*` değerini YAML env mapping ile boşaltmak yeterli olmadı. Son düzeltmede `env -u GITHUB_REPOSITORY -u GH_TOKEN -u GITHUB_TOKEN` doğrudan unit-test child process’ine uygulandı; üretim konfigürasyon kontrolü gevşetilmedi.
- İlk probe [44278929807](https://github.com/ahmetbysoy/youtube_shorts_automation/actions/runs/44278929807): doğrudan script çalıştırıldığında `scripts` import’u çözülemedi. Rezervasyon oluşturulmadan başarısız oldu. `python -m scripts.topic_persistence_probe` ve daily finalizer için `python -m scripts.topic_history` kullanıldı; probe’a pinned `requests` kurulumu eklendi.
- Düzeltme commit’i `0dee88e`: yukarıdaki import/environment sorunlarına **6 regresyon testi**, CI CLI smoke adımı, probe summary için shell-safe env/printf ve runtime marker/lock ignore kuralları eklendi. Sonraki yeni CI ve iki probe başarılıdır; önceki başarısız koşular başarı kanıtı diye kullanılmaz.

## 5. Güvenlik incelemesi

- Kullanıcının gösterdiği ignore edilmiş dosyadaki geçerli credential yalnız yerel process belleğinde, API başlığında ve tek komutluk Git environment başlığında kullanıldı. Değer gösterilmedi veya repo’ya eklenmedi.
- Credential dosyası ignored + untracked; credential veya onun Git auth başlığı `.git/config` içinde yok.
- Üç başarılı koşunun tüm job logları bilinen supplied credential ve maskelenmemiş GitHub/Google key pattern’leri için tarandı: **0 bulgu**. Bu bir tüm olası secret formatlarını kapsama garantisi değildir.
- Üç koşunun artifact sayısı **0**; ham loglar veya session/cookie dosyaları bu kanıt raporuna eklenmedi.
- Test commit’leri credential-pattern taramasından ve `git diff --check` kontrolünden geçti.

## 6. Kabul kararı ve açık sınırlar

**Faz 3’ün zorunlu iki koşulu da karşılandı:** doğrulanmış yeni kodda Ubuntu 26 CI başarılı; iki ayrı Actions koşusu reservation state’i gerçekten sakladı, sonraki koşuda gördü ve temizledi. TODO/README/ARCHITECTURE/AI_HANDOFF bu kanıta göre güncellenir.

Bununla birlikte:

1. Deterministik lexical/relation/numeric kontrol genel amaçlı semantik entailment veya insan doğrulaması değildir. Tanınmayan ilişkiler `partial` kalır; exact quote tek başına `verified` değildir.
2. Canlı kanıt sıralı iki run’ın Contents API kalıcılığıdır. Eşzamanlı SHA conflict/race ve failed-run release senaryolarının kapsamı otomatik mock testlerdir; gerçek Actions yarışması çalıştırılmadı.
3. Daily workflow’un gerçek orchestrator-success/failure finalize akışı ve YouTube yayın adımları çalıştırılmadı. Module CLI, store/release mantığı ve izinler yayınsız probe kapsamında doğrulandı; gerçek production uçtan uca kanıtı çıkarılmaz.
4. Yeni kodla canlı Gemini model draft’ı üretilmedi. Ayrı yerel Wikipedia HTTP erişim/kimlik kanıtı model üretim kanıtı değildir.
5. Faz 1’de kalan genel tüketici taraması/gerçek entegrasyon işleri, Faz 4 sahne-medya uygunluğu/lisansı ve sonraki timing/QC işleri otomatik kapanmaz.

**Sıradaki geliştirme:** Faz 4 — sahne başına medya adaptörleri, aday uygunluğu, lisans/atıf ve alakasız medyada fail-closed davranış. Üretim/yayın/silme testi bu raporun kapsamı değildir.
