#!/usr/bin/env python3
"""Faz6 public (cookie-free, keyless) provider probe.

GitHub Actions tarafindan cagrilir. Her saglayici icin:
  1. search(keyword) → aday listesi
  2. Ilk adayın download_url'ine GET ile <MAX_BYTES indir
  3. SHA256 hesapla
  4. ffprobe → codec, w, h, duration
  5. ffmpeg -f null - ile tam decode
  6. JSON raporu yaz

Kullanim:
  python scripts/public_providers_probe.py --keyword cats --out probe_out --max-bytes 64M
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Repo root'u sys.path'e ekle
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # type: ignore

from src.media_processing.media_providers import (
    NasaProvider,
    InternetArchiveProvider,
    MixkitProvider,
    MediaCandidate,
)

MAX_BYTES_DEFAULT = 64 * 1024 * 1024
# Tarayici User-Agent kullan (bazi CDN'ler bot UA'ya 403 veriyor)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def download_candidate(c: MediaCandidate, out_path: Path, max_bytes: int, timeout: int = 90) -> dict:
    """Aday videoyu indir, sınırlı bayt ile. Sonuc raporu dict dondurur."""
    diag: dict = {"url": c.download_url}
    try:
        sha = hashlib.sha256()
        total = 0
        with requests.get(c.download_url, stream=True, timeout=timeout,
                          headers={"User-Agent": USER_AGENT}) as r:
            diag["http_status"] = r.status_code
            diag["content_type"] = r.headers.get("content-type")
            decl = int(r.headers.get("content-length") or 0)
            diag["declared_bytes"] = decl
            if r.status_code != 200:
                diag["stage"] = "download_http_error"
                return diag
            if decl > max_bytes:
                diag["stage"] = "declared_too_large"
                return diag
            with out_path.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    sha.update(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        diag["stage"] = "exceeded_max_bytes"
                        return diag
        diag["downloaded_bytes"] = total
        diag["sha256"] = sha.hexdigest()
        diag["stage"] = "downloaded"
    except Exception as e:
        diag["stage"] = "download_exception"
        diag["error"] = str(e)[:300]
    return diag


def ffprobe_diag(video_path: Path) -> dict:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"ffprobe": "failed", "stderr": r.stderr[-400:]}
        info = json.loads(r.stdout)
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if not v:
            return {"ffprobe": "no_video_stream"}
        dur = info.get("format", {}).get("duration")
        return {
            "ffprobe": "ok",
            "codec": v.get("codec_name"),
            "width": v.get("width"),
            "height": v.get("height"),
            "duration": float(dur) if dur else None,
            "format": info.get("format", {}).get("format_name"),
            "bit_rate": int(info["format"]["bit_rate"]) if info.get("format", {}).get("bit_rate") else None,
        }
    except Exception as e:
        return {"ffprobe": "error", "error": str(e)[:300]}


def full_decode(video_path: Path) -> dict:
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video_path), "-f", "null", "-"],
            capture_output=True, text=True, timeout=120,
        )
        return {"full_decode": "ok" if r.returncode == 0 else "failed",
                "stderr": r.stderr[-400:] if r.returncode != 0 else ""}
    except Exception as e:
        return {"full_decode": "error", "error": str(e)[:300]}


def probe_provider(name: str, provider, keyword: str, out_dir: Path, max_bytes: int, max_candidates: int = 3) -> dict:
    rep: dict = {"provider": name, "keyword": keyword}
    try:
        cands = provider.search(keyword)
    except Exception as e:
        rep.update({"stage": "search_exception", "error": str(e)[:400], "overall": "failed"})
        diag = getattr(provider, "last_diagnostics", None)
        if diag:
            rep["provider_diag"] = diag
        return rep
    rep["candidates_found"] = len(cands)
    rep["candidate_titles"] = [c.title for c in cands[:5]]
    if not cands:
        rep.update({"stage": "no_candidates", "overall": "failed"})
        diag = getattr(provider, "last_diagnostics", None)
        if diag:
            rep["provider_diag"] = diag
        return rep

    # Her adayi dene; ilk gecen (indirme + ffprobe + decode) kazansin
    for idx, c in enumerate(cands[:max_candidates]):
        cand_dir = out_dir / name
        cand_dir.mkdir(parents=True, exist_ok=True)
        vid_path = cand_dir / f"cand{idx}.mp4"
        rep[f"candidate_{idx}"] = {
            "title": c.title,
            "source_url": c.source_url,
            "media_id": c.media_id,
            "download_url": c.download_url,
            "license_verified": c.license.verified if c.license else None,
        }
        dl = download_candidate(c, vid_path, max_bytes)
        rep[f"candidate_{idx}"].update(dl)
        if dl.get("stage") != "downloaded":
            if vid_path.exists():
                vid_path.unlink()
            continue
        # ffprobe
        fp = ffprobe_diag(vid_path)
        rep[f"candidate_{idx}"].update(fp)
        if fp.get("ffprobe") != "ok":
            if vid_path.exists():
                vid_path.unlink()
            continue
        # full decode
        fd = full_decode(vid_path)
        rep[f"candidate_{idx}"].update(fd)
        if fd.get("full_decode") == "ok":
            rep.update({
                "stage": "passed",
                "overall": "passed",
                "selected_candidate_index": idx,
                "video_path": str(vid_path.relative_to(ROOT)),
                "width": fp.get("width"),
                "height": fp.get("height"),
                "duration": fp.get("duration"),
                "codec": fp.get("codec"),
                "sha256": dl.get("sha256"),
                "bytes": dl.get("downloaded_bytes"),
            })
            # Video dosyasini birak (artifact'e koymak istersek) ama guvenlik icin kalici degil
            return rep
        if vid_path.exists():
            vid_path.unlink()
    rep.update({"stage": "no_viable_candidate", "overall": "failed"})
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="cats")
    ap.add_argument("--out", default="probe_out_public", type=Path)
    ap.add_argument("--max-bytes", default="64M")
    args = ap.parse_args()

    # max bytes parse
    mb = args.max_bytes.upper().strip()
    if mb.endswith("M"):
        max_bytes = int(float(mb[:-1]) * 1024 * 1024)
    elif mb.endswith("K"):
        max_bytes = int(float(mb[:-1]) * 1024)
    elif mb.endswith("G"):
        max_bytes = int(float(mb[:-1]) * 1024 * 1024 * 1024)
    else:
        max_bytes = int(mb)

    out_dir = (ROOT / args.out).resolve() if not os.path.isabs(args.out) else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})

    providers = [
        ("nasa", NasaProvider(session=sess)),
        ("archiveorg", InternetArchiveProvider(session=sess)),
        ("mixkit", MixkitProvider(session=sess)),
    ]

    report = {"keyword": args.keyword, "max_bytes": max_bytes, "results": {}}
    for name, prov in providers:
        print(f"\n>>> probing {name} for keyword={args.keyword!r}", flush=True)
        r = probe_provider(name, prov, args.keyword, out_dir, max_bytes)
        report["results"][name] = r
        ov = r.get("overall")
        print(f"    {name}: overall={ov} stage={r.get('stage')} "
              f"cands={r.get('candidates_found')} "
              f"{r.get('width')}x{r.get('height')} {r.get('duration')}s {r.get('codec')} "
              f"{human_bytes(r.get('bytes',0)) if r.get('bytes') else ''}", flush=True)

    report_path = out_dir / "probe_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), "utf8")
    print(f"\nRapor: {report_path}")

    failed = [n for n, r in report["results"].items() if r.get("overall") != "passed"]
    if failed:
        print(f"[FAIL] {failed}", file=sys.stderr)
        # CI'i fail et; kullanici kolayca gorebilsin
        sys.exit(1)
    print("[OK] tum public saglayicilar gecti")


if __name__ == "__main__":
    main()
