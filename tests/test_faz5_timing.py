"""Faz 5 — Gercek TTS word-timing ve sahne senkronizasyonu testleri.

Test katmanlari:
  1. Unit: normalize_words, text_to_norm_words
  2. Unit: align_words_to_text (sentetik word_timestamps ile)
  3. Unit: align_scenes_to_timestamps (coklu sahne, karisik eslesme)
  4. Unit: compute_timing_method edge-tts vs fallback
  5. Unit: scene_plan() real-timing path integration
  6. Integration: build_dynamic_shorts_srt scene_boundaries
  7. Gercek Edge-TTS test (ag gerekli, CI kosullarinda atlanabilir)
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestWordNormalization(unittest.TestCase):
    def test_basic_lowercase(self):
        from src.media_processing.timing import _normalize_word
        self.assertEqual(_normalize_word("Merhaba"), "merhaba")
        self.assertEqual(_normalize_word("DÜNYA"), "dünya")

    def test_turkish_special_i(self):
        from src.media_processing.timing import _normalize_word
        # I -> ı (Turkish dotless i lowercase), İ -> i
        self.assertEqual(_normalize_word("I"), "ı")
        self.assertEqual(_normalize_word("İ"), "i")
        self.assertEqual(_normalize_word("İstanbul"), "istanbul")
        self.assertEqual(_normalize_word("Iğdır"), "ığdır")

    def test_punctuation_stripped(self):
        from src.media_processing.timing import _normalize_word
        self.assertEqual(_normalize_word("dünya,"), "dünya")
        self.assertEqual(_normalize_word("göstermişti."), "göstermişti")
        self.assertEqual(_normalize_word("(neden)"), "neden")

    def test_empty(self):
        from src.media_processing.timing import _normalize_word, _text_to_norm_words
        self.assertEqual(_normalize_word(""), "")
        self.assertEqual(_normalize_word("..."), "")
        self.assertEqual(_text_to_norm_words(""), [])
        self.assertEqual(_text_to_norm_words("!!! ???"), [])


class TestWordToTextAlignment(unittest.TestCase):
    def test_perfect_alignment(self):
        from src.media_processing.timing import align_words_to_text
        text = "Merhaba dünya bu bir test"
        wts = [
            {"word": "Merhaba", "start_ms": 100, "end_ms": 700},
            {"word": "dünya", "start_ms": 750, "end_ms": 1100},
            {"word": "bu", "start_ms": 1200, "end_ms": 1400},
            {"word": "bir", "start_ms": 1450, "end_ms": 1650},
            {"word": "test", "start_ms": 1700, "end_ms": 2000},
        ]
        result = align_words_to_text(text, wts)
        self.assertGreaterEqual(result["mapping_confidence"], 0.99)
        self.assertEqual(result["first_wt_idx"], 0)
        self.assertEqual(result["last_wt_idx"], 4)
        self.assertEqual(result["unmapped_script_words"], [])

    def test_alignment_with_punctuation(self):
        from src.media_processing.timing import align_words_to_text
        text = "Merhaba dünya. Bu bir test!"
        wts = [
            {"word": "Merhaba", "start_ms": 100, "end_ms": 700},
            {"word": "dünya", "start_ms": 750, "end_ms": 1100},
            {"word": "Bu", "start_ms": 1200, "end_ms": 1400},
            {"word": "bir", "start_ms": 1450, "end_ms": 1650},
            {"word": "test", "start_ms": 1700, "end_ms": 2000},
        ]
        result = align_words_to_text(text, wts)
        self.assertGreaterEqual(result["mapping_confidence"], 0.99)

    def test_empty_inputs(self):
        from src.media_processing.timing import align_words_to_text
        r = align_words_to_text("", [])
        self.assertEqual(r["mapping_confidence"], 0.0)
        r2 = align_words_to_text("text", [])
        self.assertEqual(r2["mapping_confidence"], 0.0)


class TestSceneAlignment(unittest.TestCase):
    def _make_script(self, sentences, durations=None, audio_sec=None,
                    tts_engine="edge-tts:tr-TR-AhmetNeural"):
        """Helper: build a script with word_timestamps at equal intervals."""
        words = []
        all_text_parts = []
        cursor_ms = 100.0
        word_dur = 400.0
        gap_ms = 100.0
        for si, sent in enumerate(sentences):
            for w in sent.split():
                clean = w.strip(".,!?;:")
                if not clean:
                    continue
                words.append({"word": clean, "start_ms": round(cursor_ms,1),
                              "end_ms": round(cursor_ms + word_dur,1)})
                cursor_ms += word_dur + gap_ms
                all_text_parts.append(clean)
            # sentence pause
            cursor_ms += 250.0
        total_ms = words[-1]["end_ms"] if words else 1000.0
        if durations:
            total_ms = sum(durations) * 1000.0
        total_sec = audio_sec if audio_sec else total_ms / 1000.0
        # Build storyboard
        wt_idx = 0
        storyboard = []
        for si, sent in enumerate(sentences):
            n_words = len([w for w in sent.split() if w.strip(".,!?;:")])
            storyboard.append({
                "scene_id": si+1,
                "narration": sent,
                "visual_query": f"query_{si}",
            })
            wt_idx += n_words
        return {
            "script_text": " ".join(all_text_parts),
            "audio_duration_sec": total_sec,
            "tts_engine": tts_engine,
            "word_timestamps": words,
            "storyboard": storyboard,
        }

    def test_two_scene_alignment(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = self._make_script([
            "Merhaba dünya.",
            "Bu bir test.",
        ])
        report = align_scenes_to_timestamps(script)
        self.assertEqual(report["timing_method"], "edge-tts-wordboundary")
        self.assertEqual(report["timing_confidence"], 1.0)
        # Scenes tile with no gaps/overlaps
        board = script["storyboard"]
        prev_end = 0.0
        for s in board:
            self.assertIn("start_ms", s)
            self.assertIn("end_ms", s)
            self.assertIn("narration_start_ms", s)
            self.assertIn("narration_end_ms", s)
            self.assertEqual(s["timing_method"], "edge-tts-wordboundary")
            self.assertGreaterEqual(s["timing_confidence"], 0.5)
            self.assertAlmostEqual(s["start_ms"], prev_end, places=1)
            self.assertGreater(s["end_ms"], s["start_ms"])
            prev_end = s["end_ms"]
        self.assertAlmostEqual(prev_end, script["audio_duration_sec"]*1000, delta=5)

    def test_four_scene_tiling(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = self._make_script([
            "Piri Reis haritayı çizdi.",
            "Güney Amerika kıyılarını gösterdi.",
            "Araştırmacılar buna inanmadı.",
            "Haritanın sırrı çözülmedi.",
        ])
        report = align_scenes_to_timestamps(script)
        self.assertEqual(len(report["scenes"]), 4)
        total = 0
        for s in script["storyboard"]:
            total += s["end_ms"] - s["start_ms"]
        self.assertAlmostEqual(total, script["audio_duration_sec"]*1000, delta=5)

    def test_no_edge_tts_falls_back(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = self._make_script(["Hello world."], tts_engine="gtts:tr-fallback")
        report = align_scenes_to_timestamps(script)
        self.assertEqual(report["timing_method"], "estimated_word_weight_proportional")
        # Scenes should not be modified (no start_ms added)
        self.assertNotIn("start_ms", script["storyboard"][0])

    def test_low_confidence_falls_back(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        # Make a script where narration text doesn't match word_timestamps
        script = {
            "script_text": "tamamen farklı bir metin burada",
            "audio_duration_sec": 2.0,
            "tts_engine": "edge-tts:tr-TR-AhmetNeural",
            "word_timestamps": [
                {"word": "xxxxx", "start_ms": 100, "end_ms": 500},
                {"word": "yyyyy", "start_ms": 600, "end_ms": 1000},
            ],
            "storyboard": [{"scene_id":1,"narration":"uymayan cümle burada","visual_query":"test"}],
        }
        report = align_scenes_to_timestamps(script)
        self.assertEqual(report["timing_method"], "estimated_word_weight_proportional")


class TestComputeTimingMethod(unittest.TestCase):
    def test_edge_tts_real(self):
        from src.media_processing.timing import compute_timing_method
        s = {"tts_engine": "edge-tts:tr-TR-AhmetNeural",
             "word_timestamps": [{"word":"a","start_ms":0,"end_ms":100},
                                 {"word":"b","start_ms":100,"end_ms":200},
                                 {"word":"c","start_ms":200,"end_ms":300}],
             "storyboard": [{"scene_id":1,"narration":"a b c","visual_query":"q",
                             "start_ms":0,"end_ms":300}]}
        self.assertEqual(compute_timing_method(s), "edge-tts-wordboundary")

    def test_estimated_when_no_timestamps(self):
        from src.media_processing.timing import compute_timing_method
        s = {"tts_engine": "edge-tts:tr-TR-AhmetNeural", "word_timestamps": [],
             "storyboard": [{"scene_id":1,"narration":"test","visual_query":"q"}]}
        self.assertEqual(compute_timing_method(s), "estimated_word_weight_proportional")

    def test_gtts_is_estimated(self):
        from src.media_processing.timing import compute_timing_method
        s = {"tts_engine": "gtts:tr-fallback",
             "word_timestamps": [{"word":"a","start_ms":0,"end_ms":100}],
             "storyboard": [{"scene_id":1,"narration":"a","visual_query":"q"}]}
        self.assertEqual(compute_timing_method(s), "estimated_word_weight_proportional")


class TestScenePlanRealTiming(unittest.TestCase):
    def test_scene_plan_uses_real_timing_when_available(self):
        from src.media_processing.scene_media import scene_plan
        script = {
            "audio_duration_sec": 2.0,
            "visual_keywords": ["test"],
            "storyboard": [
                {"scene_id": 1, "narration": "İlk cümle burada.", "visual_query": "first",
                 "start_ms": 0.0, "end_ms": 800.0, "narration_start_ms": 100.0,
                 "narration_end_ms": 700.0, "timing_method": "edge-tts-wordboundary",
                 "timing_confidence": 1.0},
                {"scene_id": 2, "narration": "İkinci cümle.", "visual_query": "second",
                 "start_ms": 800.0, "end_ms": 2000.0, "narration_start_ms": 900.0,
                 "narration_end_ms": 1800.0, "timing_method": "edge-tts-wordboundary",
                 "timing_confidence": 1.0},
            ],
        }
        plan = scene_plan(script)
        self.assertEqual(len(plan), 2)
        # Real TTS timing: 0.8s + 1.2s = 2.0s total
        self.assertAlmostEqual(plan[0]["duration"], 0.8, places=2)
        self.assertAlmostEqual(plan[1]["duration"], 1.2, places=2)
        self.assertAlmostEqual(sum(p["duration"] for p in plan), 2.0, places=2)

    def test_scene_plan_proportional_fallback(self):
        from src.media_processing.scene_media import scene_plan
        script = {
            "audio_duration_sec": 4.0,
            "visual_keywords": ["test"],
            "storyboard": [
                {"scene_id": 1, "narration": "bir iki", "visual_query": "first"},
                {"scene_id": 2, "narration": "üç dört beş altı", "visual_query": "second"},
            ],
        }
        plan = scene_plan(script)
        # Proportional by word count: 2 + 4 words = 6 total; scene1 = 4*2/6 = 1.33s, scene2 = 4*4/6=2.67
        self.assertAlmostEqual(plan[0]["duration"], 4*2/6, places=2)
        self.assertAlmostEqual(sum(p["duration"] for p in plan), 4.0, places=2)


class TestSRTSceneBoundaries(unittest.TestCase):
    def test_srt_no_cross_scene_cuts(self):
        """Altyazi bloklari sahne kesim noktasindan (inter-word gap) sonra siniri asla gecmez.

        Gercek zamanlamada sinirlar her zaman kelimeler arasi boslukta olur (midpoint
        algorithm'i narration_end ile narration_start arasi orta noktayi secer).
        Bu testte de sahte veriyi bu gercege uygun olusturuyoruz: w1 end=900, w2 start=1000,
        sinir 950ms (aradaki gap).
        """
        from content_engine import build_dynamic_shorts_srt
        wts = [
            {"word":"w0","start_ms":0,"end_ms":400},
            {"word":"w1","start_ms":500,"end_ms":900},   # ends at 900
            {"word":"w2","start_ms":1000,"end_ms":1400}, # starts at 1000 (100ms gap)
            {"word":"w3","start_ms":1500,"end_ms":1900},
            {"word":"w4","start_ms":2000,"end_ms":2400},
        ]
        # Boundary at 950ms (midpoint between w1 end=900 and w2 start=1000)
        boundaries = [(0, 950), (950, 3000)]
        srt = build_dynamic_shorts_srt(wts, words_per_cue=3, scene_boundaries=boundaries)
        import re as _re
        cues = [c for c in srt.strip().split("\n\n") if c.strip()]
        def _parse(ts):
            h,mi,s,ms = map(int, _re.split(r"[:,]", ts))
            return (h*3600+mi*60+s)*1000+ms
        for cue in cues:
            lines = cue.strip().split("\n")
            if len(lines) < 3: continue
            m = _re.match(r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", lines[1])
            if not m: continue
            start = _parse(m.group(1))
            end = _parse(m.group(2))
            # Cue either entirely before 950 or entirely at/after 950 start
            if start < 950:
                self.assertLessEqual(end, 950 + 1, f"Cue spans boundary: {lines[1]}")
            else:
                self.assertGreaterEqual(start, 950 - 1)

    def test_srt_basic(self):
        from content_engine import build_dynamic_shorts_srt
        wts = [{"word":"a","start_ms":0,"end_ms":300},{"word":"b","start_ms":300,"end_ms":600},
               {"word":"c","start_ms":600,"end_ms":900}]
        srt = build_dynamic_shorts_srt(wts, words_per_cue=2)
        self.assertIn("00:00:00,000 --> 00:00:00,600", srt)
        self.assertIn("a b", srt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
