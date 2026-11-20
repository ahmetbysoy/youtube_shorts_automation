"""Faz 5 — Gercek TTS word-timing ve sahne senkronizasyonu testleri.

Test katmanlari:
  1. Unit: normalize_words, text_to_norm_words
  2. Unit: align_words_to_text (sentetik word_timestamps ile)
  3. Unit: _validate_word_timestamps (negatif, sirasiz, bozuk veriler)
  4. Unit: align_scenes_to_timestamps (coklu sahne, tam/yarali eslesme, karma fallback)
  5. Unit: compute_timing_method etiketleme
  6. Unit: scene_plan() real-timing vs proportional path
  7. Unit: build_dynamic_shorts_srt scene_boundaries (kesim noktasinda altyazi tasma)
  8. Integration: ses QC (sessizlik ve clipping)
  9. Integration: gercek Edge-TTS ile senaryo uretimi
"""
from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class TestWordNormalization(unittest.TestCase):
    def test_basic_lowercase(self):
        from src.media_processing.timing import _normalize_word
        self.assertEqual(_normalize_word("Merhaba"), "merhaba")
        self.assertEqual(_normalize_word("DÜNYA"), "dünya")

    def test_turkish_special_i(self):
        from src.media_processing.timing import _normalize_word
        self.assertEqual(_normalize_word("I"), "ı")
        self.assertEqual(_normalize_word("İ"), "i")
        self.assertEqual(_normalize_word("İstanbul"), "istanbul")
        self.assertEqual(_normalize_word("Iğdır"), "ığdır")

    def test_punctuation_stripped(self):
        from src.media_processing.timing import _normalize_word
        self.assertEqual(_normalize_word("dünya,"), "dünya")
        self.assertEqual(_normalize_word("göstermişti."), "göstermişti")

    def test_empty(self):
        from src.media_processing.timing import _normalize_word, _text_to_norm_words
        self.assertEqual(_normalize_word(""), "")
        self.assertEqual(_normalize_word("..."), "")
        self.assertEqual(_text_to_norm_words(""), [])


class TestWordToTextAlignment(unittest.TestCase):
    def test_perfect_alignment(self):
        from src.media_processing.timing import align_words_to_text
        text = "Merhaba dünya bu bir test"
        wts = [{"word": w, "start_ms": i*200+100, "end_ms": i*200+300}
               for i, w in enumerate(["Merhaba","dünya","bu","bir","test"])]
        r = align_words_to_text(text, wts)
        self.assertGreaterEqual(r["mapping_confidence"], 0.99)

    def test_punctuation(self):
        from src.media_processing.timing import align_words_to_text
        text = "Merhaba dünya. Bu bir test!"
        wts = [{"word": w, "start_ms": i*200+100, "end_ms": i*200+300}
               for i, w in enumerate(["Merhaba","dünya","Bu","bir","test"])]
        r = align_words_to_text(text, wts)
        self.assertGreaterEqual(r["mapping_confidence"], 0.99)

    def test_empty(self):
        from src.media_processing.timing import align_words_to_text
        r = align_words_to_text("", [])
        self.assertEqual(r["mapping_confidence"], 0.0)


class TestValidateWordTimestamps(unittest.TestCase):
    def test_valid(self):
        from src.media_processing.timing import _validate_word_timestamps
        wts = [{"word":"a","start_ms":0,"end_ms":200},
               {"word":"b","start_ms":200,"end_ms":400}]
        ok, err = _validate_word_timestamps(wts, 500)
        self.assertTrue(ok, err)

    def test_empty(self):
        from src.media_processing.timing import _validate_word_timestamps
        ok, _ = _validate_word_timestamps([], 500)
        self.assertFalse(ok)

    def test_negative_time(self):
        from src.media_processing.timing import _validate_word_timestamps
        wts = [{"word":"a","start_ms":-50,"end_ms":100}]
        ok, _ = _validate_word_timestamps(wts, 500)
        self.assertFalse(ok)

    def test_end_before_start(self):
        from src.media_processing.timing import _validate_word_timestamps
        wts = [{"word":"a","start_ms":300,"end_ms":200}]
        ok, _ = _validate_word_timestamps(wts, 500)
        self.assertFalse(ok)

    def test_non_monotonic(self):
        from src.media_processing.timing import _validate_word_timestamps
        wts = [{"word":"a","start_ms":0,"end_ms":300},
               {"word":"b","start_ms":200,"end_ms":500}]
        ok, _ = _validate_word_timestamps(wts, 500)
        self.assertFalse(ok)

    def test_exceeds_audio(self):
        from src.media_processing.timing import _validate_word_timestamps
        wts = [{"word":"a","start_ms":0,"end_ms":200},
               {"word":"b","start_ms":8000,"end_ms":9000}]
        ok, _ = _validate_word_timestamps(wts, 1000)
        self.assertFalse(ok)


