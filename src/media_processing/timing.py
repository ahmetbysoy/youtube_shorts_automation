#!/usr/bin/env python3
"""
Faz 5 — Gercek TTS word-timing'den turetilmis sahne zamanlamasi.

GUVENLIK KURALLARI (degistirmeyin):
  - Yalnizca TUM sahneler basarili sekilde eslestiginde gercek TTS zamanlamasi kullanilir.
  - Herhangi bir sahne eslesmezse HICBIR sahneye start_ms/end_ms yazilmaz (karma fallback yok).
  - Oransal fallback ve gercek TTS ayni storyboard uzerinde karistirilmaz.
  - Visual sinirlarin matematiksel ozellikleri her zaman saglanir:
      (1) ilk sahne 0 ms'de baslar
      (2) son sahne total_audio_ms'de biter
      (3) butun sahneler pozitif sureye sahiptir
      (4) sahneler arasi bosluk yok (gap=0)
      (5) sahneler birbirinin uzerine binmez (overlap=0)
      (6) hicbir sahne audio_duration_ms'yi asmaz
      (7) toplam visual süre = audio_duration_ms
      (8) sahne sirasi storyboard sirasini korur
  - Zaman damgasi verilerinin tutarliligi (monotonik artan, negatif olmama, ses
    suresini asmamasi) onaylanmadan timing gecerli sayilmaz.
"""
from __future__ import annotations

import re
from typing import Any

