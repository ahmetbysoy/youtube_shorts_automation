import unittest
from datetime import datetime, timedelta, timezone

from scripts.kpi_snapshot import build_snapshot


def _entry(hours_ago: float, video_id: str, visibility: str = "PUBLIC", status: str = "published",
           channel: str = "1") -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"timestamp": ts, "status": status, "channel_id": channel,
            "video_id": video_id, "visibility": visibility, "title": f"Baslik {video_id}"}


class KpiSnapshotTest(unittest.TestCase):
    def test_counts_window_and_gap(self):
        now = datetime.now(timezone.utc)
        entries = [
            _entry(2, "a"), _entry(10, "b", channel="2"),
            _entry(30, "c"),                      # pencere dışı
            _entry(5, "d", visibility="PRIVATE"),
            {"timestamp": now.isoformat(), "status": "failed", "video_id": "e"},
        ]
        snap = build_snapshot(entries, {"deleted_count": 3, "dry_run": False},
                              {"winning_topic": "Tarih", "boost_active": True},
                              topics_count=40, now=now, target=5, window_hours=24)
        self.assertEqual(snap["published_window"], 3)       # a, b, d
        self.assertEqual(snap["public_window"], 2)
        self.assertEqual(snap["non_public_window"], 1)
        self.assertEqual(snap["target_gap"], 2)             # 5 - 3
        self.assertEqual(snap["by_channel"], {"1": 2, "2": 1})
        self.assertEqual(snap["prune"]["deleted_count"], 3)
        self.assertFalse(snap["prune"]["dry_run"])
        self.assertEqual(snap["analytics"]["winning_topic"], "Tarih")
        self.assertTrue(snap["analytics"]["boost_active"])
        self.assertEqual(snap["topics_used_total"], 40)

    def test_target_met_gap_zero(self):
        now = datetime.now(timezone.utc)
        entries = [_entry(i, f"v{i}") for i in range(5)]
        snap = build_snapshot(entries, None, None, 0, now, target=5, window_hours=24)
        self.assertEqual(snap["published_window"], 5)
        self.assertEqual(snap["target_gap"], 0)


if __name__ == "__main__":
    unittest.main()
