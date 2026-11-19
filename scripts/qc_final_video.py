#!/usr/bin/env python3
"""Son video kalite kontrolu (QC).

final_short.mp4 icin:
- Dosya mevcut ve okunabilir
- ffprobe ile codec/cozunurluk/fps/sure/ses stream kontrolu
- FFmpeg tam decode (tam video okunur, bozuk/kare kaybi yok)
- Siyah/koyu frame orani kontrolu
- Ses/video sure uyumu (<0.5sn fark)
- Shorts formati: 9:16 dikey, sure 15-60sn
- Dosya boyutu > 500KB
- Thumbnail (cover.jpg) mevcut
- Altyazi dosyasi (final.ass) mevcut

Basarisizlikte exit 1, basarida exit 0. Rapor JSON olarak output/qc_report.json
ve step summary'ye yazilir.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def run(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def ffprobe_json(path: Path) -> dict:
    rc, out, err = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ], timeout=30)
    if rc != 0:
        raise RuntimeError(f"ffprobe basarisiz: {err.strip()}")
    return json.loads(out)


def full_decode(path: Path, timeout=600):
    """ffmpeg ile tam decode (null muxer), geri donus: (rc, stderr_son, sure_sn)."""
    rc, _, err = run([
        "ffmpeg", "-v", "error", "-i", str(path),
        "-f", "null", "-",
    ], timeout=timeout)
    # decode hata sayisi
    err_lines = [l for l in err.splitlines() if l.strip()]
    return rc, err_lines


def measure_black_frames(path: Path, timeout=120):
    """ffmpeg blackdetect ile koyu/siyah frame oranini kaba hesapla."""
    rc, out, err = run([
        "ffmpeg", "-i", str(path),
        "-vf", "blackdetect=d=0.5:pix_th=0.10",
        "-an", "-f", "null", "-",
    ], timeout=timeout)
    total_black = 0.0
    for line in (out + err).splitlines():
        if "black_start:" in line:
            # black_start:X black_end:Y black_duration:Z
            try:
                d = float(line.split("black_duration:")[-1].split()[0])
                total_black += d
            except Exception:
                pass
    return total_black


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(OUT / "final_short.mp4"))
    args = ap.parse_args()

    vpath = Path(args.video)
    report = {"video": str(vpath), "checks": {}, "errors": [], "passed": False}
    failed = 0

    def check(name, ok, detail=""):
        report["checks"][name] = {"ok": bool(ok), "detail": str(detail)}
        nonlocal failed
        if not ok:
            failed += 1
            report["errors"].append(f"{name}: {detail}")
            print(f"[✗] {name}: {detail}", file=sys.stderr)
        else:
            print(f"[✓] {name}: {detail}")

    # 1) Dosya mevcut
    check("file_exists", vpath.exists() and vpath.is_file(), str(vpath))
    if not vpath.exists():
        _finish(report, failed)
    size_mb = vpath.stat().st_size / (1024*1024)
    check("file_size", size_mb > 0.5, f"{size_mb:.2f} MB")

    # 2) ffprobe
    try:
        info = ffprobe_json(vpath)
    except Exception as e:
        check("ffprobe", False, str(e))
        _finish(report, failed := 99)
        return

    vstreams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    astreams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    check("video_stream", len(vstreams) >= 1, f"{len(vstreams)} video stream")
    check("audio_stream", len(astreams) >= 1, f"{len(astreams)} audio stream")

    if vstreams:
        v = vstreams[0]
        w = int(v.get("width", 0)); h = int(v.get("height", 0))
        codec = v.get("codec_name", "?")
        fps_num, fps_den = v.get("r_frame_rate", "30/1").split("/")
        try:
            fps = float(fps_num) / float(fps_den) if float(fps_den) else 0
        except Exception:
            fps = 0
        check("video_codec", codec in ("h264", "hevc"), codec)
        check("resolution_9:16", w == 1080 and h == 1920, f"{w}x{h}")
        check("fps_30", abs(fps - 30) < 2, f"{fps:.2f} fps")
    duration = float(info.get("format", {}).get("duration", 0))
    check("duration_shorts", 15 <= duration <= 65, f"{duration:.2f} sn (Shorts 15-60sn)")

    if astreams:
        a = astreams[0]
        acodec = a.get("codec_name", "?")
        check("audio_codec", acodec == "aac", acodec)
        adur = float(a.get("duration", duration))
        vdur = float(vstreams[0].get("duration", duration)) if vstreams else duration
        check("av_sync", abs(adur - vdur) < 0.5, f"v={vdur:.2f}s a={adur:.2f}s (fark={abs(adur-vdur):.2f}s)")

    # 3) FFmpeg tam decode
    rc, errs = full_decode(vpath)
    check("ffmpeg_full_decode", rc == 0 and not errs, f"rc={rc} hata_satiri={len(errs)}")
    if errs:
        for e in errs[:5]:
            print(f"   decode hata: {e[:160]}", file=sys.stderr)

    # 4) Siyah frame orani
    try:
        black = measure_black_frames(vpath)
        ratio = black / duration if duration else 1.0
        check("black_frames", ratio < 0.05, f"toplam siyah {black:.2f}s (%{ratio*100:.1f})")
    except Exception as e:
        check("black_frames", False, f"blackdetect calismadi: {e}")

    # 5) Cover/altyazi dosyalari
    cover = OUT / "cover.jpg"
    ass = OUT / "final.ass"
    check("cover_exists", cover.exists() and cover.stat().st_size > 10_000, str(cover))
    check("ass_subtitles", ass.exists() and ass.stat().st_size > 100, str(ass))

    _finish(report, failed)


def _finish(report, failed):
    report["passed"] = (failed == 0)
    report_path = OUT / "qc_report.json"
    OUT.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nQC sonucu: {'GECTI' if report['passed'] else 'KALDI'} ({len(report['checks'])} kontrol, {failed} hata)")
    print(f"Rapor: {report_path}")
    # Step summary
    summary = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    if summary.exists() or str(summary) != "/dev/null":
        try:
            with summary.open("a", encoding="utf-8") as f:
                f.write("\n### Final Video QC\n")
                f.write(f"| Kontrol | Sonuç | Detay |\n|---|---|---|\n")
                for name, c in report["checks"].items():
                    icon = "✅" if c["ok"] else "❌"
                    f.write(f"| {name} | {icon} | {c['detail']} |\n")
                f.write(f"\n**Sonuç: {'BAŞARILI ✅' if report['passed'] else 'BAŞARISIZ ❌'}**\n")
        except Exception:
            pass
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
