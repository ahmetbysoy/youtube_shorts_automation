import os
import unittest
from datetime import datetime, timedelta, timezone

from scripts.auto_pinned_comment import plan_actions, build_comment_text


def _entry(hours_ago: float, video_id: str, status: str = "published") -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"timestamp": ts, "status": status, "channel_id": "1",
            "video_id": video_id, "title": f"Baslik {video_id}"}


class CommentPlanTest(unittest.TestCase):
    def setUp(self):
        os.environ["SUBSCRIBE_URL"] = "https://www.youtube.com/@ornek?sub_confirmation=1"

    def test_new_published_only(self):
        now = datetime.now(timezone.utc)
        entries = [
            _entry(1, "new1"),
            _entry(200, "old1"),               # 8 günden eski
            _entry(2, "fail1", status="failed"),
        ]
        state = {"commented_video_ids": []}
        plan = plan_actions(entries, state, now)
        self.assertEqual([p["video_id"] for p in plan], ["new1"])

    def test_skips_already_commented_and_respects_cap(self):
        now = datetime.now(timezone.utc)
        entries = [_entry(i, f"v{i}") for i in range(5)]
        state = {"commented_video_ids": ["v0"]}
        plan = plan_actions(entries, state, now, max_per_run=2)
        self.assertEqual([p["video_id"] for p in plan], ["v1", "v2"])
        self.assertNotIn("v0", [p["video_id"] for p in plan])

    def test_text_has_subscribe_link(self):
        text = build_comment_text("Baslik")
        self.assertIn("youtube.com", text)
        self.assertIn("abone", text.lower())


if __name__ == "__main__":
    unittest.main()
