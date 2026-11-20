#!/usr/bin/env python3
"""
Faz 5 — Gercek TTS word-timing'den turetilmis sahne zamanlamasi.

Bu modul, edge-tts WordBoundary olaylarindan elde edilen kelime zaman damgalari ile
storyboard sahnelerinin anlatim metnini eslestirerek SAHNE BASLANGIC/BITIS zamanlarini
gercek ses uzerinden hesaplar.

Mimari:
    - align_words_to_text: TTS ham ses metni ve WordBoundary listesini normalize edip
      karsilikli indeks eslestirmesi yapar.
    - align_scenes_to_timestamps: Her scene narration parcasinin tam olarak hangi
      word_timestamp araligina denk geldigini bulur; start_ms/end_ms degerlerini yazar.
    - Sahne sureleri artik kelime-sayisi tahmini DEGIL, gercek TTS zamanlaridir.
    - Guven modu: eslestirme guveni duserse (or. gTTS fallback, noktalama uyumsuzlugu)
      timing_method='estimated' veya 'partial' olarak isaretler.
"""
from __future__ import annotations

import re
from typing import Any

# Noktalama ve Türkçe karakter normalizasyonu için sabitler
_PUNCT_RE = re.compile(r"[.,!?;:\"'()\[\]{}…—–\-\\/]+")
_WHITESPACE_RE = re.compile(r"\s+")
# Türkçe harf dönüşümü (TTS bazen ı/İ/i, ş/ṣ vb. farklı dönebilir)
_CHAR_FOLD = str.maketrans({
    "İ": "i", "I": "ı",  # Türkçe I durumu — küçük ı, büyük İ (asagida lowercase sonrasi duzeltilir)
})


def _normalize_word(word: str) -> str:
    """Kelimeleri karşılaştırma için normalize et: noktalama temizle, küçük harf, Türkçe uyumu."""
    w = _PUNCT_RE.sub(" ", str(word))
    # Tüm boşlukları tek boşluğa sıkıştır
    w = _WHITESPACE_RE.sub(" ", w).strip()
    if not w:
        return ""
    # Türkçe lower: I → ı, İ → i (Python default lower Türkçe için yanlıştır)
    out_chars = []
    for ch in w:
        if ch == "I":
            out_chars.append("ı")
        elif ch == "İ":
            out_chars.append("i")
        else:
            out_chars.append(ch.lower())
    return "".join(out_chars)


def _text_to_norm_words(text: str) -> list[str]:
    """Metni normalize edilmiş kelime listesine çevir (noktalama ayrılmış)."""
    # Noktalama işaretlerini kelimelerden ayır ama kelime sırasını koru
    cleaned = _PUNCT_RE.sub(" ", str(text or ""))
    raw_words = _WHITESPACE_RE.split(cleaned.strip())
    return [_normalize_word(w) for w in raw_words if _normalize_word(w)]


