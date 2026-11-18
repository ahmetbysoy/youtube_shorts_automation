"""Main content-engine integration tests; no Gemini session, TTS, network, or upload."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import content_engine
from scripts.validate_script_json import validate_payload


class TestGeminiWebContentEngine(unittest.TestCase):
    def setUp(self):
        self.script = (
            "Bir gezegenin dönüşü, Güneş çevresindeki turundan daha uzun sürebilir. "
            "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar. "
            "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer. "
            "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür. "
            "Yoğun atmosferi yüzeye yakın ısıyı hapseder. "
            "Bu ölçüler Venüs gününü yılından daha uzun yapar; ancak güneş günü farklı hesaplanır. "
            "Bir gün doğumundan diğerine geçen süre, gezegenin dönüş süresinden ayrılır. "
            "Sen olsan bu tuhaf takvimde yaşamak ister miydin? Yorumlara yaz."
        )
        self.source = {
            "id": "venus",
            "name": "Venus facts",
            "url": "https://en.wikipedia.org/wiki/Venus",
            "accessed_at": "2026-11-18T12:00:00+00:00",
        }
        self.scenes = [
            {"scene_id": 1, "narration": "Bir gezegenin dönüşü, Güneş çevresindeki turundan daha uzun sürebilir.",
             "visual_query": "Venus planet slow rotation", "alternative_queries": ["Venus orbit diagram"]},
            {"scene_id": 2, "narration": "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar.",
             "visual_query": "Venus rotating cloud surface", "alternative_queries": ["Venus atmosphere orbit"]},
            {"scene_id": 3, "narration": "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer.",
             "visual_query": "Venus orbit around sun", "alternative_queries": ["solar system planet orbit"]},
            {"scene_id": 4, "narration": "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür.",
             "visual_query": "Venus sunrise atmosphere", "alternative_queries": ["Venus sun horizon"]},
        ]
        self.claims = [
            {"claim": "Venüs dönüşünü 243 Dünya gününde tamamlar.",
             "script_span": "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar.",
             "evidence_quote": "Venus completes one rotation in about 243 Earth days."},
            {"claim": "Venüs'ün yörüngesi 225 gündür.",
             "script_span": "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer.",
             "evidence_quote": "It completes one orbit around the Sun in about 225 Earth days."},
            {"claim": "Güneş günü 117 Dünya günüdür.",
             "script_span": "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür.",
             "evidence_quote": "A Venus solar day lasts about 117 Earth days."},
        ]
        self.fact_check = {
            "status": "partial",
            "checked_at": "2026-11-18T12:00:00+00:00",
            "claims": [
                {"claim": c["claim"], "status": "partially_verified", "source_ids": ["venus"],
                 "notes": "Exact quote matches; semantic entailment not independently reviewed."}
                for c in self.claims
            ],
        }
        self.draft = {
            "topic": "Bilim",
            "title": "Venüs'te gün, yılından neden uzun? #Shorts",
            "description": "Venüs'te bir günün ölçüsü düşündüğünden farklı.",
            "source": "Venus facts — https://en.wikipedia.org/wiki/Venus",
            "hook": "Bir gezegenin dönüşü, Güneş çevresindeki turundan daha uzun sürebilir.",
            "script_text": self.script,
            "cta_line": "Sen olsan bu tuhaf takvimde yaşamak ister miydin? Yorumlara yaz.",
            "thumbnail_prompt": "Dramatic Venus clouds, vertical science thumbnail",
            "viral_hashtags": ["#venüs", "#gezegen", "#uzaybilimi"],
            "visual_keywords": [scene["visual_query"] for scene in self.scenes],
            "sources": [self.source],
            "fact_check": self.fact_check,
            "storyboard": self.scenes,
            "claims": self.claims,
            "topic_source_id": "venus",
            "prompt_version": "gemini-web-story-v1",
        }

    def test_gemini_web_scenario_normalizes_and_preserves_grounding_metadata(self):
        async def fake_generate(*args, **kwargs):
            return self.draft, ["fake-cookie"]

        with patch("scripts.gemini_web_text_probe.generate_text_scenario", side_effect=fake_generate), \
             patch("content_engine.asyncio.run") as run:
            run.side_effect = lambda coroutine: (coroutine.close(), (self.draft, ["fake-cookie"]))[1]
            scenario = content_engine.generate_gemini_web_scenario("", ["Recent title"])
        self.assertEqual(scenario["provider"], "gemini-web-session")
        self.assertEqual(scenario["fact_check"]["status"], "partial")
        self.assertEqual(scenario["sources"], [self.source])
        self.assertEqual(scenario["storyboard"], self.scenes)
        self.assertEqual(scenario["prompt_version"], "gemini-web-story-v1")
        self.assertEqual(scenario["visual_keywords"], [scene["visual_query"] for scene in self.scenes])

    def test_timeout_expired_session_429_and_malformed_json_fall_back_without_api_calls(self):
        failures = (
            ("timeout", TimeoutError("synthetic timeout detail")),
            ("expired_session", RuntimeError("synthetic expired session detail")),
            ("http_429", RuntimeError("synthetic HTTP 429 detail")),
            ("malformed_json", json.JSONDecodeError("synthetic malformed JSON detail", "{", 1)),
        )
        fallback = {"title": "fallback title", "provider": "local-fallback-matrix-1"}
        for label, failure in failures:
            with self.subTest(mode=label), \
                 patch.object(content_engine, "load_recent_titles", return_value=[]), \
                 patch.object(content_engine, "load_analytics_feedback", return_value={}), \
                 patch.object(content_engine, "generate_gemini_web_scenario", side_effect=failure), \
                 patch.object(content_engine, "pick_fallback_scenario", return_value=fallback), \
                 patch.object(content_engine, "save_recent_title"), \
                 patch.object(content_engine, "call_groq_llm") as groq, \
                 patch.object(content_engine, "call_gemini_llm") as gemini, \
                 patch.dict("os.environ", {"GROQ_API_KEY": "not-used", "GEMINI_API_KEY": "not-used"}):
                result = content_engine.generate_scenario(gemini_web_only=True)
            self.assertIs(result, fallback)
            groq.assert_not_called()
            gemini.assert_not_called()

    def test_pipeline_serializes_grounding_storyboard_and_passes_v2_schema(self):
        scenario = content_engine.validate_and_normalize_scenario(self.draft, "gemini-web-session")
        scenario.update({
            "sources": [self.source],
            "fact_check": self.fact_check,
            "storyboard": self.scenes,
            "claims": self.claims,
            "topic_source_id": "venus",
            "prompt_version": "gemini-web-story-v1",
        })
        timestamps = [{"word": "Venüs", "start_ms": 0, "end_ms": 250}]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(content_engine, "generate_scenario", return_value=scenario), \
                 patch.object(content_engine, "synthesize_voiceover", return_value=("test-tts", 30.0, timestamps)):
                payload = content_engine.run_content_pipeline(
                    audio_out=root / "voice.mp3",
                    txt_out=root / "script.txt",
                    json_out=root / "script.json",
                    srt_out=root / "voice.srt",
                )
            saved = json.loads((root / "script.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["fact_check"]["status"], "partial")
        self.assertEqual(saved["storyboard"], self.scenes)
        self.assertEqual(saved["sources"], [self.source])
        self.assertEqual(saved["prompt_version"], "gemini-web-story-v1")
        self.assertEqual(validate_payload(payload), [])


if __name__ == "__main__":
    unittest.main()
