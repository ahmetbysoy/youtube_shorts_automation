"""Grounded Gemini Web draft tests; all networking and cookies are mocked."""
from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from scripts.gemini_web_story import (
    draft_to_script_metadata,
    fetch_topic_research,
    finish_topic_reservation,
    reserve_topic,
    validate_grounded_response,
    _topic_appears_in_recent_titles,
)


class TestGroundedGeminiStory(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tempdir.name) / "ledger.json"
        self.slug = "Venus"
        self.research = {
            "source_id": "venus",
            "title": "Venus facts",
            "url": "https://en.wikipedia.org/wiki/Venus",
            "accessed_at": "2026-11-18T12:00:00+00:00",
            "extract": (
                "Venus completes one rotation in about 243 Earth days. "
                "It completes one orbit around the Sun in about 225 Earth days. "
                "A Venus solar day lasts about 117 Earth days. "
                "Its thick atmosphere traps heat near the surface."
            ),
        }
        self.script = (
            "Bir gezegenin bir tam dönüşü, çevresindeki yörünge turundan daha uzun sürebilir. "
            "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar. "
            "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer. "
            "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür. "
            "Yoğun atmosferi yüzeye yakın ısıyı hapseder. "
            "Bu ölçüler Venüs gününü yılından daha uzun yapar; ancak güneş günü farklı hesaplanır. "
            "Bir gün doğumundan diğerine geçen süre, gezegenin dönüş süresinden ayrılır. "
            "Sen olsan bu tuhaf takvimde yaşamak ister miydin? Yorumlara yaz."
        )
        self.raw = {
            "topic_source_id": "venus",
            "topic": "Bilim",
            "title": "Venüs'te gün, yılından neden uzun? #Shorts",
            "description": "Venüs'te bir günün ölçüsü, düşündüğünden farklı.",
            "hook": "Bir gezegenin bir tam dönüşü, çevresindeki yörünge turundan daha uzun sürebilir.",
            "script_text": self.script,
            "cta_line": "Sen olsan bu tuhaf takvimde yaşamak ister miydin? Yorumlara yaz.",
            "thumbnail_prompt": "Dramatic Venus clouds, vertical 9:16 science thumbnail",
            "viral_hashtags": ["#venüs", "#gezegen", "#uzaybilimi"],
            "claims": [
                {
                    "claim": "Venüs dönüşünü yaklaşık 243 Dünya gününde tamamlar.",
                    "script_span": "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar.",
                    "evidence_quote": "Venus completes one rotation in about 243 Earth days.",
                },
                {
                    "claim": "Venüs'ün yörünge turu yaklaşık 225 Dünya günüdür.",
                    "script_span": "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer.",
                    "evidence_quote": "It completes one orbit around the Sun in about 225 Earth days.",
                },
                {
                    "claim": "Venüs güneş günü yaklaşık 117 Dünya günüdür.",
                    "script_span": "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür.",
                    "evidence_quote": "A Venus solar day lasts about 117 Earth days.",
                },
            ],
            "storyboard": [
                {
                    "scene_id": 1,
                    "narration": "Bir gezegenin bir tam dönüşü, çevresindeki yörünge turundan daha uzun sürebilir.",
                    "visual_query": "Venus planet slow rotation space",
                    "alternative_queries": ["Venus orbital path planet"],
                },
                {
                    "scene_id": 2,
                    "narration": "Venüs kendi eksenindeki dönüşünü yaklaşık 243 Dünya gününde tamamlar.",
                    "visual_query": "Venus rotation cloud surface",
                    "alternative_queries": ["Venus spinning planet animation"],
                },
                {
                    "scene_id": 3,
                    "narration": "Güneş çevresindeki turu ise yaklaşık 225 Dünya günü sürer.",
                    "visual_query": "Venus orbit around sun diagram",
                    "alternative_queries": ["solar system Venus orbit"],
                },
                {
                    "scene_id": 4,
                    "narration": "Venüs'ün güneş günü yaklaşık 117 Dünya günüdür.",
                    "visual_query": "Venus sunrise thick atmosphere",
                    "alternative_queries": ["Venus sunlight horizon clouds"],
                },
            ],
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def test_response_contract_checks_research_and_marks_semantic_review_partial(self):
        draft = validate_grounded_response(
            json.dumps(self.raw, ensure_ascii=False), topic_slug=self.slug, research=self.research
        )
        self.assertEqual(draft["fact_check"]["status"], "partial")
        self.assertEqual(len(draft["fact_check"]["claims"]), 3)
        self.assertTrue(draft["draft_only"])
        self.assertFalse(draft["publish"])
        script = draft_to_script_metadata(draft)
        self.assertEqual(script["visual_keywords"], [scene["visual_query"] for scene in self.raw["storyboard"]])
        self.assertEqual(len(script["sources"]), 1)

    def test_rejects_claim_quote_not_present_in_fetched_source(self):
        raw = json.loads(json.dumps(self.raw, ensure_ascii=False))
        raw["claims"][0]["evidence_quote"] = "A plausible but unsupported fact from nowhere."
        with self.assertRaisesRegex(ValueError, "kaynak metninde birebir"):
            validate_grounded_response(json.dumps(raw, ensure_ascii=False), topic_slug=self.slug, research=self.research)

    def test_rejects_storyboard_narration_not_in_script(self):
        raw = json.loads(json.dumps(self.raw, ensure_ascii=False))
        raw["storyboard"][1]["narration"] = "Bu cümle senaryo metninde yer almıyor."
        with self.assertRaisesRegex(ValueError, "narration senaryoda"):
            validate_grounded_response(json.dumps(raw, ensure_ascii=False), topic_slug=self.slug, research=self.research)

    def test_rejects_source_topic_mismatch(self):
        raw = json.loads(json.dumps(self.raw, ensure_ascii=False))
        raw["topic_source_id"] = "mars"
        with self.assertRaisesRegex(ValueError, "araştırma kaynağıyla eşleşmiyor"):
            validate_grounded_response(json.dumps(raw, ensure_ascii=False), topic_slug=self.slug, research=self.research)

    def test_recent_title_history_excludes_seed_topic_with_turkish_suffix(self):
        self.assertTrue(
            _topic_appears_in_recent_titles("Göbeklitepe", ["Göbeklitepe'nin gizemli taşları #Shorts"])
        )
        self.assertFalse(_topic_appears_in_recent_titles("Krakatoa", ["Venüs'te uzun bir gün"]))

    def test_topic_ledger_reservations_prevent_parallel_duplicate_and_commit(self):
        first, reservation = reserve_topic(["Venus", "Mars"], self.ledger)
        other, other_reservation = reserve_topic(["Venus", "Mars"], self.ledger)
        self.assertNotEqual(first, other)
        finish_topic_reservation(first, reservation, commit=True, ledger_path=self.ledger)
        finish_topic_reservation(other, other_reservation, commit=False, ledger_path=self.ledger)
        repeated, repeated_reservation = reserve_topic([first, "Jupiter"], self.ledger)
        self.assertEqual(repeated, "Jupiter")
        finish_topic_reservation(repeated, repeated_reservation, commit=False, ledger_path=self.ledger)

    def test_concurrent_topic_reservations_are_unique(self):
        topics = [f"topic-{index}" for index in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            reservations = list(pool.map(lambda _: reserve_topic(topics, self.ledger), range(8)))
        self.assertEqual(len({slug for slug, _ in reservations}), 8)
        for slug, reservation_id in reservations:
            finish_topic_reservation(slug, reservation_id, commit=False, ledger_path=self.ledger)

    def test_fetch_research_requires_real_wikipedia_response_and_canonical_url(self):
        response = Mock()
        response.url = "https://en.wikipedia.org/api/rest_v1/page/summary/Venus"
        response.json.return_value = {
            "title": "Venus",
            "extract": "Venus is a planet.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Venus"}},
        }
        session = Mock()
        session.get.return_value = response
        research = fetch_topic_research("Venus", session=session)
        self.assertEqual(research["title"], "Venus")
        self.assertIn("accessed_at", research)
        session.get.assert_called_once()

        response.url = "https://example.invalid/redirect"
        with self.assertRaisesRegex(ValueError, "alan adının dışına"):
            fetch_topic_research("Venus", session=session)


if __name__ == "__main__":
    unittest.main()
