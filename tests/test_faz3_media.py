"""Faz 3 birim ve entegrasyon testleri (media_processor.py)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.media_processing.media_processor import (
    FINAL_OUTPUT,
    _escape_ffmpeg_filter_path,
    _extract_wikimedia_credit,
    _is_real_api_key,
    _srt_time_to_ass,
    convert_srt_to_ass,
    validate_output,
)


class TestFaz3MediaProcessor(unittest.TestCase):
    def test_api_key_guard_rejects_placeholders(self) -> None:
        self.assertFalse(_is_real_api_key(None))
        self.assertFalse(_is_real_api_key(""))
        self.assertFalse(_is_real_api_key("senin_gercek_pexels_api_keyin_buraya"))
        self.assertTrue(_is_real_api_key("live_key_987654321"))

    def test_srt_timestamp_to_ass_format(self) -> None:
        self.assertEqual(_srt_time_to_ass("00:00:01,492"), "0:00:01.49")
        self.assertEqual(_srt_time_to_ass("01:05:09,050"), "1:05:09.05")

    def test_convert_srt_to_ass_builds_1080x1920_pop_events(self) -> None:
        sample_srt = (
            "1\n"
            "00:00:00,100 --> 00:00:01,500\n"
            "Napolyon Bonapart'ın,\n\n"
            "2\n"
            "00:00:01,500 --> 00:00:03,200\n"
            "en tuhaf yenilgisi!\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            srt_p = Path(tmp) / "test.srt"
            ass_p = Path(tmp) / "test.ass"
            srt_p.write_text(sample_srt, encoding="utf-8")
            convert_srt_to_ass(srt_p, ass_p)
            text = ass_p.read_text(encoding="utf-8")
            self.assertIn("PlayResX: 1080", text)
            self.assertIn("PlayResY: 1920", text)
            self.assertIn("Style: Default,Montserrat-Bold,56,&H0000FFFF", text)
            self.assertIn("Style: Hook,Montserrat-Bold,62,&H0026FFFF", text)
            self.assertIn(",250,1", text)
            self.assertIn("Napolyon Bonapart'ın,", text)
            self.assertIn("Dialogue: 0,0:00:00.10,0:00:01.50,Hook", text)
            self.assertEqual(text.count("Dialogue: 0,"), 2)

    def test_wikimedia_cc_by_sa_credit_extraction(self) -> None:
        cc_by_sa = _extract_wikimedia_credit(
            {"title": "File:Sample_artifact.jpg"},
            {
                "extmetadata": {
                    "Artist": {"value": '<a href="https://commons.wikimedia.org/wiki/User:Test">Dr. Jane Doe</a>'},
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                }
            },
        )
        self.assertIsNotNone(cc_by_sa)
        self.assertIn("Dr. Jane Doe", cc_by_sa)
        self.assertIn("CC BY-SA 4.0", cc_by_sa)
        # Public Domain görsellerde gereksiz atıf satırı üretilmez
        public_domain = _extract_wikimedia_credit(
            {"title": "File:Hubble.jpg"},
            {
                "extmetadata": {
                    "Artist": {"value": "NASA"},
                    "LicenseShortName": {"value": "Public domain"},
                }
            },
        )
        self.assertEqual(public_domain, "")

    def test_escape_ffmpeg_filter_path(self) -> None:
        escaped = _escape_ffmpeg_filter_path(Path("/tmp/a:b'c.ass"))
        self.assertIn(r"\:", escaped)
        self.assertIn(r"\'", escaped)

    def test_final_short_output_passes_ffprobe_validation(self) -> None:
        if FINAL_OUTPUT.exists():
            meta = validate_output(FINAL_OUTPUT)
            v_stream = next(s for s in meta["streams"] if s["codec_type"] == "video")
            a_stream = next(s for s in meta["streams"] if s["codec_type"] == "audio")
            self.assertEqual(v_stream["width"], 1080)
            self.assertEqual(v_stream["height"], 1920)
            self.assertEqual(v_stream["codec_name"], "h264")
            self.assertEqual(a_stream["codec_name"], "aac")


if __name__ == "__main__":
    unittest.main()
