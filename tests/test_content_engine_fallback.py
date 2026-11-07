"""Uçtan uca test: content_engine fallback modu (Force Fallback).

edge_tts / requests modülleri mock'lanır; API anahtarı olmadan
yedek senaryo havuzunun (%30 Jaccard tekrar korumasıyla) doğru çalışıp
çalışmadığı ve .used_topics.json'ın güncellendiği doğrulanır.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Harici bağımlılıkları mock'la (content_engine import ederken çökmesin)
sys.modules["edge_tts"] = MagicMock()
sys.modules["requests"] = MagicMock()

sys.path.insert(0, "/home/user/yts")

from content_engine import (  # noqa: E402
    generate_scenario,
    load_recent_titles,
    pick_fallback_scenario,
    save_recent_title,
    HISTORY_FILE,
)


class TestContentEngineFallback(unittest.TestCase):  # type: ignore[name-defined]
    """Fallback modu içerik üretimi testleri."""

    def setUp(self):
        """Her testten önce .used_topics.json'ı temiz bir kopya ile başlat."""
        self.original_history = HISTORY_FILE.read_text(encoding="utf-8") if HISTORY_FILE.exists() else "[]"

    def tearDown(self):
        """Test sonrası .used_topics.json'ı eski haline döndür."""
        HISTORY_FILE.write_text(self.original_history, encoding="utf-8")

    def test_generate_scenario_fallback_produces_scenario(self):
        """force_fallback=True ile geçerli bir senaryo üretilmeli."""
        scenario = generate_scenario(concept="İlginç Bilgiler", force_fallback=True, channel_id="1")
        self.assertIsInstance(scenario, dict)
        self.assertIn("title", scenario)
        self.assertIn("script_text", scenario)
        self.assertIn("topic", scenario)
        self.assertTrue(scenario["title"].endswith("#Shorts"), f"Başlık #Shorts ile bitmiyor: {scenario['title']}")
        self.assertGreaterEqual(scenario["word_count"], 45)
        self.assertLessEqual(scenario["word_count"], 110)

    def test_fallback_title_not_similar_to_recent(self):
        """Üretilen başlık, geçmiştekiyle %30'den fazla benzer olmamalı."""
        recent = load_recent_titles()
        scenario = generate_scenario(concept="İlginç Bilgiler", force_fallback=True, channel_id="1")
        new_title = scenario["title"]
        from content_engine import is_similar_to_recent  # noqa: E402
        self.assertFalse(
            is_similar_to_recent(new_title, recent),
            f"Yeni başlık geçmişle çok benzer: '{new_title}'",
        )

    def test_history_saved_and_limited_to_25(self):
        """Üretilen başlık .used_topics.json'a eklenmeli; max 25 kayıt tutulmalı."""
        # 25 tane tekrarsız başlık ekleyip 26.'sını dene
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        titles = [f"Test Başlığı {i} #Shorts" for i in range(25)]
        for t in titles:
            save_recent_title(t)
        history = load_recent_titles()
        self.assertEqual(len(history), 25)

        # 26. başlık eklendiğinde en eski çıkmalı
        save_recent_title("Yeni Test Başlığı #Shorts")
        history = load_recent_titles()
        self.assertEqual(len(history), 25)
        self.assertIn("Yeni Test Başlığı #Shorts", history)
        self.assertNotIn("Test Başlığı 0 #Shorts", history)

    def test_pick_fallback_scenario_respects_history(self):
        """pick_fallback_scenario, geçmişteki başlıkları filtrelemeli."""
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        # Tüm havuzu geçmişe ekle
        from content_engine import FALLBACK_SCENARIOS  # noqa: E402
        all_titles = [s["title"] for s in FALLBACK_SCENARIOS]
        for t in all_titles:
            save_recent_title(t)
        # Havuz sıfırlanmalı (10'dan az kalınca tüm havuz kullanılır)
        scenario = pick_fallback_scenario(load_recent_titles(), channel_id="1")
        self.assertIsInstance(scenario, dict)
        self.assertIn("title", scenario)

    def test_scenario_has_required_fields(self):
        """Senaryoda gerekli tüm alanlar bulunmalı."""
        scenario = generate_scenario(concept="Tarih", force_fallback=True, channel_id="1")
        required = ["title", "script_text", "topic", "description", "visual_keywords", "thumbnail_prompt", "viral_hashtags"]
        for field in required:
            self.assertIn(field, scenario, f"Eksik alan: {field}")
        self.assertIsInstance(scenario["visual_keywords"], list)
        self.assertGreaterEqual(len(scenario["visual_keywords"]), 1)
        self.assertEqual(len(scenario["viral_hashtags"]), 3)


if __name__ == "__main__":
    import unittest
    unittest.main()
