"""Bounded media downloads, full visual decode and real technical measurements."""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import requests
from PIL import Image

from .media_providers import DOWNLOAD_HOSTS, MediaCandidate, get_public

MAX_BYTES = 64 * 1024 * 1024


def download_candidate(candidate: MediaCandidate, path: Path, *, session=requests) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    try:
        with get_public(session, candidate.download_url, DOWNLOAD_HOSTS.get(candidate.provider, set()), stream=True) as response:
            declared = int(response.headers.get("Content-Length", "0"))
            if declared > MAX_BYTES:
                raise ValueError("media_size_limit")
            size = 0
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("media_size_limit")
                        handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            if size < 1024 or (declared and declared != size):
                raise ValueError("empty_or_truncated_media")
        partial.replace(path)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        raise RuntimeError("media_download_failed") from None
    finally:
        partial.unlink(missing_ok=True)


def probe_media(path: Path, kind: str) -> dict:
    """Download success is NOT acceptance. Decode the entire selected visual stream."""
    try:
        if not path.is_file() or not 1024 <= path.stat().st_size <= MAX_BYTES:
            raise ValueError("invalid_media_size")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if kind == "image":
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                if im.format not in {"JPEG", "PNG"} or getattr(im, "n_frames", 1) != 1:
                    raise ValueError("unsupported_image_format")
                im.load()
                width, height = im.size
            return {"width": width, "height": height, "duration": None, "sha256": sha, "decode_status": "passed", "bytes": path.stat().st_size}
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,duration", "-of", "json", str(path)],
                                capture_output=True, text=True, timeout=25, check=True)
        data = json.loads(result.stdout)
        streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        if len(streams) != 1:
            raise ValueError("video_stream_count")
        s = streams[0]
        duration = float(s.get("duration") or data.get("format", {}).get("duration") or 0)
        if not math.isfinite(duration) or not 0 < duration <= 120:
            raise ValueError("invalid_media_duration")
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-an", "-f", "null", "-"],
                                 capture_output=True, text=True, timeout=90, check=True)
        if decoded.stderr.strip():
            raise ValueError("decode_errors")
        return {"width": int(s["width"]), "height": int(s["height"]), "duration": duration,
                "sha256": sha, "decode_status": "passed", "bytes": path.stat().st_size}
    except Exception:
        raise RuntimeError("media_probe_or_decode_failed") from None
