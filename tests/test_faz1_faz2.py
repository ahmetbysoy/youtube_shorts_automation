import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.content_generation import (
    FALLBACK_SCENARIOS,
    build_dynamic_shorts_srt,
    generate_scenario,
    sanitize_for_tts,
)
from src.youtube_upload import (
    FORCED_PRIVACY_STATUS,
    YouTubeOAuthHandler,
    build_video_Metadata,
    extract_auth_code,
)


class Faz1AndFaz2Tests(unittest.TestCase):
    def test_extract_auth_code_from_loopback_url_and_raw(self):
        url = "http://localhost:8080/?state=xyz&code=4/0AVGzR1_TestCode&scope=https://www.googleapis.com/auth/youtube.upload"
        self.assertEqual(extract_auth_code(url), "4/0AVGzR1_TestCode")
        self.assertEqual(YouTubeOAuthHandler._extract_code(url), "4/0AVGzR1_TestCode")

    def test_oauth_handler_fails_cleanly_when_secrets_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            handler = YouTubeOAuthHandler(
                client_secret_path=tmp_dir / "missing_secret.json",
                token_path=tmp_dir / "missing_token.json",
            )
            self.assertFalse(handler.authenticate())
            with self.assertRaises(RuntimeError):
                handler.get_service()

    def test_oauth_handler_sessionless_token_works_without_client_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            token_path = tmp_dir / "token.json"
            token_path.write_text(
                json.dumps(
                    {
                        "token": "ya29.mock_access_token",
                        "refresh_token": "1//0mock_refresh_token",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "client_id": "12345.apps.googleusercontent.com",
                        "client_secret": "GOCSPX-mock",
                        "expiry": "2099-01-01T00:00:00Z",
                        "scopes": [
                            "https://www.googleapis.com/auth/youtube.upload",
                            "https://www.googleapis.com/auth/youtube.force-ssl",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            handler = YouTubeOAuthHandler(
                client_secret_path=tmp_dir / "nonexistent_client_secret.json",
                token_path=token_path,
            )
            with patch("src.youtube_upload.oauth_handler.build", return_value=MagicMock()) as mock_build:
                ok = handler.authenticate()
                self.assertTrue(ok)
                mock_build.assert_called_once()
                self.assertIsNotNone(handler.get_service())

    def test_upload_metadata_forces_private_status(self):
        body = build_video_Metadata(
            title="Test Video 01",
            description="Test açıklama",
            category_id="27",
            tags=["shorts", "test"],
        )
        self.assertEqual(FORCED_PRIVACY_STATUS, "private")
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])

    def test_tts_sanitizer_normalizes_turkish_abbreviations(self):
        raw = "**M.Ö.** %25 oranında [Müzik] 4.5 milyar yıl!"
        cleaned = sanitize_for_tts(raw)
        self.assertIn("milattan önce", cleaned)
        self.assertIn("yüzde 25", cleaned)
        self.assertIn("4,5", cleaned)
        self.assertNotIn("[Müzik]", cleaned)

    def test_fallback_scenarios_within_word_budget(self):
        self.assertGreaterEqual(len(FALLBACK_SCENARIOS), 3)
        scenario = generate_scenario(force_fallback=True)
        self.assertGreaterEqual(scenario["word_count"], 55)
        self.assertLessEqual(scenario["word_count"], 95)
        self.assertIn("#shorts", scenario["title"].lower())

    def test_dynamic_shorts_srt_builder(self):
        words = [
            {"word": "Tarihte", "start_ms": 100.0, "end_ms": 500.0},
            {"word": "sadece", "start_ms": 500.0, "end_ms": 900.0},
            {"word": "otuz", "start_ms": 900.0, "end_ms": 1200.0},
            {"word": "sekiz", "start_ms": 1200.0, "end_ms": 1600.0},
        ]
        srt = build_dynamic_shorts_srt(words, words_per_cue=3)
        self.assertIn("00:00:00,100 --> 00:00:01,200", srt)
        self.assertIn("Tarihte sadece otuz", srt)


if __name__ == "__main__":
    unittest.main()
