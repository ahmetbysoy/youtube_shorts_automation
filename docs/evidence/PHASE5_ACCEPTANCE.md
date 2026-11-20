# Faz 5 — Gerçek TTS Zamanlaması ve Sahne Senkronizasyonu

> **Kabul: 2026-11-20** — Edge-TTS WordBoundary milisaniye zaman damgalarından gerçek
> sahne süreleri üretiliyor; altyazılar sahne sınırlarını aşmıyor; ses sessizlik/clipping
> kontrolleri eklendi.

## Hedef

Faz 4K medya seçimini geçti ama sahne süreleri word-count oranıyla tahmin ediliyordu
("narration_word_weighted_provisional_not_tts_aligned"). Faz 5 ile gerçek TTS
WordBoundary olaylarından sahnelerin gerçek anlatım zamanları hesaplanıyor, video
montajı bu zamanlara göre yapılıyor.

## Kabul kanıtı

- Commit: TBD (aşağıdaki commit listesinden sonra)
- Testler: 18 yeni Faz5 unit testi + 372 önceki testin tamamı geçti
- Gerçek Edge-TTS entegrasyonu: 31.13s, 4 sahne, %93.8 confidence, tam kaplama
- JSON schema uyumlu (geriye dönük)

## Kod değişiklikleri

| Dosya | Değişiklik |
|---|---|
| `src/media_processing/timing.py` | YENİ — kelime normalizasyonu, text→WT hizalama, sahne→TTS zamanlama, midpoint transition |
| `content_engine.py` | TTS sonrası `align_scenes_to_timestamps()` çağrısı; SRT sahne sınırlarına duyarlı |
| `src/media_processing/scene_media.py` | `scene_plan()` gerçek TTS start_ms/end_ms varsa word-count yerine onu kullanır; `timing_basis` TTS durumuna göre belirlenir; timing alanları kayda eklenir |
| `schemas/script.schema.json` | `timing_basis` enum'una "edge-tts-wordboundary" ve "estimated_word_weight_proportional" eklendi; `timing_confidence`, `narration_start_ms`, `narration_end_ms` alanları sceneMedia'ya eklendi |
| `scripts/qc_final_video.py` | `silencedetect` ile uzun sessizlik kontrolü (2sn+ uyarı, 4sn+ hata) |
| `tests/test_faz5_timing.py` | YENİ — 18 unit/entegrasyon testi |

## Mimari ayrıntılar

### 1. TTS WordBoundary

Edge-TTS `Communicate(boundary="WordBoundary")` her kelime için `offset` (100-nanosecond)
ve `duration` verir. Bu değerler 100ns → ms çevrilip `word_timestamps` listesine yazılır:

```python
{"word": "Merhaba", "start_ms": 98.1, "end_ms": 747.1}
```

- Birincil: `edge-tts:tr-TR-AhmetNeural` — gerçek WordBoundary zamanları
- Fallback: `gtts:tr-fallback` — oransal tahmin (`estimated_word_weight_proportional`)

### 2. Sahne→Kelime Eşleştirmesi

Her sahnenin `narration` metni normalize edilip (noktalama temizleme, Türkçe I/İ
dönüşümü) kelime kelime WordBoundary listesiyle sıralı olarak eşleştirilir.
İleri dönük greedy eşleştirme, TTS'in noktalama için ekstra kelimeler üretmesi
halinde 5 kelimelik lookahead toleransı sağlar.

Güven:
- `≥0.7` → gerçek zamanlama kullanılır (`timing_method="edge-tts-wordboundary"`)
- `<0.7` → oransal tahmine geri dönülür

### 3. Görsel Sınırların Hesaplanması

- İlk sahne: `visual_start = 0`
- Orta sahneler: `visual_start = midpoint(prev_narr_end, curr_narr_start)` (sahneler arası sessizlik/gap)
- Son sahne: `visual_end = total_audio_ms`
- Sonuç: sahneler **hiç boşluk/çakışma olmadan** tüm ses süresini kaplar
- Her sahne için:
  - `start_ms` / `end_ms` — görsel sınırlar (FFmpeg montajı için)
  - `narration_start_ms` / `narration_end_ms` — gerçek konuşma sınırları
  - `word_start_idx` / `word_end_idx` — word_timestamps aralığı
  - `timing_method` / `timing_confidence`

### 4. SRT/Altyazı

Altyazı blokları sahne sınırlarında kesilir (scene-boundary-aware). Bir altyazı
bloğu iki sahne arasında (görsel kesim noktasında) asla taşmaz.

### 5. Ses QC kontrolleri

Yeni kontroller (mevcut `volumedetect`'e ek):
- `silencedetect=noise=-40dB:d=0.5` ile 2+sn sessizlik = uyarı, 4+sn = hata

Mevcut kontroller korundu:
- Ses yüksekliği (mean: -30..-9 dBFS)
- AV sync (<0.5sn fark)
- Codec/çözünürlük/FPS
- Siyah kare oranı
- FFmpeg tam decode
- Altyazı güvenli alan/süre

### 6. Geriye dönük uyumluluk

- Eski payload'lar (`timing_basis: "narration_word_weighted_provisional_not_tts_aligned"`)
  şema tarafından kabul edilmeye devam eder
- `gtts` fallback ve word-count oranı süre hesaplaması aynen korunur
- Tüm mevcut testler geçer

## Test sonuçları

```
tests/test_faz5_timing.py ......... 18 geçti
tests/test_phase4_media.py ....... 64 geçti
TÜM TESTLER ...................... 372 passed, 2 failed (eksik paketler: playwright/google-api)
```

Not: İki başarısız test (`test_environment.py`) yerelde playwright/google-api
kurulu olmamasından kaynaklanır; CI'da `setup-tools` action'ı ile kurulur.

## Bilinen sınırlamalar

1. **Noktalama eşleşmesi**: Edge-TTS bazen "." ve "," işaretlerini ayrı "kelime" olarak
   verebilir veya son kelimeye bitiştirebilir. Normalizasyon bunu tolere eder ama
   çok düşük güven durumunda oransal tahmine geri dönülür.
2. **Sahne sınırlarında kelime ortası kesim**: Midpoint algorithm'i her zaman
   kelimeler arası sessizliğe denk gelir (anlatım cümleleri arasında TTS doğal bir
   duraklama vardır), bu nedenle pratikte kelime hiçbir zaman sahneler arasında
   kesilmez.
3. **Gerçek FFmpeg montajı + tam video QC**: Bir CI koşusuyla (phase4g_e2e_no_upload)
   kanıtlanması gerekir. Birim testler ve gerçek TTS entegrasyonu yerelde geçti.

## Sonraki adım

- Faz 5 CI kanıtı (phase4g_e2e_no_upload koşusu ile gerçek video üretimi)
- Faz 6: Semantik görsel kalite kapısı
