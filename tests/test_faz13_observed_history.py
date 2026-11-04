"""FAZ 13.4 kaynaklı geçmiş: kullanıcı kanalından gerçek anlık görüntü testleri."""
import json
import unittest
from pathlib import Path

from scripts.build_verified_history import build_history

ROOT = Path(__file__).resolve().parent.parent
FEED = ROOT / "docs/evidence/public_feed_2026-11-04.json"
REPORT = ROOT / "docs/evidence/pruner_report_2026-11-04_1711.json"


class ObservedHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(FEED.read_text(encoding="utf-8"))
        cls.report = json.loads(REPORT.read_text(encoding="utf-8"))
        cls.history = build_history(cls.feed, cls.report)
        cls.by_id = {r["video_id"]: r for r in cls.history["records"]}

    def test_real_sources_are_merged_by_video_id(self):
        self.assertEqual(self.history["channel_id"], self.report["channel_id"])
        expected = {v["video_id"] for v in self.feed["videos"]}
        for group in ("protected", "targets", "deleted"):
            expected.update(v["videoId"] for v in self.report[group])
        self.assertEqual(set(self.by_id), expected)
        self.assertEqual(self.history["record_count"], len(expected))

    def test_duplicate_antikythera_is_not_collapsed(self):
        older = self.by_id["BlrZMXlIbU0"]
        newer = self.by_id["T_yIHvyUY2Y"]
        self.assertEqual(older["latest_observed_title"], newer["latest_observed_title"])
        self.assertNotEqual(older["video_id"], newer["video_id"])

    def test_report_observation_is_not_fabricated_publication_time(self):
        newer = self.by_id["T_yIHvyUY2Y"]
        self.assertTrue(newer["observations"])
        self.assertTrue(all("published_at" not in o for o in newer["observations"]))
        self.assertEqual(newer["observations"][0]["observed_at"], self.report["finished_at"])

    def test_feed_publication_time_is_preserved(self):
        old = self.by_id["BlrZMXlIbU0"]
        feed_obs = next(o for o in old["observations"] if o["source"] == "youtube_atom")
        feed_item = next(v for v in self.feed["videos"] if v["video_id"] == old["video_id"])
        self.assertEqual(feed_obs["published_at"], feed_item["published"])


if __name__ == "__main__":
    unittest.main()
