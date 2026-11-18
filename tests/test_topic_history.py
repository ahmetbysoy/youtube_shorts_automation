"""Topic history CAS, similarity, fail-closed, and release tests."""
from __future__ import annotations

import base64
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

from scripts.topic_history import (
    GitHubContentsStore,
    finalize_candidate,
    load_recent_titles,
    reserve_candidate,
)


class TestTopicHistory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / ".used_topics.json"
        self.path.write_text("[]", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_same_subject_is_blocked_under_a_different_title(self):
        first = reserve_candidate(
            "Venüs'te Takvimler Neden Farklı?",
            {"topic": "Venüs", "topic_source_id": "venus", "script_text": "Venüs dönüşünü anlatan içerik."},
            path=self.path,
            reservation_id="first",
        )
        self.assertEqual(first["title"], "Venüs'te Takvimler Neden Farklı?")
        with self.assertRaisesRegex(ValueError, "same_normalized_topic"):
            reserve_candidate("Venüs'ün Gizemli Günü", {"topic": "Venüs", "topic_source_id": "venus"}, path=self.path)

    def test_same_claims_with_different_words_are_blocked(self):
        reserve_candidate(
            "Bir Gezegenin Eksen Hareketi",
            {"topic": "Astronomi", "claims": [{"claim": "Venus completes one rotation in 243 Earth days"}]},
            path=self.path,
        )
        with self.assertRaisesRegex(ValueError, "same_core_claim"):
            reserve_candidate(
                "Venüs'ün Bir Dönüşü 243 Dünya Günü Sürer",
                {"topic": "Uzay", "claims": [{"claim": "Venüs 243 Dünya gününde bir eksen dönüşü yapar"}]},
                path=self.path,
            )

    def test_concurrent_same_topic_reservation_is_atomic(self):
        def reserve(index):
            try:
                return reserve_candidate(
                    "Venüs'te farklı bir başlık",
                    {"topic": "Venüs", "topic_source_id": "venus"},
                    path=self.path,
                    reservation_id=f"parallel-{index}",
                )
            except ValueError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(8)))
        successful = [item for item in results if item]
        self.assertEqual(len(successful), 1)
        self.assertEqual(successful[0]["topic_key"], "venus")

    def test_failed_generation_releases_reservation_and_retry_is_allowed(self):
        item = reserve_candidate("Mars'ın atmosferi", {"topic": "Mars"}, path=self.path, reservation_id="failure")
        finalize_candidate("failure", commit=False, path=self.path)
        self.assertNotIn(item["title"], load_recent_titles(self.path))
        retry = reserve_candidate("Mars'ın atmosferi", {"topic": "Mars"}, path=self.path, reservation_id="retry")
        self.assertEqual(retry["reservation_id"], "retry")

    def test_successful_finalize_persists_title_and_topic_identity(self):
        reserve_candidate("Krakatoa'nın patlaması", {"topic": "Krakatoa"}, path=self.path, reservation_id="success")
        finalize_candidate("success", commit=True, path=self.path)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIn("Krakatoa'nın patlaması", stored["used_titles"])
        self.assertTrue(any(record["topic_key"] == "krakatoa" for record in stored["used_records"]))

    def test_unreadable_history_fails_closed(self):
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fail-closed"):
            load_recent_titles(self.path)
        with self.assertRaisesRegex(ValueError, "fail-closed"):
            reserve_candidate("Yeni konu", {"topic": "Yeni"}, path=self.path)

    def test_contents_api_sha_conflict_reloads_and_retries_without_losing_history(self):
        legacy = ["Önceki kalıcı başlık"]
        encoded = base64.b64encode(json.dumps(legacy, ensure_ascii=False).encode()).decode()
        get1 = Mock(status_code=200)
        get1.json.return_value = {"content": encoded, "sha": "sha-old"}
        # Another writer commits an additional entry before our retry reads again.
        competing = ["Önceki kalıcı başlık", "Eşzamanlı yazarın başlığı"]
        encoded2 = base64.b64encode(json.dumps(competing, ensure_ascii=False).encode()).decode()
        get2 = Mock(status_code=200)
        get2.json.return_value = {"content": encoded2, "sha": "sha-new"}
        put_conflict = Mock(status_code=409)
        put_success = Mock(status_code=201)
        session = Mock()
        session.get.side_effect = [get1, get2]
        session.put.side_effect = [put_conflict, put_success]
        store = GitHubContentsStore("owner/repo", "not-a-real-secret", session=session)
        reserve_candidate("Yeni başlık", {"topic": "Yeni konu"}, path=self.path, store=store, reservation_id="cas")
        self.assertEqual(session.get.call_count, 2)
        self.assertEqual(session.put.call_count, 2)
        payload = session.put.call_args_list[1].kwargs["json"]
        self.assertEqual(payload["sha"], "sha-new")
        stored = json.loads(base64.b64decode(payload["content"]))
        self.assertIn("Önceki kalıcı başlık", stored["used_titles"])
        self.assertIn("Eşzamanlı yazarın başlığı", stored["used_titles"])
        self.assertEqual(len(stored["pending"]), 1)

    def test_github_history_read_failure_is_fail_closed(self):
        response = Mock(status_code=500)
        session = Mock(get=Mock(return_value=response))
        store = GitHubContentsStore("owner/repo", "unused", session=session)
        with self.assertRaisesRegex(RuntimeError, "fail-closed"):
            reserve_candidate("Başlık", {"topic": "Konu"}, path=self.path, store=store)


if __name__ == "__main__":
    unittest.main()
