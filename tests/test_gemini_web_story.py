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
            "source_validation": {"status": "verified", "content_matches_page": True, "http_status": 200},
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

    def test_response_contract_checks_exact_quotes_semantic_support_and_partial_rollup(self):
        draft = validate_grounded_response(
            json.dumps(self.raw, ensure_ascii=False), topic_slug=self.slug, research=self.research
        )
        self.assertEqual(draft["fact_check"]["status"], "verified")
        self.assertEqual(len(draft["fact_check"]["claims"]), 3)
        self.assertTrue(all(item["quote_match"] for item in draft["fact_check"]["claims"]))
        self.assertTrue(all(item["semantic_support"] == "verified" for item in draft["fact_check"]["claims"]))
        self.assertEqual(draft["fact_check"]["verification_method"], "deterministic_lexical_numeric_v1")
        self.assertTrue(draft["draft_only"])
        self.assertFalse(draft["publish"])
        script = draft_to_script_metadata(draft)
        self.assertEqual(script["visual_keywords"], [scene["visual_query"] for scene in self.raw["storyboard"]])
        self.assertEqual(len(script["sources"]), 1)
        self.assertTrue(script["sources"][0]["validation"]["content_matches_page"])
        self.assertEqual(script["sources"][0]["validation"]["http_status"], 200)

    def test_rejects_malformed_model_json_before_schema_or_network_side_effects(self):
        with self.assertRaises(json.JSONDecodeError):
            validate_grounded_response("{not-valid-json}", topic_slug=self.slug, research=self.research)

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
        response.status_code = 200
        response.json.return_value = {
            "title": "Venus",
            "extract": "Venus is a planet.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Venus"}},
        }
        page = Mock()
        page.url = "https://en.wikipedia.org/wiki/Venus"
        page.status_code = 200
        page.text = '<html><head><title>Venus - Wikipedia</title><link rel="canonical" href="https://en.wikipedia.org/wiki/Venus" /></head></html>'
        session = Mock()
        session.get.side_effect = [response, page]
        research = fetch_topic_research("Venus", session=session)
        self.assertEqual(research["title"], "Venus")
        self.assertIn("accessed_at", research)
        self.assertTrue(research["source_validation"]["content_matches_page"])
        self.assertEqual(session.get.call_count, 2)

        response.url = "https://example.invalid/redirect"
        session.get.side_effect = None
        session.get.return_value = response
        with self.assertRaisesRegex(ValueError, "alan adının dışına"):
            fetch_topic_research("Venus", session=session)

    def test_wiki_seed_topics_resolve_against_en_wikipedia(self):
        """Faz4K: WIKI_SEED_TOPICS içindeki her slug en.wikipedia.org API'de
        çözülebilmeli. Türkçe başlıklar (Mariana_Çukuru → Mariana_Trench gibi)
        English Wikipedia'da 404 döndürürse Gemini Web ValueError ile düşer."""
        import requests
        import urllib.parse
        from content_engine import WIKI_SEED_TOPICS
        url_template = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
        failed = []
        for slug in WIKI_SEED_TOPICS:
            url = url_template.format(urllib.parse.quote(slug.replace("_", " "), safe=""))
            try:
                r = requests.get(url, headers={"User-Agent": "ShortsResearchBot/1.0 (test)"},
                                 timeout=(5, 15))
                if r.status_code != 200:
                    failed.append((slug, r.status_code))
            except Exception as exc:
                failed.append((slug, f"exc:{type(exc).__name__}"))
        self.assertEqual(failed, [],
                         f"Şu seed'ler en.wikipedia.org'da çözümlenemedi: {failed}")
        self.assertGreaterEqual(len(WIKI_SEED_TOPICS), 6,
                                "En az 6 çalışır seed konu olmalı")


if __name__ == "__main__":
    unittest.main()
