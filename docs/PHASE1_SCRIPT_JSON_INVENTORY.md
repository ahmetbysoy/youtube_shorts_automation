# Faz 1 — script.json Sözleşme Envanteri

> Tarih: 2026-11-17  
> Durum: Envanter tamamlandı; yeni şema henüz uygulanmadı. Bu belge yalnız mevcut kod ve örnek dosyalardan doğrulanan yapıyı kaydeder.

## 1. Üretici

Tek doğrulanmış ana üretici `content_engine.py` içindeki `run_content_pipeline()` fonksiyonudur. Senaryoyu `generate_scenario()` ile alır, TTS seslendirmesini üretir, kelime zaman damgalarını toplar, `script.txt` ve `voiceover.srt` dosyalarını yazar, ardından `script.json` payload'ını oluşturur.

Üretim payload'ında şu alanlar bulunur:

| Alan | Mevcut tür / anlam |
|---|---|
| `generated_at` | UTC ISO-8601 tarih/saat metni |
| `llm_provider` | Senaryo sağlayıcısı / fallback etiketi |
| `tts_engine` | TTS motoru ve ses adı |
| `topic` | Konu/kategori metni |
| `title` | YouTube başlığı |
| `description` | Açıklama metni |
| `affiliate_link` | Affiliate URL veya boş/null değer olasılığı; gerçek senaryo üretiminde doğrulanmalı |
| `affiliate_cta` | Affiliate çağrı metni veya boş/null değer olasılığı |
| `cta_line` | Kapanış çağrı metni |
| `thumbnail_prompt` | Eski kapak prompt metni |
| `viral_hashtags` | Etiket dizisi |
| `hook` | Açılış kancası |
| `script_text` | Tam Türkçe seslendirme metni |
| `word_count` | Kelime sayısı |
| `audio_file` | Ses dosyası yolu |
| `srt_file` | Altyazı dosyası yolu |
| `audio_duration_sec` | Ses süresi, saniye |
| `visual_keywords` | Eski medya motorunun kullandığı arama terimleri dizisi |
| `word_timestamps` | Kelime bazlı zaman damgası nesneleri dizisi |

Her `word_timestamps[]` nesnesinde `word` metin, `start_ms` ve `end_ms` sayısal milisaniye değerleridir. Bu zamanlar gerçek Edge-TTS WordBoundary çıktısından gelebilir; gTTS yedeğinde süreye göre yaklaşık dağıtılır. Dolayısıyla yeni şemada zaman kaynağı/kalitesi ayrıca belirtilebilir; mevcut alanların anlamı değiştirilmemelidir.

## 2. Doğrulanmış tüketiciler

1. `src/media_processing/media_processor.py` dosyası `script.json` okur. Şu an ana medya sözleşmesi `visual_keywords` alanıdır; alan yoksa genel varsayılan anahtar kelimelere düşer. Wikimedia lisans atıfları eksikse `description` alanını güncelleyip JSON dosyasını tekrar yazar.
2. `scripts/embed_cover_frame.py` dosyası `script.json` okur ve `title` ile `topic` alanlarını kullanır. Kod açıklaması `thumbnail_prompt` alanının artık varsayılan kapak promptunda kullanılmadığını açıkça belirtir.
3. `tests/test_full_pipeline_fallback.py` uçtan uca üretim testinde `script.json` dosyasının oluşmasını ve temel alanların varlığını kontrol eder. Henüz JSON Schema doğrulaması yoktur.

Bu envanterde doğrulanmamış olası tüketiciler tamamlanmış sayılmaz. Kod araması ve çalışma akışı incelemesi Faz 1'in devamında genişletilecektir.

## 3. Örnek dosya uyumsuzluğu

`samples/script.json` mevcut bir örnektir; üreticinin güncel payload'ıyla birebir aynı değildir. Örnekte `affiliate_link`, `affiliate_cta` ve `cta_line` alanları bulunmaz. Örnek dosyanın `generated_at` tarihi 2026-11-02'dir. Bu nedenle örnek, tek başına güncel ve zorunlu alanların kesin kaynağı kabul edilmemelidir.

## 4. Storyboard durumu

Mevcut üretici payload'ında `storyboard`, `schema_version`, `generation_id`, `fact_check`, kaynak kayıtları veya sahne bazlı medya alanları yoktur. Medya işlemcisi tek bir `visual_keywords` dizisi tüketir. Bu yüzden storyboard yeni şemada geriye uyumlu ve ayrı bir alan olarak eklenmeli; eski `visual_keywords` tüketicisi geçiş süresince çalışmaya devam etmelidir.

## 5. Faz 1 tasarım kuralları

- Önce mevcut payload ve örnekler testlerle sabitlenmeli; ardından versiyonlu JSON Schema eklenmeli.
- `schema_version` olmayan eski JSON geçiş dönemi sürümü olarak tanınmalı; sessizce yanlış alanlara dönüştürülmemeli.
- Yeni `storyboard`, `fact_check`, `sources` ve `generation_id` alanları eklenirken eski tüketiciler kırılmamalı.
- `visual_keywords` mevcut medya işlemcisi tamamen taşınana kadar korunmalı.
- `description` alanının Wikimedia atıf güncellemesi nedeniyle JSON tüketicisi salt-okunur varsayılmamalı.
- Hatalı JSON, yanlış tip, eksik zorunlu alan, negatif/ters zaman damgası ve geçersiz URL gibi durumlar test edilmelidir.
- Faz 1 yalnız JSON sözleşmesi ve test altyapısını kapsar; üretim workflow'u, yayın davranışı, cookie'ler ve secret'lar değiştirilmez.

## 6. Kanıt kaynakları

- `content_engine.py` — `run_content_pipeline()` payload üretimi.
- `samples/script.json` — 2026-11-02 tarihli gerçek örnek.
- `src/media_processing/media_processor.py` — `visual_keywords` tüketimi ve açıklama güncellemesi.
- `scripts/embed_cover_frame.py` — `title` / `topic` tüketimi.
- `tests/test_full_pipeline_fallback.py` — mevcut çıktı sözleşmesi için test.
- `tests/test_content_engine_fallback.py` — senaryo alanları için test.
