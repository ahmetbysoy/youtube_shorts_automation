"""Phase 3 fact checks: deterministic, no paid APIs, all network calls mocked."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

import requests

from scripts.gemini_web_story import fetch_topic_research
from scripts.semantic_fact_check import assess_claim, extract_numeric_facts


class TestPhase3FactChecks(unittest.TestCase):
    def test_semantic_relation_and_exact_quote_are_independent(self):
        evidence = "Venus completes one rotation in about 243 Earth days."
        result = assess_claim("Venüs kendi ekseninde yaklaşık 243 Dünya gününde döner.", evidence, evidence)
        self.assertTrue(result["quote_match"])
        self.assertEqual(result["semantic_support"], "verified")
        self.assertEqual(result["numeric_checks"][0]["dimension"], "duration_days")

    def test_unrelated_relation_is_rejected_even_when_numbers_match(self):
        evidence = "Venus completes one orbit around the Sun in about 243 Earth days."
        result = assess_claim("Venüs kendi ekseninde 243 Dünya gününde döner.", evidence, evidence)
        self.assertEqual(result["quote_match"], True)
        self.assertEqual(result["semantic_support"], "rejected")
        self.assertIn("relation_mismatch", result["reason_codes"])

    def test_number_mismatch_is_rejected(self):
        evidence = "Venus completes one rotation in about 243 Earth days."
        result = assess_claim("Venüs bir dönüşü 242 Dünya gününde tamamlar.", evidence, evidence)
        self.assertEqual(result["semantic_support"], "rejected")
        self.assertIn("numeric_value_or_unit_mismatch", result["reason_codes"])

    def test_date_and_unit_mismatches_are_deterministic(self):
        date = assess_claim("The event occurred in 1985.", "The event occurred in 1984.", "The event occurred in 1984.")
        self.assertEqual(date["semantic_support"], "rejected")
        speed = assess_claim("The vehicle travels at 100 km/h.", "The vehicle travels at 100 miles per hour.", "The vehicle travels at 100 miles per hour.")
        self.assertEqual(speed["semantic_support"], "rejected")
        equivalent = assess_claim(
            "The car speed is 100 km/h.",
            "The car speed is 62.137119 mph.",
            "The car speed is 62.137119 mph.",
        )
        self.assertTrue(equivalent["numeric_checks"][0]["matched"])
        percent = assess_claim("The rate is 40 percent.", "The rate is 40 days.", "The rate is 40 days.")
        self.assertEqual(percent["semantic_support"], "rejected")
        self.assertEqual(extract_numeric_facts("2 miles per hour")[0]["dimension"], "speed_kmh")

    def test_unavailable_empty_and_broken_sources_never_verify(self):
        for source in ("", None):
            result = assess_claim("Venus rotates", "Venus rotates", source, source_available=False)
            self.assertEqual(result["semantic_support"], "unavailable")
        response = Mock()
        response.url = "https://en.wikipedia.org/api/rest_v1/page/summary/Venus"
        response.raise_for_status.return_value = None
        response.json.return_value = {"title": "Venus", "extract": "", "content_urls": {}}
        with self.assertRaisesRegex(ValueError, "başlık, içerik veya kaynak URL"):
            fetch_topic_research("Venus", session=Mock(get=Mock(return_value=response)))

    def test_inaccessible_source_url_is_rejected(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("404")
        with self.assertRaisesRegex(ValueError, "Araştırma kaynağı alınamadı"):
            fetch_topic_research("Venus", session=Mock(get=Mock(return_value=response)))

    def test_page_content_canonical_identity_must_match_source_url(self):
        summary = Mock(url="https://en.wikipedia.org/api/rest_v1/page/summary/Venus", status_code=200)
        summary.json.return_value = {
            "title": "Venus", "extract": "Venus is a planet.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Venus"}},
        }
        page = Mock(url="https://en.wikipedia.org/wiki/Venus", status_code=200)
        page.text = '<title>Venus - Wikipedia</title><link rel="canonical" href="https://en.wikipedia.org/wiki/Mars" />'
        with self.assertRaisesRegex(ValueError, "kanonik sayfa kimliği"):
            fetch_topic_research("Venus", session=Mock(get=Mock(side_effect=[summary, page])))

    def test_schema_accepts_new_v2_fact_check_states_and_old_states(self):
        import json
        from pathlib import Path
        schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "script.schema.json").read_text())
        fact_status = schema["$defs"]["currentV2"]["properties"]["fact_check"]["properties"]["status"]["enum"]
        claim_status = schema["$defs"]["claim"]["properties"]["status"]["enum"]
        for value in ("verified", "partial", "rejected", "unavailable"):
            self.assertIn(value, fact_status)
            self.assertIn(value, claim_status)
        self.assertIn("passed", fact_status)
        self.assertIn("partially_verified", claim_status)


if __name__ == "__main__":
    unittest.main()
