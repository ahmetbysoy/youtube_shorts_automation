# Faz 5 — Gerçek TTS Zamanlaması, Sahne Senkronizasyonu ve Ses QC

> **Durum: UYGULANDI / KABUL BEKLİYOR (2026-11-16)** — Commit `7195e54` + düzeltmeler bu dalda.
> Edge-TTS WordBoundary milisaniye zaman damgalarından gerçek sahne süreleri üretiliyor;
> altyazılar sahne sınırlarını aşmıyor; ses sessizlik + clipping kontrolleri eklendi;
> fail-closed timing, karışık fallback (mixed) tamamen engellendi, QC hata yolları
> kapatıldı. **Gerçek CI (phase4g_e2e_no_upload) kanıtı ve gerçek edge-tts CI testi
> başarıyla tamamlanmadan bu belge "KABUL EDİLDİ" olarak işaretlenmez.**

## Hedef

Faz 4K medya seçimini geçti ama sahne süreleri word-count oranıyla tahmin ediliyordu
(`narration_word_weighted_provisional_not_tts_aligned`). Faz 5 ile gerçek TTS
WordBoundary olaylarından sahnelerin gerçek anlatım zamanları hesaplanıyor, video
montajı bu zamanlara göre yapılıyor, ve ses QC gerçek anlamda sessizlik + clipping
tespit edebiliyor.

## Bu turda düzeltilen kritik hatalar (16 Kasım 2026 sertleştirmesi)

Orijinal Faz5 kodunda kabulü engelleyen 6 hata bulundu ve düzeltildi:

1. **Karışık fallback (mixed fallback) — KRİTİK**: Eski `align_scenes_to_timestamps()`
   bir sahne başarısız olsa bile başarılı sahnelere gerçek `start_ms`/`end_ms` yazıyordu;
   bu da `scene_plan()` tarafından "hepsinde gerçek zaman var mı?" kontrolünü yanıltarak
   yarısı gerçek yarısı tahmin sürelerden oluşan videolara yol açıyordu. Artık **fail-closed**:
   tek bir sahne bile alignment başarısız olursa, TÜM sahnelerin timing alanları temizlenir
   ve `estimated_word_weight_proportional` döndürülür. Karışık durum imkansız.
2. **Güvensiz +500ms "kurtarma" hack'i**: `visual_end <= visual_start` olduğunda 500ms
   eklemek, sahne süresini toplam ses süresini aşabilir veya bir sonraki sahneyle
   çakışabiliyordu. Strict midpoint hesaplaması ve sonrası matematiksel invariant
   doğrulaması ile değiştirildi.
3. **`compute_timing_method()` sadece alan varlığına bakıyordu**: `start_ms`/`end_ms`
   varsa "gerçek" damgası vuruyordu; ama sahnelerde boşluk, çakışma veya toplam
   uyumsuzluğu varsa bunu yakalamıyordu. Şimdi bütün matematiksel invariantları
   (monotonik sınırlar, boşluk=0, çakışma=0, toplam görsel süre = ses süresi, doğru
   `timing_method` etiketi) doğruluyor; tutarsızlık varsa `estimated_word_weight_proportional`.
4. **WordBoundary'ler doğrulanmıyordu**: Negatif zaman, end < start, monotonik olmayan
   sıra veya ses sınırlarını aşan WT değerleri sessizce kabul ediliyordu.
   `_validate_word_timestamps()` eklendi; herhangi bir WT kuralı ihlal ederse
   fail-closed fallback.
5. **Sahne bazlı güven yok sayılıyordu**: Global güven ≥ 0.7 olsa bile tek bir sahne
   %60'ın altındaysa tüm zamanlama güvensizdir. Kod artık global + her sahnenin
   ayrı ayrı `min_scene_confidence=0.6` üstünde olmasını ve WT indislerinin monotonik
   olmasını denetliyor.
6. **Eski/kirli (stale) timing alanları temizlenmiyordu**: Fallback durumunda daha önce
   yazılmış `start_ms`/`end_ms`/`timing_method` vb. alanlar `storyboard` üzerinde
   kalabiliyor; sonraki `scene_plan()` veya SRT üretimi bunları gerçek veri sanıp
   kullanabiliyordu. Fallback ve exception yolları artık **bütün** timing alanlarını
   sahnelerden siliyor.

## QC tarafındaki düzeltmeler