def _make_script(sentences, tts_engine="edge-tts:tr-TR-AhmetNeural", word_dur=400, gap=100,
                 sent_pause=250, start_offset=100.0):
    """Helper: duzenli aralikli sentetik wt uret."""
    words = []
    cursor = start_offset
    all_words_flat = []
    for si, sent in enumerate(sentences):
        sent_words = [w.strip(".,!?;:") for w in sent.split() if w.strip(".,!?;:" )]
        for w in sent_words:
            words.append({"word": w, "start_ms": round(cursor,1), "end_ms": round(cursor+word_dur,1)})
            all_words_flat.append(w)
            cursor += word_dur + gap
        cursor += sent_pause
    total_ms = words[-1]["end_ms"] if words else 1000
    return {
        "script_text": " ".join(all_words_flat),
        "audio_duration_sec": round(total_ms/1000.0, 3),
        "tts_engine": tts_engine,
        "word_timestamps": words,
        "visual_keywords": all_words_flat[:4] if all_words_flat else ["test"],
        "storyboard": [
            {"scene_id": i+1, "narration": s, "visual_query": f"q{i}"}
            for i, s in enumerate(sentences)
        ],
    }


class TestSceneAlignment(unittest.TestCase):
    def test_two_scene_perfect_tiling(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = _make_script(["Merhaba dünya.", "Bu bir test."])
        r = align_scenes_to_timestamps(script)
        self.assertEqual(r["timing_method"], "edge-tts-wordboundary")
        board = script["storyboard"]
        self.assertEqual(len(board), 2)
        # Matematiksel kosullari dogrula
        self.assertEqual(board[0]["start_ms"], 0.0)
        self.assertAlmostEqual(board[-1]["end_ms"], script["audio_duration_sec"]*1000, delta=1)
        prev_end = 0.0
        total = 0.0
        for s in board:
            self.assertGreater(s["end_ms"], s["start_ms"])
            self.assertAlmostEqual(s["start_ms"], prev_end, delta=1)
            self.assertIn("timing_method", s)
            self.assertEqual(s["timing_method"], "edge-tts-wordboundary")
            total += s["end_ms"] - s["start_ms"]
            prev_end = s["end_ms"]
        self.assertAlmostEqual(total, script["audio_duration_sec"]*1000, delta=2)

    def test_four_scene_tiling(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = _make_script([
            "Piri Reis haritayı çizdi.",
            "Güney Amerika kıyılarını gösterdi.",
            "Araştırmacılar buna inanmadı.",
            "Haritanın sırrı Çözülmedi.",
        ])
        r = align_scenes_to_timestamps(script)
        self.assertEqual(r["timing_method"], "edge-tts-wordboundary")
        prev_end = 0.0
        for s in script["storyboard"]:
            self.assertAlmostEqual(s["start_ms"], prev_end, delta=1)
            prev_end = s["end_ms"]
        self.assertAlmostEqual(prev_end, script["audio_duration_sec"]*1000, delta=1)

    def test_fallback_on_single_scene_failure(self):
        """Bir sahne eslesmezse HICBIR sahneye timing yazilmamali (karma fallback yok)."""
        from src.media_processing.timing import align_scenes_to_timestamps
        # narration wt ile tamamen uyuşmayan bir kelime ekle
        script = {
            "script_text": "Merhaba dünya bu bir test",
            "audio_duration_sec": 2.0,
            "tts_engine": "edge-tts:tr-TR-AhmetNeural",
            "word_timestamps": [
                {"word":"Merhaba","start_ms":100,"end_ms":700},
                {"word":"dünya","start_ms":750,"end_ms":1100},
                {"word":"bu","start_ms":1200,"end_ms":1400},
                {"word":"bir","start_ms":1450,"end_ms":1650},
                {"word":"test","start_ms":1700,"end_ms":2000},
            ],
            "storyboard": [
                {"scene_id":1,"narration":"Merhaba dünya","visual_query":"q0"},
                {"scene_id":2,"narration":"xyzabc qwerty uyuşmayan","visual_query":"q1"},
            ],
        }
        r = align_scenes_to_timestamps(script)
        self.assertEqual(r["timing_method"], "estimated_word_weight_proportional")
        # Hicbir sahneye start_ms yazilmamis olmali
        for s in script["storyboard"]:
            self.assertNotIn("start_ms", s, f"Scene {s['scene_id']} timing kaldi ama fallback bekleniyordu")
        self.assertIsNotNone(r.get("fallback_reason"))

    def test_fallback_when_no_edge_tts(self):
        from src.media_processing.timing import align_scenes_to_timestamps
        script = _make_script(["Merhaba dünya."], tts_engine="gtts:tr-fallback")
        r = align_scenes_to_timestamps(script)
        self.assertEqual(r["timing_method"], "estimated_word_weight_proportional")
        self.assertNotIn("start_ms", script["storyboard"][0])

    def test_fallback_clears_stale_timing(self):
        """Fallbacge donuldugunde daha once yazilmis start_ms/end_ms temizlenmeli."""
        from src.media_processing.timing import align_scenes_to_timestamps
        script = _make_script(["Merhaba"], tts_engine="gtts:tr-fallback")
        script["storyboard"][0]["start_ms"] = 123.0  # stale data
        script["storyboard"][0]["end_ms"] = 456.0
        script["storyboard"][0]["timing_method"] = "edge-tts-wordboundary"
        align_scenes_to_timestamps(script)
        self.assertNotIn("start_ms", script["storyboard"][0])
        self.assertNotIn("timing_method", script["storyboard"][0])

    def test_visual_end_leq_start_never_500_hack(self):
        """Eski kodda visual_end<=visual_start durumunda +500ms ekleniyordu; bu
        audio'yu asabilir veya cakisma yaratabilirdi. Yeni matematiksel çözümde
        bu durum hic olusmamali."""
        from src.media_processing.timing import align_scenes_to_timestamps
        script = _make_script(["a b.", "c d."], word_dur=50, gap=10, sent_pause=20)
        r = align_scenes_to_timestamps(script)
        self.assertEqual(r["timing_method"], "edge-tts-wordboundary")
        for s in script["storyboard"]:
            self.assertGreater(s["end_ms"] - s["start_ms"], 100)  # mantiksiz kisa sure yok


class TestComputeTimingMethod(unittest.TestCase):
    def test_edge_tts_real(self):
        from src.media_processing.timing import compute_timing_method
        s = _make_script(["a b.", "c d."])
        from src.media_processing.timing import align_scenes_to_timestamps
        align_scenes_to_timestamps(s)
        self.assertEqual(compute_timing_method(s), "edge-tts-wordboundary")

    def test_estimated_when_no_timestamps(self):
        from src.media_processing.timing import compute_timing_method
        s = {"tts_engine":"edge-tts:tr-TR-AhmetNeural","word_timestamps":[],
             "storyboard":[{"scene_id":1,"narration":"t","visual_query":"q"}],
             "audio_duration_sec":1.0}
        self.assertEqual(compute_timing_method(s), "estimated_word_weight_proportional")

    def test_gtts_is_estimated(self):
        from src.media_processing.timing import compute_timing_method
        s = _make_script(["a"], tts_engine="gtts:tr-fallback")
        self.assertEqual(compute_timing_method(s), "estimated_word_weight_proportional")

    def test_inconsistent_fields_detected(self):
        """Sahnelerde start_ms var ama degerler tutarsizsa estimated donmeli."""
        from src.media_processing.timing import compute_timing_method
        s = {"tts_engine":"edge-tts:tr-TR-AhmetNeural",
             "word_timestamps":[{"word":"a","start_ms":0,"end_ms":200}],
             "audio_duration_sec":1.0,
             "storyboard":[{"scene_id":1,"narration":"a","visual_query":"q",
                            "start_ms":0.0,"end_ms":500.0,"duration_sec":0.5,
                            "timing_method":"edge-tts-wordboundary"},
                           {"scene_id":2,"narration":"b","visual_query":"q",
                            "start_ms":600.0,"end_ms":1000.0,"duration_sec":0.4,
                            "timing_method":"edge-tts-wordboundary"}]}
        # Gap var (500-600) → estimated
        self.assertEqual(compute_timing_method(s), "estimated_word_weight_proportional")


class TestScenePlanRealTiming(unittest.TestCase):
    def test_scene_plan_uses_real_timing(self):
        from src.media_processing.scene_media import scene_plan
        script = _make_script(["İlk cümle burada.", "İkinci cümle burada."])
        from src.media_processing.timing import align_scenes_to_timestamps
        align_scenes_to_timestamps(script)
        plan = scene_plan(script)
        total = sum(p["duration"] for p in plan)
        self.assertAlmostEqual(total, script["audio_duration_sec"], places=2)
        for p in plan:
            self.assertGreater(p["duration"], 0.3)

    def test_scene_plan_proportional_fallback(self):
        from src.media_processing.scene_media import scene_plan
        script = {
            "audio_duration_sec":4.0,"visual_keywords":["test"],
            "storyboard":[{"scene_id":1,"narration":"bir iki","visual_query":"first"},
                          {"scene_id":2,"narration":"üç dört beş altı","visual_query":"second"}]}
        plan = scene_plan(script)
        self.assertAlmostEqual(sum(p["duration"] for p in plan), 4.0, places=2)


class TestSRTSceneBoundaries(unittest.TestCase):
    def test_no_cross_scene_cuts(self):
        from content_engine import build_dynamic_shorts_srt
        # Gercekci senaryo: w1 sonu 900, w2 basi 1000, sinir 950
        wts = [
            {"word":"w0","start_ms":0,"end_ms":400},
            {"word":"w1","start_ms":500,"end_ms":900},
            {"word":"w2","start_ms":1000,"end_ms":1400},
            {"word":"w3","start_ms":1500,"end_ms":1900},
            {"word":"w4","start_ms":2000,"end_ms":2400},
        ]
        boundaries = [(0, 950), (950, 3000)]
        srt = build_dynamic_shorts_srt(wts, words_per_cue=3, scene_boundaries=boundaries)
        import re as _re
        def _parse(ts):
            h,mi,s,ms = map(int, _re.split(r"[:,]", ts))
            return (h*3600+mi*60+s)*1000+ms
        cues = [c for c in srt.strip().split("\n\n") if "-->" in c]
        for cue in cues:
            lines = cue.split("\n")
            m = _re.match(r"(\d+:\d+:\d+,\d+) --> (\d+:\d+:\d+,\d+)", lines[1])
            s_ts, e_ts = _parse(m.group(1)), _parse(m.group(2))
            # Boundary oncesinde baslayip 955ms sonrasina uzanan cue olmamali
            if s_ts < 950:
                self.assertLessEqual(e_ts, 955, f"Cue siniri asiyor: {lines[1]}")

    def test_srt_basic(self):
        from content_engine import build_dynamic_shorts_srt
        wts = [{"word":"a","start_ms":0,"end_ms":300},{"word":"b","start_ms":300,"end_ms":600},
               {"word":"c","start_ms":600,"end_ms":900}]
        srt = build_dynamic_shorts_srt(wts, words_per_cue=2)
        self.assertIn("00:00:00,000 --> 00:00:00,600", srt)


def _make_sine_wav(path: Path, duration_s: float, freq: float = 440, sr: int = 24000,
                   volume: float = 0.5, clipping: bool = False,
                   silences: list[tuple[float, float]] | None = None) -> None:
    """Test icin sentetik WAV (sonra MP3'e cevir) uret."""
    import wave
    t = np.linspace(0, duration_s, int(sr*duration_s), endpoint=False)
    signal = volume * np.sin(2*np.pi*freq*t)
    if clipping:
        signal = np.sign(signal) * 0.99  # hard clipping
    if silences:
        for s, e in silences:
            si, ei = int(s*sr), int(e*sr)
            signal[si:ei] = 0.0
    # float32 → int16
    pcm = (signal * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def _wav_to_mp3(wav: Path, mp3: Path) -> None:
    subprocess.run(["ffmpeg","-y","-i",str(wav),str(mp3)],
                   capture_output=True, check=True, timeout=30)


class TestSilenceDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="faz5_silence_"))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, duration=5.0, silences=None, clipping=False):
        wav = self.tmp/"test.wav"
        mp3 = self.tmp/"test.mp3"
        _make_sine_wav(wav, duration, silences=silences, clipping=clipping)
        _wav_to_mp3(wav, mp3)
        return mp3

    def test_no_silence(self):
        from scripts.qc_final_video import measure_audio_silence
        mp3 = self._make(duration=3.0)
        silences, err = measure_audio_silence(mp3)
        self.assertIsNone(err, f"sessizlik olcumu hatasi: {err}")
        # 2sn+ sessizlik olmamali
        long = [(s,e) for s,e in silences if e-s >= 2.0]
        self.assertEqual(long, [], f"Beklenmeyen sessizlikler: {silences}")

    def test_2s_silence_warning(self):
        from scripts.qc_final_video import measure_audio_silence
        mp3 = self._make(duration=5.0, silences=[(2.0, 4.2)])
        silences, err = measure_audio_silence(mp3)
        self.assertIsNone(err, f"sessizlik olcumu hatasi: {err}")
        self.assertTrue(any(e-s >= 2.0 for s,e in silences), f"2s+ sessizlik bekleniyordu: {silences}")

    def test_4s_silence_error(self):
        from scripts.qc_final_video import measure_audio_silence
        mp3 = self._make(duration=7.0, silences=[(1.0, 5.5)])
        silences, err = measure_audio_silence(mp3)
        self.assertIsNone(err, f"sessizlik olcumu hatasi: {err}")
        self.assertTrue(any(e-s >= 4.0 for s,e in silences))

    def test_nonexistent_file(self):
        from scripts.qc_final_video import measure_audio_silence
        silences, err = measure_audio_silence(self.tmp/"nonexistent.mp3")
        self.assertEqual(silences, [])
        self.assertEqual(err, "file_not_found")


