"""Offline regression tests for the thumbnail helper scripts.

These tests must never call Gemini, Pollinations, YouTube Studio, or any paid API.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_fallback_thumbnail as fallback  # noqa: E402
import gemini_frame_selector  # noqa: E402


def test_fallback_thumbnail_cli_creates_vertical_jpeg(tmp_path: Path):
    output = tmp_path / "fallback.jpg"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "generate_fallback_thumbnail.py"),
            "--title",
            "Bu Başlık İçin Çarpıcı Bir Kapak",
            "--topic",
            "Bilim",
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=BASE,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.is_file() and output.stat().st_size > 5_000
    with Image.open(output) as image:
        assert image.format == "JPEG"
        assert image.size == (1080, 1920)


def test_fallback_crop_preserves_target_canvas():
    source = Image.new("RGB", (1200, 800), "navy")
    cropped = fallback.cover_crop(source, 1080, 1920)
    assert cropped.size == (1080, 1920)


def test_contrast_frame_picker_ignores_corrupt_files_and_selects_detail(tmp_path: Path):
    flat = tmp_path / "flat.png"
    detailed = tmp_path / "detailed.png"
    corrupt = tmp_path / "broken.png"
    Image.new("RGB", (160, 90), (128, 128, 128)).save(flat)
    image = Image.new("RGB", (160, 90), "black")
    draw = ImageDraw.Draw(image)
    for x in range(0, 160, 10):
        draw.rectangle((x, 0, x + 4, 89), fill="white")
    image.save(detailed)
    corrupt.write_bytes(b"not an image")

    assert fallback.pick_best_frame([corrupt, flat, detailed]) == detailed
    assert fallback.pick_best_frame([corrupt]) is None


def test_pick_matching_still_reports_exact_match(tmp_path: Path):
    cover = tmp_path / "cover.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (120, 180), (20, 80, 140)).save(cover)
    Image.new("RGB", (120, 180), (20, 80, 140)).save(candidate)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "pick_matching_still.py"),
            str(cover),
            str(candidate),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=BASE,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["index"] == 0
    assert payload["distance"] == 0
    assert payload["matched"] is True


def test_gemini_frame_selector_stays_offline_when_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_VISION_ENABLED", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-used")
    frame = tmp_path / "frame.png"
    Image.new("RGB", (32, 32), "black").save(frame)
    assert gemini_frame_selector.select_subject_frame("Test title", [frame]) is None


def test_gemini_frame_selector_rejects_too_many_frames_before_network(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GEMINI_FREE_VISION_ENABLED", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "must-not-be-used")
    frames = []
    for index in range(9):
        frame = tmp_path / f"frame-{index}.png"
        Image.new("RGB", (32, 32), "black").save(frame)
        frames.append(frame)
    assert gemini_frame_selector.select_subject_frame("Test title", frames) is None