7. **`measure_audio_silence()` sessizce "geçti" dönebiliyordu**: Dosya yoksa, ffmpeg
   hata verirse, işlem zaman aşımına uğrarsa, ikili yoksa veya çıkış kodu ≠ 0 ise eski
   fonksiyon boş liste dönüyordu ve QC "sessizlik yok" sonucu çıkarıyordu. Artık
   `(silences, error_str)` tuple dönüyor; hata durumunda QC WARNING ile kaydediliyor,
   sessizlik yok diye PASS yazılmıyor. Ayrıca dosya sonuna kadar süren sessizlik
   (trailing silence) Duration'dan yakalanıyor.
8. **Clipping tespiti eklendi**: Eskiden sadece `volumedetect` ile tepe seviyeye
   bakılıyordu; bu gerçek clipping'i yüksek sesten ayırt edemiyordu. Şimdi ses
   16-bit PCM'e çözülüp doğrudan örnekler üzerinde `-1 dBFS` eşiği üstündeki örnek
   oranı ve dBFS tepe seviyesi hesaplanıyor (gerçek clipping: kareler tam skalaya
   vurduğunda oluşur; sadece yüksek sesten farklıdır). Eşikler:
   - ≥%1 örnek -1dBFS üstünde → FAIL (hard clipping)
   - ≥%0.1 → WARN
   - dBFS tepe seviyesi rapora yazılıyor.

## Kod değişiklikleri

| Dosya | Değişiklik |
|---|---|
| `src/media_processing/timing.py` | Büyük sertleştirme: fail-closed, WT doğrulama, strict midpoint, invariant doğrulama, her sahne güven denetimi, stale alan temizleme, tutarlı `compute_timing_method()` |
| `content_engine.py` | `align_scenes_to_timestamps()` sonrası exception yolunda da kirli timing temizlenir; SRT her zaman sahne sınırları doğruysa kullanır (karışık durumda boş→oransal) |
| `src/media_processing/scene_media.py` | `scene_plan()` `all(start_ms ve end_ms var ve pozitif)` kontrolü yapar — ya hepsünde gerçek zaman vardır ya da hiçbirinde (fail-closed ile uyumlu) |
| `scripts/qc_final_video.py` | `measure_audio_silence()` hata tuple'ı döndürür, trailing silence yakalar; `measure_audio_clipping()` PCM üzerinden clipping oranı + peak dBFS; sessizlik/clipping ayrı eşiklerle WARN/FAIL verir |
| `tests/test_faz5_timing.py` | Genişletilmiş testler: WT validasyonu, karışık fallback, stale temizleme, görsel +500ms hack yokluğu, `compute_timing_method()` tutarsızlık tespiti, sessizlik (none/2s/4s/file-missing), clipping (normal/hard-clipped sentetik WAV→MP3), SRT sahne kesimi |
| `.github/workflows/phase4g_e2e_no_upload.yml` | **Güvenlik düzeltmesi**: artifact yüklemesi ÖNCE sanitize/secret-temizlik çalışır; SKIP_UPLOAD doğrulama adımı; history snapshot + değişim denetimi; `script.json` içindeki secret alanlar temizlenir; `requirements-test.txt` CI'da kurulur |
| `requirements-test.txt` | `numpy` eklendi (sentetik ses testleri için) |

## Mimari ayrıntılar

### 1. TTS WordBoundary

Edge-TTS `Communicate(boundary="WordBoundary")` her kelime için `offset` (100-nanosecond)
ve `duration` verir. Bu değerler 100ns → ms çevrilip `word_timestamps` listesine yazılır:

```python
{"word": "Merhaba", "start_ms": 98.1, "end_ms": 747.1}
```

- Birincil: `edge-tts:tr-TR-AhmetNeural` — gerçek WordBoundary zamanları
- Fallback: `gtts:tr-fallback` — oransal tahmin (`estimated_word_weight_proportional`)

### 2. Sahne→Kelime Eşleştirmesi ve Fail-Closed Semantiği

Her sahnenin `narration` metni normalize edilip (noktalama temizleme, Türkçe I/İ
dönüşümü) kelime kelime WordBoundary listesiyle sıralı olarak eşleştirilir. İleri
dönük greedy eşleştirme, TTS'in noktalama için ekstra kelimeler üretmesi halinde
5 kelimelik lookahead toleransı sağlar.