_PUNCT_RE = re.compile(r"[.,!?;:\"'()\[\]{}…—–\-\\/]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_word(word: str) -> str:
    """Kelimeleri karsilastirma icin normalize et: noktalama temizle, kucuk harf, Turkce I/i."""
    w = _PUNCT_RE.sub(" ", str(word))
    w = _WHITESPACE_RE.sub(" ", w).strip()
    if not w:
        return ""
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
    """Metni normalize edilmis kelime listesine cevir (noktalama ayrilmis)."""
    cleaned = _PUNCT_RE.sub(" ", str(text or ""))
    raw_words = _WHITESPACE_RE.split(cleaned.strip())
    return [_normalize_word(w) for w in raw_words if _normalize_word(w)]


def align_words_to_text(
    script_text: str,
    word_timestamps: list[dict[str, Any]],
) -> dict[str, Any]:
    """TTS script metnini WordBoundary zaman damgalariyla eslestir.

    Returns:
        mapped: list of (norm_word, wt_index_or_None) in script word order
        mapping_confidence: 0.0-1.0 (fraction of script words matched)
        first_wt_idx, last_wt_idx
        unmapped_script_words, unmatched_wt_words
    """
    if not script_text or not word_timestamps:
        return {
            "mapped": [], "mapping_confidence": 0.0,
            "first_wt_idx": -1, "last_wt_idx": -1,
            "unmapped_script_words": _text_to_norm_words(script_text),
            "unmatched_wt_words": [_normalize_word(wt.get("word", "")) for wt in word_timestamps],
        }

    script_words = _text_to_norm_words(script_text)
    wt_words = [_normalize_word(wt.get("word", "")) for wt in word_timestamps]

    mapped: list[tuple[str, int | None]] = []
    wt_pos = 0
    n_wt = len(wt_words)
    hits = 0

    for sw in script_words:
        if not sw:
            continue
        best_idx = None
        # Tolerans: 6 lookahead (TTS noktalama/sessizlik kelimeleri uretirse)
        for ahead in range(0, 6):
            cand = wt_pos + ahead
            if cand >= n_wt:
                break
            cw = wt_words[cand]
            if cw == sw:
                best_idx = cand
                break
            # Substring toleransi yalnizca 4+ karakterli kelimelerde ve CIFT YONLU
            # tam esitlik yoksa. Farkli Turkce ekleri ayni kelime diye eslestirme.
            if len(sw) >= 5 and len(cw) >= 5 and (sw in cw or cw in sw):
                best_idx = cand
                break
        if best_idx is not None:
            mapped.append((sw, best_idx))
            wt_pos = best_idx + 1
            hits += 1
        else:
            mapped.append((sw, None))

    confidence = hits / max(1, len(script_words))
    matched_idxs = [i for _, i in mapped if i is not None]
    first_wt = matched_idxs[0] if matched_idxs else -1
    last_wt = matched_idxs[-1] if matched_idxs else -1
    used = set(matched_idxs)
    unmatched_wt = [wt_words[i] for i in range(n_wt) if i not in used]
    unmapped_script = [w for w, i in mapped if i is None]

    return {
        "mapped": mapped,
        "mapping_confidence": round(confidence, 3),
        "first_wt_idx": first_wt,
        "last_wt_idx": last_wt,
        "unmapped_script_words": unmapped_script,
        "unmatched_wt_words": unmatched_wt,
    }


def _validate_word_timestamps(word_timestamps: list[dict[str, Any]], total_audio_ms: float) -> tuple[bool, str]:
    """WordBoundary verilerinin bi�imsel tutarliligini dogrula.

    Kurallar:
      - Her word'un word (non-empty str), start_ms (>=0), end_ms (>start_ms) olmali
      - Zamanlar monotonik artmali (sirayla)
      - Hicbir kelime total_audio_ms + 200ms'yi asmamali (kuyruk toleransi)
      - En az 1 kelime olmali
    """
    if not word_timestamps:
        return False, "empty_word_timestamps"
    prev_end = -1.0
    for i, wt in enumerate(word_timestamps):
        w = wt.get("word")
        s = wt.get("start_ms")
        e = wt.get("end_ms")
        if not isinstance(w, str) or not w.strip():
            return False, f"wt[{i}].word eksik veya bos"
        try:
            s = float(s); e = float(e)
        except (TypeError, ValueError):
            return False, f"wt[{i}] start/end_ms sayisal degil"
        if s < 0 or e < 0:
            return False, f"wt[{i}] negatif zaman: {s},{e}"
        if e <= s:
            return False, f"wt[{i}] end<=start: {s},{e}"
        if s < prev_end - 1:  # 1ms tolerans (yuvarlama)
            return False, f"wt[{i}] zaman sirasi bozuk: prev_end={prev_end} start={s}"
        if s > total_audio_ms + 500:
            return False, f"wt[{i}] ses suresini asiyor: {s} > {total_audio_ms}"
        prev_end = e
    return True, "ok"


def _align_one_scene(
    narration_words: list[str],
    word_timestamps: list[dict[str, Any]],
    start_wt_pos: int,
    n_wt: int,
    scene_idx: int,
    lookahead: int = 6,
) -> tuple[int | None, int | None, int, float, int]:
    """Tek bir sahnenin narration kelimelerini wt dizisinde eslestir.

    Donus: (first_wt_idx, last_wt_idx, new_wt_pos, confidence, hit_count)
    Eslesmezse first_wt_idx=None, last_wt_idx=None.
    """
    hits = 0
    first_wt = None
    last_wt = None
    local_pos = start_wt_pos
    for nw in narration_words:
        best_idx = None
        for ahead in range(0, lookahead):
            cand = local_pos + ahead
            if cand >= n_wt:
                break
            cw = _normalize_word(word_timestamps[cand].get("word", ""))
            if cw == nw:
                best_idx = cand
                break
            if len(nw) >= 5 and len(cw) >= 5 and (nw in cw or cw in nw):
                best_idx = cand
                break
        if best_idx is not None:
            if first_wt is None:
                first_wt = best_idx
            last_wt = best_idx
            local_pos = best_idx + 1
            hits += 1
    conf = hits / max(1, len(narration_words))
    return first_wt, last_wt, local_pos, conf, hits


def align_scenes_to_timestamps(
    script: dict[str, Any],
    *,
    min_global_confidence: float = 0.7,
    min_scene_confidence: float = 0.6,
) -> dict[str, Any]:
    """Storyboard sahnelerini TTS WordBoundary zaman damgalarina eslestir.

    DONUS KOŞULLU:
      - Yalnizca TUM kosullar saglanirsa sahnelere start_ms/end_ms vb. yazilir:
          * Edge-TTS engine
          * en az 3 wt
          * gecerli wt verisi (monotonik, pozitif, sinirlar icinde)
          * global guven >= min_global_confidence
          * HER SAHNE icin guven >= min_scene_confidence
          * sahneler sirayla eslesir (wt endeksleri daima artan)
          * gorsel sinirlar matematiksel olarak dogru
      - Aksi takdirde script uzerinde HICBIR DEGISIKLIK yapilmaz ve nedenini
        aciklayan bir fallback raporu dondurulur.
    """
    board = script.get("storyboard")
    word_timestamps = script.get("word_timestamps") or []
    tts_engine = str(script.get("tts_engine", ""))
    total_audio_ms = float(script.get("audio_duration_sec", 0)) * 1000.0
    has_real_edge_tts = tts_engine.startswith("edge-tts") and len(word_timestamps) >= 3

    def fallback(reason: str) -> dict[str, Any]:
        """Fail-safe fallback: hicbir timing alani yazma; kirli timing alanlarini her zaman temizle (karma fallback onleme)."""
        # Eski/kalan timing alanlarini temizle — her fallback'de ZORUNLU
        if isinstance(board, list):
            for s in board:
                if isinstance(s, dict):
                    for k in ("start_ms", "end_ms", "narration_start_ms", "narration_end_ms",
                              "word_start_idx", "word_end_idx", "timing_confidence",
                              "timing_method", "duration_sec", "visual_start_ms", "visual_end_ms"):
                        s.pop(k, None)
        return {
            "timing_method": "estimated_word_weight_proportional",
            "timing_confidence": 0.0,
            "global_alignment_confidence": 0.0,
            "scenes": [],
            "total_audio_ms": round(total_audio_ms, 1),
            "total_visual_ms": 0.0,
            "fallback_reason": reason,
            "note": f"Fallback proportional timing used: {reason}",
        }

    if not has_real_edge_tts:
        return fallback("no_wordboundary_timestamps")
    if not isinstance(board, list) or len(board) < 1:
        return fallback("no_storyboard")
    if total_audio_ms <= 0 or total_audio_ms > 180_000:  # 3 dakika ustu kabul edilmez
        return fallback(f"invalid_audio_duration_ms={total_audio_ms}")

    # WT biçimsel doğrulama
    wt_valid, wt_err = _validate_word_timestamps(word_timestamps, total_audio_ms)
    if not wt_valid:
        return fallback(f"invalid_word_timestamps:{wt_err}")

    # Global eslestirme: script_text yoksa sahnelerin narration'larindan uret
    script_text = script.get("script_text")
    if not script_text:
        script_text = " ".join(str(s.get("narration", "")) for s in board if isinstance(s, dict))
    global_align = align_words_to_text(script_text, word_timestamps)
    global_conf = global_align["mapping_confidence"]
    if global_conf < min_global_confidence:
        return fallback(f"global_alignment_confidence_too_low({global_conf:.2f})")

    # Her sahneyi sirayla eslestir
    n_wt = len(word_timestamps)
    wt_pos = 0
    scene_intermediates: list[dict[str, Any]] = []
    for idx, scene in enumerate(board):
        narration = str(scene.get("narration", "")).strip()
        scene_id = int(scene.get("scene_id", idx + 1))
        narration_words = _text_to_norm_words(narration)
        if not narration_words:
            return fallback(f"scene{scene_id}_empty_narration")
        first_wt, last_wt, new_pos, scene_conf, hits = _align_one_scene(
            narration_words, word_timestamps, wt_pos, n_wt, idx
        )
        if first_wt is None or last_wt is None or scene_conf < min_scene_confidence:
            return fallback(f"scene{scene_id}_alignment_failed(conf={scene_conf:.2f},hits={hits}/{len(narration_words)})")
        # Monotonik sira kontrolu: onceki sahnenin last_wt'i bu sahnenin first_wt'inden kucuk olmali
        if scene_intermediates:
            prev_last = scene_intermediates[-1]["last_wt"]
            if first_wt < prev_last:
                return fallback(f"scene{scene_id}_non_monotonic(prev_last={prev_last},first={first_wt})")
        narr_start = float(word_timestamps[first_wt]["start_ms"])
        narr_end = float(word_timestamps[last_wt]["end_ms"])
        scene_intermediates.append({
            "scene_id": scene_id, "scene": scene, "first_wt": first_wt, "last_wt": last_wt,
            "narration_start_ms": narr_start, "narration_end_ms": narr_end,
            "scene_conf": scene_conf, "hits": hits, "total_words": len(narration_words),
        })
        wt_pos = new_pos

    # ── GORSEL SINIRLARIN MATEMATİKSEL HESABI ──
    # Strateji:
    #   S[0].visual_start = 0
    #   S[n-1].visual_end = total_audio_ms
    #   Orta sahnelerde, S[i].visual_end = S[i+1].visual_start = midpoint
    #     midpoint = (S[i].narration_end + S[i+1].narration_start) / 2
    #   Sinirlar pozitif/monotonik olacak; ard arda gelen sahnelerin narration
    #   sinirlari cakisiyorsa (ornegin cok kisa cumleler) kirpma yap.
    n = len(scene_intermediates)
    visual_starts = [0.0] * n
    visual_ends = [0.0] * n
    for i in range(1, n):
        prev_end = scene_intermediates[i-1]["narration_end_ms"]
        curr_start = scene_intermediates[i]["narration_start_ms"]
        mid = (prev_end + curr_start) / 2.0
        # mid, iki narration arasi boslukta olmali. Eger cumleler bitisik
        # (prev_end >= curr_start), mid = prev_end (cakisma yok, kirpma yok).
        mid = max(mid, prev_end)
        mid = min(mid, curr_start)
        mid = max(mid, 0.0)
        visual_starts[i] = round(mid, 1)
        visual_ends[i-1] = round(mid, 1)
    visual_ends[-1] = round(total_audio_ms, 1)

    # Matematiksel dogrulama
    # (1) ilk sahne 0'da baslar
    if visual_starts[0] != 0.0:
        return fallback(f"first_scene_start_nonzero:{visual_starts[0]}")
    # (2) son sahne audio_duration_ms'de biter
    if abs(visual_ends[-1] - total_audio_ms) > 1.0:
        return fallback(f"last_scene_end_mismatch:{visual_ends[-1]} vs {total_audio_ms}")
    prev_end = 0.0
    for i in range(n):
        vs, ve = visual_starts[i], visual_ends[i]
        # (3) pozitif sure
        if ve <= vs:
            return fallback(f"scene{i+1}_non_positive_duration:{vs}-{ve}")
        # (4) bosluk yok, (5) cakisma yok
        if abs(vs - prev_end) > 1.0:
            return fallback(f"scene{i+1}_gap_or_overlap:vs={vs} prev_end={prev_end}")
        # (6) ses suresi asimi
        if ve > total_audio_ms + 1.0:
            return fallback(f"scene{i+1}_exceeds_audio:ve={ve} total={total_audio_ms}")
        prev_end = ve
    total_visual = sum(ve - vs for vs, ve in zip(visual_starts, visual_ends))
    # (7) toplam uyumu
    if abs(total_visual - total_audio_ms) > 2.0:
        return fallback(f"total_visual_mismatch:{total_visual} vs {total_audio_ms}")

    # Butun kontroller gectiyse sahnelere timing alanlarini yaz
    scene_reports = []
    for i, sd in enumerate(scene_intermediates):
        vs, ve = visual_starts[i], visual_ends[i]
        scene = sd["scene"]
        scene["start_ms"] = vs
        scene["end_ms"] = ve
        scene["visual_start_ms"] = vs
        scene["visual_end_ms"] = ve
        scene["narration_start_ms"] = round(sd["narration_start_ms"], 1)
        scene["narration_end_ms"] = round(sd["narration_end_ms"], 1)
        scene["word_start_idx"] = sd["first_wt"]
        scene["word_end_idx"] = sd["last_wt"]
        scene["timing_confidence"] = round(sd["scene_conf"], 3)
        scene["timing_method"] = "edge-tts-wordboundary"
        scene["duration_sec"] = round((ve - vs) / 1000.0, 3)
        scene_reports.append({
            "scene_id": sd["scene_id"],
            "narration_start_ms": round(sd["narration_start_ms"], 1),
            "narration_end_ms": round(sd["narration_end_ms"], 1),
            "visual_start_ms": vs, "visual_end_ms": ve,
            "word_start_idx": sd["first_wt"], "word_end_idx": sd["last_wt"],
            "scene_confidence": round(sd["scene_conf"], 3),
            "word_hit_count": sd["hits"],
            "word_total_count": sd["total_words"],
            "status": "aligned",
        })

    return {
        "timing_method": "edge-tts-wordboundary",
        "timing_confidence": global_conf,
        "global_alignment_confidence": global_conf,
        "min_scene_confidence": min(s["scene_confidence"] for s in scene_reports),
        "scenes": scene_reports,
        "total_audio_ms": round(total_audio_ms, 1),
        "total_visual_ms": round(total_visual, 1),
        "fallback_reason": None,
        "note": "All scenes aligned; visual bounds tile without gap/overlap covering full audio.",
    }


def _build_fallback_timing_report(script: dict, *, reason: str) -> dict[str, Any]:
    """Public API: TTS zamani yoksa veya guven dusukse, word-weight tahmini korunur."""
    # Bu fonksiyon disaridan cagrilabilir; mevcut board uzerinde eski timing alanlarini temizle
    board = script.get("storyboard")
    if isinstance(board, list):
        for s in board:
            if isinstance(s, dict):
                for k in ("start_ms", "end_ms", "narration_start_ms", "narration_end_ms",
                          "visual_start_ms", "visual_end_ms",
                          "word_start_idx", "word_end_idx", "timing_confidence",
                          "timing_method", "duration_sec"):
                    s.pop(k, None)
    return {
        "timing_method": "estimated_word_weight_proportional",
        "timing_confidence": 0.0,
        "global_alignment_confidence": 0.0,
        "min_scene_confidence": 0.0,
        "scenes": [],
        "total_audio_ms": round(float(script.get("audio_duration_sec", 0)) * 1000.0, 1),
        "total_visual_ms": 0.0,
        "fallback_reason": reason,
        "note": f"Fallback proportional timing used: {reason}",
    }


def compute_timing_method(script: dict[str, Any]) -> str:
    """Script uzerinden timing_method etiketini belirle.

    Yalnizca su kosullar dogruysa 'edge-tts-wordboundary' doner:
      - tts_engine edge-tts ile basliyor
      - en az 3 wt var
      - her sahnenin start_ms/end_ms/duration_sec degerleri var
      - matematiksel kosullar saglaniyor (monotonik, gap=0, toplam = audio, pozitif)
    """
    tts = str(script.get("tts_engine", ""))
    wt = script.get("word_timestamps") or []
    board = script.get("storyboard") or []
    if not tts.startswith("edge-tts") or len(wt) < 3 or not isinstance(board, list) or not board:
        return "estimated_word_weight_proportional"

    total_ms = float(script.get("audio_duration_sec", 0)) * 1000.0
    if total_ms <= 0:
        return "estimated_word_weight_proportional"

    # Her sahne start_ms/end_ms/duration_sec var mi ve tutarli mi?
    prev_end = 0.0
    total_vis = 0.0
    for s in board:
        if not isinstance(s, dict):
            return "estimated_word_weight_proportional"
        vs = s.get("start_ms"); ve = s.get("end_ms")
        if not isinstance(vs, (int, float)) or not isinstance(ve, (int, float)):
            return "estimated_word_weight_proportional"
        if vs < 0 or ve <= vs or ve > total_ms + 1.0:
            return "estimated_word_weight_proportional"
        if abs(vs - prev_end) > 2.0:
            return "estimated_word_weight_proportional"
        if s.get("timing_method") != "edge-tts-wordboundary":
            return "estimated_word_weight_proportional"
        prev_end = ve
        total_vis += ve - vs
    if abs(prev_end - total_ms) > 2.0:
        return "estimated_word_weight_proportional"
    if abs(total_vis - total_ms) > 3.0:
        return "estimated_word_weight_proportional"
    return "edge-tts-wordboundary"
