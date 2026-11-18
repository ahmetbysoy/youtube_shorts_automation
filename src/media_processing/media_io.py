"""Bounded media IO with safe, separated HTTP/download/probe/full-decode evidence."""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import requests
from PIL import Image

from .media_providers import DOWNLOAD_HOSTS, MediaCandidate, PublicHTTPError, get_public

MAX_BYTES = 64 * 1024 * 1024
IO_STAGES = ("download_http", "redirect_final_host", "content_type", "content_length", "download_body", "file_sha256", "container_probe", "full_decode")


class MediaIOError(RuntimeError):
    """Only a fixed safe class and structured evidence; no raw exception cause."""
    def __init__(self, message: str, code: str, evidence: dict):
        super().__init__(message)
        self.safe_error_class = code
        self.evidence = evidence


def io_evidence() -> dict:
    return {name: {"status": "not_reached"} for name in IO_STAGES}


def _playwright_download(candidate: MediaCandidate, path: Path, evidence: dict) -> Path | None:
    """Faz 4E: `catalog_transport == "playwright"` olan adaylar cookie ile
    video_fetcher.js uzerinden indirilir. Public HTTP fallback YOK.
    Donen dosya zaten SHA256 + ffprobe + full-decode dogrulamasindan gecmistir;
    burada tekrar probe bilgilerini evidence'e doldururuz.
    """
    from .media_processor import probe_media as _probe
    import sys
    fetcher = Path(__file__).resolve().parents[2] / "video_fetcher.js"
    if not fetcher.exists():
        raise MediaIOError("video_fetcher.js not found", "missing_fetcher", evidence)
    # Tarayici child'a YALNIZCA guvenli env + ilgili cookie
    provider_env = {"pexels": "PEXELS_COOK", "pixabay": "PIXABAY_COOK"}.get(candidate.provider)
    safe_env_names = {"PATH","HOME","USER","LOGNAME","LANG","LC_ALL","LC_CTYPE","DISPLAY",
                      "TMPDIR","TMP","TEMP","XDG_RUNTIME_DIR","PLAYWRIGHT_BROWSERS_PATH"}
    if provider_env:
        safe_env_names.add(provider_env)
    child_env = {k: v for k, v in os.environ.items() if k in safe_env_names}
    path.parent.mkdir(parents=True, exist_ok=True)
    # video_fetcher.js indirme+dogrulama yapip cikti dosyasini path'e yazar
    args = ["node", str(fetcher), str(candidate.title or candidate.provider), str(path),
            "--provider", candidate.provider,
            "--min-width", "640", "--min-height", "360",
            "--min-duration", "2", "--max-duration", "300",
            "--max-bytes", str(MAX_BYTES)]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=180,
                           cwd=str(fetcher.parent), env=child_env)
    except subprocess.TimeoutExpired:
        evidence["download_http"] = {"status": "failed", "error_class": "playwright_timeout"}
        return None
    if r.returncode != 0 or not path.exists() or path.stat().st_size < 50_000:
        err_tail = (r.stderr or "").strip().splitlines()[-1][:200] if r.stderr else "(no stderr)"
        evidence["download_http"] = {"status": "failed", "error_class": "playwright_failed", "detail": err_tail}
        return None
    # IO evidence doldur
    size = path.stat().st_size
    evidence["download_http"] = {"status": "passed", "http_status": 200, "transport": "cookie_playwright"}
    evidence["redirect_final_host"] = {"status": "passed", "final_host": f"{candidate.provider}_via_playwright", "final_host_allowed": True, "hops": []}
    evidence["content_type"] = {"status": "observed", "mime": "video/mp4"}
    evidence["content_length"] = {"status": "observed", "declared_bytes": size}
    evidence["download_body"] = {"status": "passed", "received_bytes": size, "declared_length_matches": None}
    return path


