"""Offline smoke tests for installed dependencies and media tools."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from config.constants import VIDEO_HEIGHT, VIDEO_WIDTH
from config.settings import PROJECT_ROOT
from main import inspect_environment


class EnvironmentTests(unittest.TestCase):
    def test_all_required_python_modules_import(self):
        report = inspect_environment()
        failures = {name: value for name, value in report["packages"].items() if not value["ok"]}
        self.assertEqual(failures, {})

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Media tools not installed")
    def test_ffmpeg_encodes_vertical_h264_aac(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            video = Path(temp) / "smoke.mp4"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c=black:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:r=30:d=0.2",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(video),
            ], check=True, capture_output=True, text=True, timeout=30)
            result = subprocess.run([
                "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video),
            ], check=True, capture_output=True, text=True, timeout=30)
            streams = json.loads(result.stdout)["streams"]
            visual = next(stream for stream in streams if stream["codec_type"] == "video")
            audio = next(stream for stream in streams if stream["codec_type"] == "audio")
            self.assertEqual((visual["width"], visual["height"]), (1080, 1920))
            self.assertEqual(visual["codec_name"], "h264")
            self.assertEqual(audio["codec_name"], "aac")

    def test_chromium_runs_local_page_without_external_requests(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            try:
                page = browser.new_page()
                page.route("http://**/*", lambda route: route.abort())
                page.route("https://**/*", lambda route: route.abort())
                page.set_content("<title>Offline smoke test</title><p>42</p>")
                self.assertEqual(page.title(), "Offline smoke test")
                self.assertEqual(page.evaluate("6 * 7"), 42)
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
