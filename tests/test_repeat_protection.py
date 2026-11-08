"""Birim testleri: FAZ 13.4 tekrar korumasi (baslik benzerlik kontrolu)."""

import sys
import unittest
from unittest.mock import MagicMock

# content_engine icindeki harici bagimliliklari yalnizca kurulu degilse mock'la
for _mod in ("edge_tts", "requests"):
    try:
        __import__(_mod)
    except ImportError:
        sys.modules[_mod] = MagicMock()

sys.path.insert(0, "/home/user/yts")

from content_engine import (  # noqa: E402
    is_similar_to_recent,
    title_tokens,
)


class TestTitleTokens(unittest.TestCase):
    """title_tokens() fonksiyonu icin testler."""

    def test_basic_tokens(self):
        tokens = title_tokens("Piramitlerden 7 Bin Yil Daha Eski Tapinak: Gobeklitepe! #Shorts")
        self.assertIn("gobeklitepe", tokens)
        self.assertIn("piramitlerden", tokens)
        self.assertIn("tapinak", tokens)
        self.assertIn("eski", tokens)
        # Stopword'ler cikarilmalidir
        self.assertNotIn("bir", tokens)
        self.assertNotIn("daha", tokens)
        self.assertNotIn("kadar", tokens)
        self.assertNotIn("shorts", tokens)

    def test_turkce_karakter_normalize(self):
        tokens = title_tokens("Güneş Dünyanın Yüzde 99.8'ini Oluşturuyor! #Shorts")
        self.assertIn("gunes", tokens)
        # "Dünyanın" normalize edilirken "ı"->"i" dusunce "dunyanin" cikar;
        # "dunyanin" _TITLE_STOPWORDS listesinde oldugu icin tokenlerden filtrelenir.
        self.assertNotIn("dunyanin", tokens)
        self.assertIn("yuzde", tokens)
        self.assertIn("olusturuyor", tokens)

    def test_short_words_filtered(self):
        tokens = title_tokens("Ay'a giris! #Shorts")
        # "giris" 5 harfli ve stopword degil, kalabilir; "ay" ve "a" filtrelenmeli
        self.assertNotIn("ay", tokens)
        self.assertNotIn("a", tokens)

    def test_empty_string(self):
        self.assertEqual(title_tokens(""), set())
        self.assertEqual(title_tokens("   "), set())


class TestIsSimilarToRecent(unittest.TestCase):
    """is_similar_to_recent() fonksiyonu icin testler."""

    def test_identical_title_is_similar(self):
        self.assertTrue(is_similar_to_recent("Gobeklitepe! #Shorts", ["Gobeklitepe! #Shorts"]))

    def test_completely_different_topic_is_not_similar(self):
        self.assertFalse(
            is_similar_to_recent(
                "Venus'te Bir Gun, Bir Yildan Daha Uzundur! #Shorts",
                ["Gobeklitepe! #Shorts"],
            )
        )

    def test_single_common_token_is_not_similar(self):
        self.assertFalse(
            is_similar_to_recent(
                "Piramitlerden 7 Bin Yil Daha Eski Tapinak: Gobeklitepe! #Shorts",
                ["Gobeklitepe! #Shorts"],
            )
        )

    def test_high_similarity_is_detected(self):
        self.assertTrue(
            is_similar_to_recent("Gobeklitepe Tapinagini Kesfedin! #Shorts", ["Gobeklitepe! #Shorts"])
        )

    def test_empty_recent_list_is_not_similar(self):
        self.assertFalse(is_similar_to_recent("Herhangi bir baslik", []))

    def test_case_insensitive(self):
        self.assertTrue(
            is_similar_to_recent("gobeklitepe! #shorts", ["GOBEKLITEPE! #SHORTS"])
        )

    def test_multiple_recent_titles(self):
        self.assertFalse(
            is_similar_to_recent(
                "Tamamen Baska Bir Konu Hakkinda! #Shorts",
                ["Gobeklitepe! #Shorts", "Venus Gezegni! #Shorts", "Napolyon Tarihi! #Shorts"],
            )
        )
        self.assertTrue(
            is_similar_to_recent(
                "Gobeklitepe Tapinagini Anlatiyorum! #Shorts",
                ["Gobeklitepe! #Shorts", "Venus Gezegni! #Shorts"],
            )
        )


if __name__ == "__main__":
    unittest.main()