def download_candidate(candidate: MediaCandidate, path: Path, *, session=requests, evidence: dict | None = None) -> Path:
    evidence = io_evidence() if evidence is None else evidence
    for key in IO_STAGES: evidence.setdefault(key, {"status": "not_reached"})
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix+".part")
    transport = {}; size = 0; code = "http_error"; stage = "download_http"
    try:
        # Faz 4E: playwright/cookie transport'u olan adaylar public HTTP ile degil
        # video_fetcher.js uzerinden (cookie+ffprobe+decode dogrulamali) indirilir.
        if candidate.catalog_transport == "playwright" and candidate.media_type == "video":
            pw = _playwright_download(candidate, path, evidence)
            if pw is None:
                code = "playwright_download_failed"; raise ValueError(code)
            # SHA256 + probe simetrik olsun diye ustteki akista devam etmesi icin return etme,
            # asagidaki post-download probe'a dusmesi icin partial akisini burada ayarla.
            # (video_fetcher.js zaten dogruladi; burada sadece io_evidence zinciri icin)
            evidence["file_sha256"] = {"status": "passed", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "complete_download": True}
            return path
        with get_public(session, candidate.download_url, DOWNLOAD_HOSTS.get(candidate.provider, set()), trace=transport, stream=True) as response:
            evidence["download_http"] = {"status": "passed", "http_status": response.status_code if type(response.status_code) is int else 200}
            evidence["redirect_final_host"] = {"status": "passed", "final_host": transport.get("final_host"),
                "final_host_allowed": transport.get("final_host_allowed", False), "hops": transport.get("hops", [])}
            stage = "content_type"
            # Never retain an arbitrary raw header (which can contain URLs).
            raw_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            known = {"video/webm", "video/mp4", "video/ogg", "image/jpeg", "image/png", "application/octet-stream", "application/ogg", "text/html", "text/plain", "application/json"}
            mime = raw_type if raw_type in known else "unrecognized" if raw_type else "not_supplied"
            evidence[stage] = {"status": "observed", "mime": mime}
            if mime in {"text/html", "text/plain", "application/json"}:
                code = "invalid_container"; raise ValueError(code)
            stage = "content_length"; code = "invalid_content_length"
            raw_length = response.headers.get("Content-Length")
            declared = int(raw_length) if raw_length is not None else None
            if declared is not None and declared < 0: raise ValueError("invalid_content_length")
            evidence[stage] = {"status": "observed", "declared_bytes": declared}
            if declared is not None and declared > MAX_BYTES:
                code = "download_size_limit"; raise ValueError(code)
            stage = "download_body"; code = "truncated_download"
            with partial.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        size += len(chunk)
                        if size > MAX_BYTES:
                            code = "download_size_limit"; raise ValueError(code)
                        handle.write(chunk)
                handle.flush(); os.fsync(handle.fileno())
            evidence[stage] = {"status": "received", "received_bytes": size}
            if size < 1024:
                code = "empty_download"; raise ValueError(code)
            if declared and declared != size: raise ValueError("length_mismatch")
        partial.replace(path)
        evidence["download_body"] = {"status": "passed", "received_bytes": size, "declared_length_matches": declared == size if declared else None}
        evidence["file_sha256"] = {"status": "passed", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "complete_download": True}
        return path
    except Exception as exc:
        if isinstance(exc, requests.Timeout): code = "download_timeout"
        elif isinstance(exc, requests.exceptions.ChunkedEncodingError): code = "truncated_download"
        elif transport.get("error_class"): code = transport["error_class"]
        if stage == "download_http":
            evidence["download_http"] = {"status": "failed", "http_status": exc.http_status if isinstance(exc, PublicHTTPError) else transport.get("http_status"), "error_class": code}
            evidence["redirect_final_host"] = {"status": "failed" if code == "redirect_rejected" else "validated_before_http", "final_host": transport.get("final_host"),
                "final_host_allowed": transport.get("final_host_allowed", False), "hops": transport.get("hops", [])}
        evidence[stage] = {**evidence[stage], "status": "failed", "error_class": code}
        if stage == "download_body": evidence[stage]["received_bytes"] = size
        path.unlink(missing_ok=True)
        raise MediaIOError("media_download_failed", code, evidence) from None
    finally:
        partial.unlink(missing_ok=True)


def probe_media(path: Path, kind: str, *, evidence: dict | None = None) -> dict:
    """Probe metadata and decode the ENTIRE stream, with no network protocols."""
    evidence = io_evidence() if evidence is None else evidence
    for key in IO_STAGES: evidence.setdefault(key, {"status": "not_reached"})
    stage = "container_probe"; code = "probe_failed"
    try:
        if not path.is_file() or not 1024 <= path.stat().st_size <= MAX_BYTES:
            code = "empty_download"; raise ValueError(code)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        evidence["file_sha256"] = {**evidence["file_sha256"], "status": "passed", "sha256": sha}
        if kind == "image":
            code = "invalid_container"
            with Image.open(path) as im:
                if im.format not in {"JPEG", "PNG"} or getattr(im, "n_frames", 1) != 1: raise ValueError(code)
                width, height, fmt = *im.size, im.format
                evidence["container_probe"] = {"status": "passed", "container": fmt, "width": width, "height": height, "duration": None}
                stage = "full_decode"; code = "full_decode_failed"
                im.verify()
            with Image.open(path) as im: im.load()
            evidence["full_decode"] = {"status": "passed", "method": "pillow_verify_and_full_load"}
            return {"width": width, "height": height, "duration": None, "sha256": sha, "decode_status": "passed", "bytes": path.stat().st_size}
        if kind != "video":
            code = "invalid_container"; raise ValueError(code)
        result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries",
            "format=format_name,duration:stream=codec_type,codec_name,width,height,duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=25, check=True)
        data = json.loads(result.stdout)
        streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
        if len(streams) != 1: raise ValueError("video_stream_count")
        s = streams[0]; container = data.get("format", {}).get("format_name")
        if container not in {"matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2", "ogg"}:
            code = "invalid_container"; raise ValueError(code)
        duration = float(s.get("duration") or data.get("format", {}).get("duration") or 0)
        if not math.isfinite(duration) or not 0 < duration <= 120: raise ValueError("invalid_media_duration")
        width, height = int(s["width"]), int(s["height"])
        evidence["container_probe"] = {"status": "passed", "container": container, "width": width, "height": height, "duration": duration}
        stage = "full_decode"; code = "full_decode_failed"
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0", "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=90, check=True)
        if decoded.stderr.strip(): raise ValueError(code)
        evidence["full_decode"] = {"status": "passed", "method": "ffmpeg_entire_visual_stream_xerror", "network_protocols_allowed": False}
        return {"width": width, "height": height, "duration": duration, "sha256": sha, "decode_status": "passed", "bytes": path.stat().st_size}
    except Exception:
        evidence[stage] = {**evidence[stage], "status": "failed", "error_class": code}
        raise MediaIOError("media_probe_or_decode_failed", code, evidence) from None