def align_words_to_text(
    script_text: str,
    word_timestamps: list[dict[str, Any]],
) -> dict[str, Any]:
    """TTS script metnini WordBoundary zaman damgalariyla eslestir.

    Donus:
        {
            'mapped': [(norm_word, wt_index_or_None), ...]  # script kelime sirasiyla
            'mapping_confidence': 0.0-1.0,                  # eslesen oran
            'first_wt_idx': int,
            'last_wt_idx': int,
            'unmapped_script_words': [norm_word, ...],
            'unmatched_wt_words': [norm_word, ...],
        }
    """
    if not script_text or not word_timestamps:
        return {
            "mapped": [],
            "mapping_confidence": 0.0,
            "first_wt_idx": -1,
            "last_wt_idx": -1,
            "unmapped_script_words": _text_to_norm_words(script_text),
            "unmatched_wt_words": [_normalize_word(wt.get("word", "")) for wt in word_timestamps],
        }

    script_words = _text_to_norm_words(script_text)
    wt_words = [_normalize_word(wt.get("word", "")) for wt in word_timestamps]

    # Greedy sequential alignment: iki liste uzerinde ileri dogru eslestir.
    # TTS bazen bazi kelimeleri birlestirir veya noktalamayi ayri kelime olarak
    # verebilir (ornegin "dunya," → "dunya" + ","). Iki nokta arasinda en yakin
    # kelimeyi eslestirerek toleransli ilerliyoruz.
    mapped: list[tuple[str, int | None]] = []
    wt_pos = 0
    n_wt = len(wt_words)
    hits = 0

    for sw in script_words:
        if not sw:
            continue
        # wt_pos'tan itibaren en fazla 3 kelime ileride ara (TTS'in fazladan
        # noktalama/sessizlik kelimeleri uretmesi durumunda)
        best_idx = None
        for ahead in range(0, 4):
            cand = wt_pos + ahead
            if cand >= n_wt:
                break
            if wt_words[cand] == sw:
                best_idx = cand
                break
            # Tolerance: sw, wt_words[cand]'un icinde veya tam tersi
            if len(sw) >= 4 and (sw in wt_words[cand] or wt_words[cand] in sw):
                best_idx = cand
                break
        if best_idx is not None:
            mapped.append((sw, best_idx))
            wt_pos = best_idx + 1
            hits += 1
        else:
            # Eslesme bulunamadi: wt_pos'u ilerlet ama script kelimesini None olarak isaretle
            mapped.append((sw, None))

    confidence = hits / max(1, len(script_words))

    matched_wt_idxs = [i for _, i in mapped if i is not None]
    first_wt_idx = matched_wt_idxs[0] if matched_wt_idxs else -1
    last_wt_idx = matched_wt_idxs[-1] if matched_wt_idxs else -1
    used_wt = set(matched_wt_idxs)
    unmatched_wt = [wt_words[i] for i in range(n_wt) if i not in used_wt]
    unmapped_script = [w for w, i in mapped if i is None]

    return {
        "mapped": mapped,
        "mapping_confidence": round(confidence, 3),
        "first_wt_idx": first_wt_idx,
        "last_wt_idx": last_wt_idx,
        "unmapped_script_words": unmapped_script,
        "unmatched_wt_words": unmatched_wt,
    }


