import os
import unittest
from pathlib import Path
from unittest.mock import patch

from config.constants import DEFAULT_PRIVACY_STATUS, VIDEO_HEIGHT, VIDEO_WIDTH
from config.settings import PROJECT_ROOT, Settings


class ScaffoldTests(unittest.TestCase):
    def test_required_directories_exist(self):
        for folder in (
            "config", "src/content_generation", "src/youtube_upload",
            "src/media_processing", "src/utils", "tests", "logs", "output",
        ):
            with self.subTest(folder=folder):
                self.assertTrue((PROJECT_ROOT / folder).is_dir())

    def test_vertical_video_defaults(self):
        self.assertEqual((VIDEO_WIDTH, VIDEO_HEIGHT), (1080, 1920))
        self.assertEqual(DEFAULT_PRIVACY_STATUS, "private")

    def test_secrets_are_not_required_for_configuration(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "PEXELS_API_KEY": "", "PIXABAY_API_KEY": ""}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.groq_api_key, "")
        self.assertEqual(settings.youtube_privacy_status, "private")
        self.assertEqual(settings.max_retries, 3)

    def test_project_root_is_absolute(self):
        self.assertTrue(Path(PROJECT_ROOT).is_absolute())


if __name__ == "__main__":
    unittest.main()
