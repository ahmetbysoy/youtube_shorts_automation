"""Faz 3 birim ve entegrasyon testleri (media_processor.py)."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.media_processing.media_processor import (
    FINAL_OUTPUT,
    _escape_ffmpeg_filter_path,
    _extract_wikimedia_credit,
    _is_real_api_key,
    _srt_time_to_ass,
    convert_srt_to_ass,
    get_visual_search_queries,
    validate_output,
)


class TestFaz3MediaProcessor(unittest.TestCase):
    def test_storyboard_queries_prefer_scene_searches_over_legacy_keywords(self) -> None:
        data = {
            "storyboard": [
                {"scene_id": 1, "visual_query": "Venus cloud surface"},
                {"scene_id": 2, "visual_query": "planet orbital diagram"},
            ],
            "visual_keywords": ["generic space", "generic planet"],
        }
        self.assertEqual(
            get_visual_search_queries(data),
            ["Venus cloud surface", "planet orbital diagram"],
        )

    def test_media_search_keeps_legacy_and_safe_default_fallbacks(self) -> None:
        self.assertEqual(get_visual_search_queries({"visual_keywords": ["old query"]}), ["old query"])
        self.assertEqual(get_visual_search_queries({}), ["history", "nature", "cinematic"])

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

    @staticmethod
    def _valid_probe_payload() -> dict:
        return {
            "format": {"duration": "12.0", "size": "500000", "bit_rate": "300000"},
            "streams": [
                {
                    "codec_type": "video", "codec_name": "h264", "width": 1080,
                    "height": 1920, "r_frame_rate": "30/1", "avg_frame_rate": "30/1",
                    "pix_fmt": "yuv420p", "duration": "12.0", "nb_frames": "360",
                },
                {
                    "codec_type": "audio", "codec_name": "aac", "duration": "12.0",
                    "sample_rate": "48000", "channels": 2,
                },
            ],
        }

    def _run_mocked_probe(self, payload: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "final_short.mp4"
            video.write_bytes(b"x" * 1024)
            completed = subprocess.CompletedProcess(
                args=["ffprobe"], returncode=0, stdout=json.dumps(payload), stderr=""
            )
            with patch("src.media_processing.media_processor.subprocess.run", return_value=completed):
                return validate_output(video)

    def test_quality_gate_accepts_valid_vertical_h264_aac_video(self) -> None:
        result = self._run_mocked_probe(self._valid_probe_payload())
        self.assertEqual(len(result["streams"]), 2)

    def test_quality_gate_rejects_wrong_orientation_codec_pixel_format_and_fps(self) -> None:
        cases = (
            ("landscape", {"width": 1920, "height": 1080}),
            ("wrong_video_codec", {"codec_name": "vp9"}),
            ("wrong_pixel_format", {"pix_fmt": "yuv444p"}),
            ("wrong_fps", {"avg_frame_rate": "25/1"}),
        )
        for label, changes in cases:
            with self.subTest(case=label):
                payload = self._valid_probe_payload()
                payload["streams"][0].update(changes)
                with self.assertRaises(RuntimeError):
                    self._run_mocked_probe(payload)

    def test_quality_gate_rejects_missing_or_duplicate_audio_stream(self) -> None:
        for streams in (
            [self._valid_probe_payload()["streams"][0]],
            self._valid_probe_payload()["streams"] + [self._valid_probe_payload()["streams"][1]],
        ):
            payload = self._valid_probe_payload()
            payload["streams"] = streams
            with self.assertRaises(RuntimeError):
                self._run_mocked_probe(payload)

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
