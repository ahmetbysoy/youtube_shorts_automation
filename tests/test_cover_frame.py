"""FAZ 3.5: kapak karesi gomme (offline, AI servisi kapali)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
SCRIPT = BASE / "scripts" / "embed_cover_frame.py"

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg yok")


def _make_video(path: Path, seconds: float = 3.0) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=size=1080x1920:rate=30:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True, capture_output=True)


def _frame(video: Path, t: float, out: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(out)],
                   check=True, capture_output=True)


def _duration(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def test_cover_is_embedded_in_first_frames_without_changing_duration(tmp_path: Path):
    video = tmp_path / "final_short.mp4"
    _make_video(video)
    before = _duration(video)
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"title": "Test Kapak #Shorts", "topic": "Bilim", "thumbnail_prompt": "x"}), encoding="utf-8")
    cover = tmp_path / "cover.jpg"

    res = subprocess.run([sys.executable, str(SCRIPT), "--video", str(video), "--script", str(script),
                          "--cover-out", str(cover), "--no-ai", "--seconds", "0.6"],
                         capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "gomuldu" in res.stdout
    assert cover.exists() and cover.stat().st_size > 5000
    assert abs(_duration(video) - before) < 0.2

    f0, f2 = tmp_path / "f0.jpg", tmp_path / "f2.jpg"
    _frame(video, 0.1, f0)
    _frame(video, 2.0, f2)
    pick = BASE / "scripts" / "pick_matching_still.py"
    out = subprocess.run([sys.executable, str(pick), str(cover), str(f2), str(f0)], capture_output=True, text=True)
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["index"] == 1 and data["matched"] is True, data


def test_missing_video_is_safe_noop(tmp_path: Path):
    res = subprocess.run([sys.executable, str(SCRIPT), "--video", str(tmp_path / "yok.mp4"), "--no-ai"],
                         capture_output=True, text=True)
    assert res.returncode == 0 and "atlandi" in res.stdout
