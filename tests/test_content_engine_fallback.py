"""Uçtan uca test: content_engine fallback modu (Force Fallback).

Kurulu edge_tts / requests bağımlılıkları kullanılır; API anahtarı olmadan
yedek senaryo havuzunun (%30 Jaccard tekrar korumasıyla) doğru çalışıp
çalışmadığı ve .used_topics.json'ın güncellendiği doğrulanır.
"""

import json
import sys
import unittest
from pathlib import Path

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


class TestFallbackReserveSafety(unittest.TestCase):  # type: ignore[name-defined]
    """45069984817 dersi: pick filtresi ile reserve_candidate semantiği uyumsuzdu.

    Aynı 15dk slotu + sabit havuz determinizmi, 3 fallback denemesini de AYNI
    çarpan başlığa kilitliyordu. Bu sınıf: (1) attempt rotasyonu, (2) ledger
    topic_key/norm eleme, (3) retry yardımcısının duplicate-redlerine dayanıklılığı.
    """

    def setUp(self):
        self.original_history = HISTORY_FILE.read_text(encoding="utf-8") if HISTORY_FILE.exists() else "[]"
        import content_engine as ce
        self.ce = ce

    def tearDown(self):
        HISTORY_FILE.write_text(self.original_history, encoding="utf-8")

    def test_pick_fallback_attempt_rotates_titles(self):
        """Aynı 15dk bucket'ında attempt=0..5 FARKLI başlıklar döndürmeli."""
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        seen = [
            pick_fallback_scenario([], channel_id="1", attempt=a)["title"]
            for a in range(6)
        ]
        self.assertEqual(
            len(set(seen)), 6,
            f"attempt rotasyonu tekrar eden başlık verdi: {seen}",
        )

    def test_pick_fallback_filters_ledger_topic_key(self):
        """Ledger'da topic_key'i zaten kullanılmış senaryo pick edilmemeli."""
        from scripts.topic_history import _record as th_record, _norm as th_norm
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        target = None
        for item in self.ce.FALLBACK_SCENARIOS:
            rec = th_record(item["title"], item)
            if rec["topic_key"]:
                target = (item, rec)
                break
        self.assertIsNotNone(target, "topic_key'i dolu bir senaryo yok")
        item, rec = target
        ledger = {
            "version": 2,
            "used_titles": [item["title"]],
            "used_records": [rec],
            "pending": [],
        }
        HISTORY_FILE.write_text(json.dumps(ledger), encoding="utf-8")
        target_key = rec["topic_key"]
        for a in range(6):
            scenario = pick_fallback_scenario([], channel_id="1", attempt=a)
            cand = th_record(scenario["title"], scenario)
            self.assertNotEqual(
                cand["topic_key"], target_key,
                f"attempt={a}: pick, ledger topic_key'i ile çarpışan senaryoyu verdi",
            )
            self.assertNotEqual(
                th_norm(scenario["title"]), th_norm(item["title"]),
                f"attempt={a}: pick, ledger başlığının normalize eşini verdi",
            )

    def test_retry_helper_survives_duplicate_rejections(self):
        """save hep duplicate reddederse 8 deneme sonrası RuntimeError; 8 farklı pick."""
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        picked_attempts = []
        real_pick = self.ce.pick_fallback_scenario

        def spy_pick(recent_titles, **kwargs):
            picked_attempts.append(kwargs.get("attempt"))
            return real_pick(recent_titles, **kwargs)

        def always_dup(title, scenario=None):
            raise ValueError("Konu tekrarı engellendi (exact_title); yeni konu seçilmeli.")

        real_save = self.ce.save_recent_title
        self.ce.pick_fallback_scenario = spy_pick
        self.ce.save_recent_title = always_dup
        try:
            with self.assertRaises(RuntimeError):
                self.ce._pick_and_reserve_with_retry([], "1", None, attempts=8)
        finally:
            self.ce.pick_fallback_scenario = real_pick
            self.ce.save_recent_title = real_save
        self.assertEqual(picked_attempts, [0, 1, 2, 3, 4, 5, 6, 7], "attempt rotasyonu bozuldu")

    def test_retry_helper_recovers_on_second_attempt(self):
        """İlk rezervasyon reddi sonrası attempt=1'den BAŞARILI senaryo dönmeli."""
        HISTORY_FILE.write_text("[]", encoding="utf-8")
        state = {"n": 0}

        def first_dup(title, scenario=None):
            state["n"] += 1
            if state["n"] == 1:
                raise ValueError("Konu tekrarı engellendi (same_normalized_topic); yeni konu seçilmeli.")

        real_save = self.ce.save_recent_title
        self.ce.save_recent_title = first_dup
        try:
            scenario = self.ce._pick_and_reserve_with_retry([], "1", None, attempts=8)
        finally:
            self.ce.save_recent_title = real_save
        self.assertEqual(state["n"], 2, "İkinci deneme rezervasyonu yapılmadı")
        self.assertIn("title", scenario)


if __name__ == "__main__":
    import unittest
    unittest.main()