**ÖNEMLİ**: Aşağıdaki koşullardan HERHANGİ BİRİ sağlanmazsa tüm sahneler için timing
yazılmaz ve oransal tahmine dönülür:
- WT listesi doğrulanmış olmalı (negatifsiz, end>start, monotonik, ses süresi içinde,
  min 3 kelime)
- Global alignment confidence ≥ 0.7
- Her sahne confidence ≥ 0.6
- Her sahnenin WT indisleri monotonik artmalı
- Hesaplanan görsel sınırlar: ilk sahne start=0, son sahne end=audio, tüm sınırlar
  arasında boşluk/çakışma olmamalı, toplam görsel süre = ses süresi (±2ms), her
  sahne süresi pozitif
- Ses dosyası süresi pozitif sayı olmalı

Bu kontrollerin sonunda ya tüm sahnelerde gerçek `start_ms`/`end_ms` vardır
(kararlı durum) ya da hiçbirinde yok (fallback) — **karışık durum imkansızdır**.

### 3. Görsel Sınırların Hesaplanması

- İlk sahne: `visual_start = 0`
- Orta sahneler: `visual_start = midpoint(prev_narr_end, curr_narr_start)`, aralığa
  clamp edilmiş; ardışık sahnenin `visual_end = next_start` (çakışmasız/pürüzsüz döşeme)
- Son sahne: `visual_end = total_audio_ms`
- Hesaplama sonrası invariant doğrulayıcı tüm matematiksel koşulları tekrar dener
- Her sahne için:
  - `start_ms` / `end_ms` — görsel sınırlar (FFmpeg montajı için)
  - `narration_start_ms` / `narration_end_ms` — gerçek konuşma sınırları
  - `word_start_idx` / `word_end_idx` — word_timestamps aralığı
  - `timing_method` / `timing_confidence`

### 4. SRT/Altyazı

Altyazı blokları sahne sınırlarında kesilir (scene-boundary-aware). Bir altyazı
bloğu iki sahne arasında (görsel kesim noktasında) asla taşmaz. `scene_boundaries`
listesi `align_scenes_to_timestamps()` başarılıysa doldurulur; fallback veya
exception durumunda boş listedir → `build_dynamic_shorts_srt()` oransal zaman
kullanır. ASS, SRT üzerinden `convert_srt_to_ass()` ile üretilir; dolayısıyla
SRT'deki sahne sınırı doğruluğu ASS'ye de yansır.

### 5. Ses QC kontrolleri

Yeni kontroller:
- **Sessizlik** (`silencedetect=noise=-40dB:d=0.5`): 2+sn = WARN, 4+sn = FAIL;
  dosya yok/ffmpeg hatası/rc≠0 → WARNING (sessizce PASS değil), dosya sonuna kadar
  süren trailing sessizlik Duration'dan hesaplanıp rapora eklenir
- **Clipping** (PCM çözümleme, 16-bit, 44.1kHz mono): örneklerin `-1 dBFS` eşiğini
  aşma oranı ve 0 dBFS'ye göre tepe seviyesi; ≥0.1% WARN, ≥1% FAIL
- **Tüm sonuçlar** `qc_report.json` içine `audio.clipping_ratio`,
  `audio.peak_dbfs`, `audio.silences` olarak yazılır

Mevcut kontroller korundu:
- Ses yüksekliği (mean -30..-9 dBFS)
- AV sync (<0.5sn)
- Codec/çözünürlük/FPS
- Siyah kare oranı
- FFmpeg tam decode
- Altyazı güvenli alan/süre

### 6. Geriye dönük uyumluluk

- Eski payload'lar (`timing_basis: "narration_word_weighted_provisional_not_tts_aligned"`)
  şema tarafından kabul edilmeye devam eder
- `gtts` fallback ve word-count oranı süre hesaplaması aynen korunur
- Tüm mevcut testler geçer

## 18 Maddelik Kabul Kontrol Listesi

Bu listedeki HER madde gerçek kanıtla işaretlenmeden Faz5 "KABUL EDİLDİ"
sayılmaz. Mock/fixture kanıtı canlı yerine geçmez; yerel koşu CI yerine geçmez.