def align_scenes_to_timestamps(
    script: dict[str, Any],
    *,
    min_confidence_for_real_timing: float = 0.7,
) -> dict[str, Any]:
    """Storyboard sahnelerini TTS WordBoundary zaman damgalarina eslestir.

    Her sahneye sozcuk-bazli gercek `start_ms` ve `end_ms` degerlerini yazar.
    Donus script'i degistirir ve ayrica bir alignment raporu dondurur.

    Islem sirasi:
        1. Butun script_text ve word_timestamps eslestirmesini yap (referans).
        2. Her sahne narration'ini ayrica eslestirip kuresel wt indekslerini bul.
        3. narration_start_ms / narration_end_ms: ilk kelime baslangici, son kelime bitisi.
        4. visual_start_ms / visual_end_ms: sahne gorsellerinin baslayacagi/bitecegi
           zaman — narration_start_ms'dan once 250ms (onceki sahne ile crossfade yer tutar)
           ve narration_end_ms'dan sonra bir sonraki sahnenin ilk kelimesine kadar.
        5. Geriye-donuk uyumluluk: eski word-count weight duration korunur ama
           timing_method='tts_wordboundary' veya 'estimated' olarak etiketlenir.

    Rapor:
        {
            'timing_method': 'edge-tts-wordboundary' | 'gtts-proportional' | 'estimated-fallback',
            'timing_confidence': 0.0-1.0,
            'scenes': [{'scene_id':..,'start_ms':..,'end_ms':..,'confidence':..}, ...],
            'gaps_ms': [...],          # sahneler arasi bosluklar
            'total_video_ms': ...,
        }
    """
    board = script.get("storyboard")
    word_timestamps = script.get("word_timestamps") or []
    tts_engine = str(script.get("tts_engine", ""))
    total_audio_ms = float(script.get("audio_duration_sec", 0)) * 1000.0

    # Edge-TTS ve yeterli zaman damgasi varsa gercek zamanlamayi dene
    has_real_edge_tts = tts_engine.startswith("edge-tts") and len(word_timestamps) >= 3

    scene_reports: list[dict[str, Any]] = []

    if not has_real_edge_tts or not isinstance(board, list) or not board:
        # Gercek TTS yok: mevcut word-weight tahmini korunur.
        return _build_fallback_timing_report(script, reason="no_wordboundary_timestamps" if not has_real_edge_tts else "no_storyboard")

    # 1. Global script_text → wt eslestirmesi (debug/rapor icin)
    global_align = align_words_to_text(script.get("script_text", ""), word_timestamps)
    global_conf = global_align["mapping_confidence"]

    if global_conf < min_confidence_for_real_timing:
        return _build_fallback_timing_report(script, reason=f"global_alignment_confidence_too_low({global_conf:.2f})")

    # 2. Her sahneyi sirayla eslestir (scenes anlatim sirasina gore)
    # narration'leri kelime kelime wt ile eslestirirken wt_pos'u her scene'de kaldigi
    # yerden devam ettir — bu cumlelerin birbirine karismasini onler.
    wt_pos = 0
    n_wt = len(word_timestamps)
    # Once butun sahnelerin narration zamanlarini hesapla, sonra visual bound'ları
    # narration'lar arasinda GAP/OLUSMAYACAK sekilde yerlestir.
    scene_data: list[dict[str, Any]] = []
    for idx, scene in enumerate(board):
        narration = str(scene.get("narration", "")).strip()
        scene_id = int(scene.get("scene_id", idx + 1))
        narration_words = _text_to_norm_words(narration)
        if not narration_words:
            scene_data.append({
                "scene_id": scene_id, "scene": scene, "narration_start_ms": 0.0,
                "narration_end_ms": 0.0, "first_wt": None, "last_wt": None,
                "scene_conf": 0.0, "status": "empty_narration",
            })
            wt_pos = min(n_wt, wt_pos + 1)
            continue
        hits = 0
        first_wt = None
        last_wt = None
        local_wt_pos = wt_pos
        for nw in narration_words:
            best_idx = None
            for ahead in range(0, 6):
                cand = local_wt_pos + ahead
                if cand >= n_wt:
                    break
                cand_word = _normalize_word(word_timestamps[cand].get("word", ""))
                if cand_word == nw:
                    best_idx = cand
                    break
                if len(nw) >= 4 and (nw in cand_word or cand_word in nw):
                    best_idx = cand
                    break
            if best_idx is not None:
                if first_wt is None:
                    first_wt = best_idx
                last_wt = best_idx
                local_wt_pos = best_idx + 1
                hits += 1
        scene_conf = hits / max(1, len(narration_words))
        if first_wt is None or last_wt is None or scene_conf < 0.5:
            scene_data.append({
                "scene_id": scene_id, "scene": scene, "narration_start_ms": 0.0,
                "narration_end_ms": 0.0, "first_wt": None, "last_wt": None,
                "scene_conf": scene_conf, "status": "alignment_failed",
            })
            wt_pos = min(n_wt, wt_pos + len(narration_words))
            continue
        scene_data.append({
            "scene_id": scene_id, "scene": scene,
            "narration_start_ms": float(word_timestamps[first_wt]["start_ms"]),
            "narration_end_ms": float(word_timestamps[last_wt]["end_ms"]),
            "first_wt": first_wt, "last_wt": last_wt,
            "scene_conf": scene_conf, "status": "aligned",
        })
        wt_pos = local_wt_pos

    # Simdi visual bound'lari hesapla:
    #  - Ilk sahne visual=0'dan baslar (TTS lead-in'i yakalamak icin)
    #  - Orta sahneler: visual_start = onceki sahnenin narration_end'i ile bu sahnenin
    #    narration_start'i arasindaki orta nokta (smooth transition, cakisma yok).
    #  - Son sahne: visual_end = audio_duration_ms
    # Bu strateji ile video tam olarak audio_duration_ms kadar olur ve hicbir anlatim
    # parcasi gorsel kapsama disinda kalmaz.
    scene_reports: list[dict[str, Any]] = []
    for i, sd in enumerate(scene_data):
        scene = sd["scene"]
        scene_id = sd["scene_id"]
        if sd["status"] != "aligned":
            scene_reports.append({
                "scene_id": scene_id, "narration_start_ms": 0, "narration_end_ms": 0,
                "visual_start_ms": 0, "visual_end_ms": 0,
                "word_start_idx": -1, "word_end_idx": -1,
                "scene_confidence": sd["scene_conf"], "status": sd["status"],
            })
            continue
        narr_start = sd["narration_start_ms"]
        narr_end = sd["narration_end_ms"]
        first_wt = sd["first_wt"]
        last_wt = sd["last_wt"]

        if i == 0:
            visual_start = 0.0
        else:
            # Onceki sahneden gelen son aligned scene
            prev_aligned = None
            for prev in reversed(scene_data[:i]):
                if prev["status"] == "aligned":
                    prev_aligned = prev
                    break
            if prev_aligned is not None:
                # Orta nokta: onceki narration_end ile bu narration_start arasi
                mid = (prev_aligned["narration_end_ms"] + narr_start) / 2.0
                visual_start = max(0.0, mid)
            else:
                visual_start = max(0.0, narr_start - 100.0)

        if i == len(scene_data) - 1:
            visual_end = total_audio_ms
        else:
            # Sonraki aligned scene'in narration_start'i ile bunun narr_end arasi orta
            next_aligned = None
            for nxt in scene_data[i+1:]:
                if nxt["status"] == "aligned":
                    next_aligned = nxt
                    break
            if next_aligned is not None:
                mid = (narr_end + next_aligned["narration_start_ms"]) / 2.0
                visual_end = min(total_audio_ms, mid)
            else:
                visual_end = min(total_audio_ms, narr_end + 200.0)

        # Ensure no overlap / zero-length
        if visual_end <= visual_start:
            visual_end = visual_start + 500.0

        # Scene nesnesine yaz
        scene["start_ms"] = round(visual_start, 1)
        scene["end_ms"] = round(visual_end, 1)
        scene["narration_start_ms"] = round(narr_start, 1)
        scene["narration_end_ms"] = round(narr_end, 1)
        scene["word_start_idx"] = first_wt
        scene["word_end_idx"] = last_wt
        scene["timing_confidence"] = round(sd["scene_conf"], 3)
        scene["timing_method"] = "edge-tts-wordboundary"
        scene["duration_sec"] = round((visual_end - visual_start) / 1000.0, 3)

        scene_reports.append({
            "scene_id": scene_id,
            "narration_start_ms": round(narr_start, 1),
            "narration_end_ms": round(narr_end, 1),
            "visual_start_ms": round(visual_start, 1),
            "visual_end_ms": round(visual_end, 1),
            "word_start_idx": first_wt,
            "word_end_idx": last_wt,
            "scene_confidence": round(sd["scene_conf"], 3),
            "status": "aligned",
        })

    # 3. Toplam visual sureyi rapora ekle
    total_visual_ms = sum(s["visual_end_ms"] - s["visual_start_ms"]
                          for s in scene_reports if s.get("status") == "aligned")

    # 3. Rapor
    return {
        "timing_method": "edge-tts-wordboundary",
        "timing_confidence": global_conf,
        "global_alignment_confidence": global_conf,
        "scenes": scene_reports,
        "total_audio_ms": round(total_audio_ms, 1),
        "total_visual_ms": round(total_visual_ms, 1),
        "note": "scene.start_ms/end_ms visual bounds; scene.narration_start_ms/end_ms actual speech bounds",
    }


def _build_fallback_timing_report(script: dict, *, reason: str) -> dict[str, Any]:
    """TTS zamani yoksa veya guven dusukse, mevcut word-weight tahmini korunur."""
    return {
        "timing_method": "estimated_word_weight_proportional",
        "timing_confidence": 0.0,
        "global_alignment_confidence": 0.0,
        "scenes": [],
        "total_audio_ms": round(float(script.get("audio_duration_sec", 0)) * 1000.0, 1),
        "total_visual_ms": 0.0,
        "note": f"Fallback proportional timing used: {reason}",
    }


def compute_timing_method(script: dict) -> str:
    """Script uzerinden timing_method etiketini belirle."""
    tts = str(script.get("tts_engine", ""))
    wt = script.get("word_timestamps") or []
    board = script.get("storyboard") or []
    if tts.startswith("edge-tts") and len(wt) >= 3 and board:
        # Sahnelerde start_ms/end_ms varsa gercek zamanlama
        has_real = all("start_ms" in s and "end_ms" in s for s in board if isinstance(s, dict))
        if has_real:
            return "edge-tts-wordboundary"
    return "estimated_word_weight_proportional"
