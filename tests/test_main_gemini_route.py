"""main.py route is wired to Gemini Web-only mode, not paid text APIs."""
from __future__ import annotations

import unittest

from main import content_generation_command


class TestMainGeminiRoute(unittest.TestCase):
    def test_content_command_selects_cookie_only_gemini_and_channel(self):
        command = content_generation_command("7")
        self.assertEqual(command[-3:], ["--gemini-web-only", "--channel_id", "7"])
        self.assertTrue(command[1].endswith("content_engine.py"))


if __name__ == "__main__":
    unittest.main()