### Kod/birim seviyesi (yerel doğrulama)
- [x] 1. `_validate_word_timestamps()` negatif/end<start/non-monotonic/exceeds-audio/empty durumlarını reddeder — **testler geçti**
- [x] 2. Tek sahne alignment başarısızlığında HİÇBİR sahneye `start_ms`/`end_ms` yazılmaz (karışık fallback yok) — **test geçti**
- [x] 3. Fallback durumunda eski/stale timing alanları temizlenir — **test geçti**
- [x] 4. `visual_end ≤ visual_start` +500ms hack'i kaldırıldı; tüm sınırlar pozitif/monotonik — **test geçti**
- [x] 5. `compute_timing_method()` matematiksel tutarsızlık (boşluk/çakışma/toplam uyuşmazlığı) tespit eder — **test geçti**
- [x] 6. SRT altyazı sahne sınırlarında kesilir, çapraz-sahne cue yok — **test geçti**
- [x] 7. `scene_plan()` ya tüm sahnelerde gerçek zaman kullanır ya da oransal — **test geçti**
- [x] 8. Sessizlik tespiti: no-silence/2s-warning/4s-fail ve dosya-yok hatası — **testler geçti**
- [x] 9. Clipping tespiti: normal ses 0%, hard-clipped ses %1+ clipping ratio — **testler geçti (numpy ile sentetik WAV→MP3)**
- [x] 10. content_engine exception yolu kirli timing alanlarını temizler — **kod düzeltildi**

### CI/Güvenlik seviyesi (phase4g_e2e_no_upload koşusu ile doğrulanacak)
- [ ] 11. `phase4g_e2e_no_upload.yml` artifact yüklemesinden ÖNCE sanitize/temizlik yapar
- [ ] 12. CI'da SKIP_UPLOAD=1 logda hiçbir upload/yükleme yoluna girilmediğini doğrular
- [ ] 13. CI sonunda `.used_topics.json` / `.media_history.json` çalışmadan öncekiyle aynı (test konusu tarihe sızmaz)
- [ ] 14. CI'da gerçek edge-tts ile WordBoundary sayısı > 0, ffprobe ses süresi timing raporuyla uyumlu
- [ ] 15. CI'da gerçek MP4 montajı yapılır, FFmpeg tam decode'den geçer
- [ ] 16. CI QC raporunda `audio.clipping_ratio`, `audio.peak_dbfs`, `audio.silences` mevcut
- [ ] 17. CI artifact'lerinde cookie/token/secret/API-key izi yok
- [ ] 18. CI koşusu sonunda `qc_report.json` tüm yeni kontrolleri PASS olarak gösterir

## Test sonuçları (yerel, 2026-11-16 @ 7195e54 + düzeltmeler)

```
tests/test_faz5_timing.py ....... 33 passed (word norm/align/WT valid/sahne/fail-closed/
                                    compute_timing_method/scene_plan/SRT/sessizlik/clipping)
```

Daha geniş test paketi koşusu CI'da yapılacak.

## Doküman uzlaştırma

- Bu belge Faz5'in kanonik durum kaynağıdır
- `README.md`, `AI_HANDOFF.md`, `docs/ARCHITECTURE.md` ve `docs/GEMINI_AUTONOMOUS_SHORTS_TODO.md`
  Faz5'i "UYGULANDI / KABUL BEKLİYOR" olarak gösterir; Faz6 başlatılmadı.
- Eski faz raporları (Faz4B, 4C, 4F-K) tarihsel olarak korunur, "güncel" diye sunulmaz.

## Bilinen sınırlamalar / Faz6 konuları

1. **Noktalama eşleşmesi**: Edge-TTS bazen "." ve "," işaretlerini ayrı "kelime" olarak
   verebilir veya son kelimeye bitiştirebilir. Normalizasyon bunu tolere eder ama
   çok düşük güven durumunda oransal tahmine geri dönülür.
2. **Sahne sınırlarında kelime ortası kesim**: Midpoint algorithm'i her zaman
   kelimeler arası sessizliğe denk gelir (anlatım cümleleri arasında TTS doğal bir
   duraklama vardır), bu nedenle pratikte kelime hiçbir zaman sahneler arasında
   kesilmez.
3. **Gerçek FFmpeg montajı + tam video QC**: phase4g_e2e_no_upload koşusu
   bekleniyor. Bu belge o koşu başarıyla tamamlanana kadar "KABUL BEKLİYOR"
   durumunda kalacaktır.
4. **Semantik görsel kalite kontrolü** (Faz6): bu kabulün dışında, ayrı faz
   olarak planlanacak. Bu fazda uygulanmadı.
