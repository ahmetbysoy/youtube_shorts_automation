"""Faz 9 birim testleri: Konu bazlı affiliate link enjeksiyonu ve analitik geri bildirim döngüsü."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import content_engine


class TestFaz9MonetizationAndFeedback(unittest.TestCase):
    def test_space_topic_injects_telescope_affiliate_at_top_of_description(self) -> None:
        with patch.dict(os.environ, {"AFFILIATE_URL_SPACE": "https://ornek-magaza.tr/teleskop-pro"}, clear=False):
            raw = {
                "topic": "Bilim",
                "title": "Güneş Işığı Dünya'ya Gelene Kadar 8 Dakika Geçmiş Olur! #Shorts",
                "description": "Uzay ve ışık hızı gerçeği #uzay #shorts",
                "hook": "Şu anda Güneş aniden yok olsaydı ne olurdu?",
                "script_text": " ".join(["kelime"] * 65),
                "visual_keywords": ["sunlight", "space"],
            }
            norm = content_engine.validate_and_normalize_scenario(raw, "unit-test")
            self.assertEqual(norm["affiliate_link"], "https://ornek-magaza.tr/teleskop-pro")
            self.assertEqual(norm["affiliate_cta"], "Bu teleskobu incele: https://ornek-magaza.tr/teleskop-pro (Bu bir affiliate bağlantısıdır.)")
            self.assertTrue(norm["description"].startswith("Bu teleskobu incele: https://ornek-magaza.tr/teleskop-pro"))

    def test_history_topic_injects_book_affiliate_at_top_of_description(self) -> None:
        with patch.dict(os.environ, {"AFFILIATE_URL_HISTORY": "https://ornek-magaza.tr/antik-tarih-kitabi"}, clear=False):
            raw = {
                "topic": "Tarih",
                "title": "Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe! #Shorts",
                "description": "Göbeklitepe sırrı #tarih #shorts",
                "hook": "Piramitlerden eski tapınak Türkiye'de!",
                "script_text": " ".join(["kelime"] * 65),
                "visual_keywords": ["gobeklitepe", "temple"],
            }
            norm = content_engine.validate_and_normalize_scenario(raw, "unit-test")
            self.assertEqual(norm["affiliate_cta"], "Bu kitabı oku: https://ornek-magaza.tr/antik-tarih-kitabi (Bu bir affiliate bağlantısıdır.)")
            self.assertTrue(norm["description"].startswith("Bu kitabı oku: https://ornek-magaza.tr/antik-tarih-kitabi"))

    def test_analytics_feedback_injects_directive_into_llm_prompt_and_boosts_winner(self) -> None:
        feedback = {
            "winning_topic": "Uzay",
            "boost_active": True,
            "discarded_topics": ["Tarih"],
            "optimization_directive": "Önceki gün en yüksek performansı 'Uzay' gösterdi, yeni senaryoların %80'i Uzay/Fizik odaklı olsun.",
        }
        _, user_prompt = content_engine.build_llm_prompts(
            "İlginç Bilgiler", [], wiki_fact=None, analytics_feedback=feedback
        )
        self.assertIn("Önceki gün en yüksek performansı 'Uzay' gösterdi", user_prompt)
        self.assertIn("Tarih", user_prompt)


if __name__ == "__main__":
    unittest.main()