class TestClippingDetection(unittest.TestCase):
    """Clipping tespiti icin astats ile clipped_samples sayisini olcen fonksiyon."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="faz5_clip_"))

    def tearDown(self):
        import shutil; shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, duration=3.0, clipping=False):
        wav = self.tmp/"test.wav"
        mp3 = self.tmp/"test.mp3"
        _make_sine_wav(wav, duration, clipping=clipping)
        _wav_to_mp3(wav, mp3)
        return mp3

    def test_no_clipping_normal_audio(self):
        from scripts.qc_final_video import measure_audio_clipping
        mp3 = self._make(clipping=False)
        ratio, db = measure_audio_clipping(mp3)
        self.assertIsNotNone(ratio)
        self.assertLess(ratio, 0.01, f"Normal ses clipping olmamali: {ratio*100:.2f}%")

    def test_hard_clipping_detected(self):
        from scripts.qc_final_video import measure_audio_clipping
        mp3 = self._make(clipping=True)
        ratio, db = measure_audio_clipping(mp3)
        self.assertIsNotNone(ratio)
        # Hard clipping'li seste yuksek oranli clipped samples olmali
        self.assertGreater(ratio, 0.01, f"Clipping tespit edilmedi: {ratio*100:.2f}%")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---- Gerçek edge-tts entegrasyon testi (ağ gerekli) ----
# Bu test gerçek Microsoft Edge TTS servisine bağlanır; ağ yoksa veya servis
# erişilemezse kendiliğinden skip olur.
class TestRealEdgeTTSIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="faz5_realedgetts_"))
        cls.audio_out = cls.tmp / "voice.mp3"
        cls.tts_engine = None
        cls.duration_sec = None
        cls.word_timestamps = None
        cls.error = None
        try:
            from content_engine import synthesize_voiceover
            cls.tts_engine, cls.duration_sec, cls.word_timestamps = synthesize_voiceover(
                text="Piri Reis haritayı çizdi. Güney Amerika kıyılarını gösterdi.",
                voice="tr-TR-AhmetNeural",
                rate="+4%",
                audio_out=cls.audio_out,
            )
        except Exception as e:
            cls.error = e

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _require_edge_tts(self):
        if self.error is not None:
            self.skipTest(f"edge-tts servisine erisilemedi: {self.error}")
        if not self.tts_engine or not self.tts_engine.startswith("edge-tts"):
            self.skipTest(f"edge-tts calismadi (engine={self.tts_engine})")

    def test_audio_file_exists(self):
        self._require_edge_tts()
        self.assertTrue(self.audio_out.exists())
        self.assertGreater(self.audio_out.stat().st_size, 1024, "ses dosyasi cok kucuk")

    def test_wordboundary_count_positive(self):
        self._require_edge_tts()
        self.assertIsInstance(self.word_timestamps, list)
        self.assertGreater(len(self.word_timestamps), 0, "WordBoundary sayisi 0 — edge-tts gercek donmedi")

    def test_ffprobe_duration_consistent(self):
        self._require_edge_tts()
        # ffprobe ile ses suresunu olc
        import subprocess
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(self.audio_out)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            probe_dur = float(r.stdout.strip())
            self.assertGreater(probe_dur, 1.0)
            self.assertLess(abs(probe_dur - self.duration_sec), 0.5,
                            f"ffprobe duration {probe_dur} ile timing {self.duration_sec} uyumsuz")

    def test_alignment_produces_real_timing(self):
        self._require_edge_tts()
        from src.media_processing.timing import align_scenes_to_timestamps
        script = {
            "audio_duration_sec": self.duration_sec,
            "tts_engine": self.tts_engine,
            "word_timestamps": self.word_timestamps,
            "visual_keywords": ["piri", "reis", "harita", "güney", "amerika"],
            "storyboard": [
                {"scene_id": 1, "narration": "Piri Reis haritayı çizdi.", "visual_query": "piri reis map"},
                {"scene_id": 2, "narration": "Güney Amerika kıyılarını gösterdi.", "visual_query": "south america map"},
            ],
        }
        r = align_scenes_to_timestamps(script)
        # Gerçek edge-tts çalıştığına göre gerçek timing üretilmeli
        self.assertEqual(r["timing_method"], "edge-tts-wordboundary",
                         f"beklenen edge-tts-wordboundary, fakat: {r.get('fallback_reason')}")
        for s in script["storyboard"]:
            self.assertIn("start_ms", s)
            self.assertIn("end_ms", s)
            self.assertIn("timing_method", s)
            self.assertEqual(s["timing_method"], "edge-tts-wordboundary")
        # Toplam görsel süre ≈ ses süresi
        total_visual = sum(s["end_ms"] - s["start_ms"] for s in script["storyboard"])
        self.assertLess(abs(total_visual - self.duration_sec * 1000.0), 5.0,
                        f"toplam gorsel {total_visual}ms, ses {self.duration_sec*1000}ms")

    def test_srt_contains_real_boundaries(self):
        self._require_edge_tts()
        from src.media_processing.timing import align_scenes_to_timestamps
        from content_engine import build_dynamic_shorts_srt
        script = {
            "audio_duration_sec": self.duration_sec,
            "tts_engine": self.tts_engine,
            "word_timestamps": self.word_timestamps,
            "visual_keywords": ["piri", "reis", "harita"],
            "storyboard": [
                {"scene_id": 1, "narration": "Piri Reis haritayı çizdi.", "visual_query": "q1"},
                {"scene_id": 2, "narration": "Güney Amerika kıyılarını gösterdi.", "visual_query": "q2"},
            ],
        }
        align_scenes_to_timestamps(script)
        bounds = [(s["start_ms"], s["end_ms"]) for s in script["storyboard"]
                  if "start_ms" in s and "end_ms" in s]
        srt = build_dynamic_shorts_srt(self.word_timestamps, words_per_cue=3,
                                       scene_boundaries=bounds if bounds else None)
        self.assertIn("-->", srt)
        # SRT içinde 00:00:00,000 ile bitiş zamanı olmalı
        import re as _re
        times = _re.findall(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", srt)
        self.assertGreater(len(times), 0)
