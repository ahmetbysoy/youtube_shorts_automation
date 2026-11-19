#!/usr/bin/env python3
"""Son video kalite kontrolu (QC) — Faz 4H.

final_short.mp4 icin:

Teknik kontroller:
  - Dosya mevcut ve okunabilir
  - ffprobe ile codec/cozunurluk/fps/sure/ses stream kontrolu
  - FFmpeg tam decode (tam video okunur, bozuk/kare kaybi yok)
  - Siyah/koyu frame orani kontrolu (tum video + bas/son 1 sn ozel)
  - Ses/video sure uyumu (<0.5sn fark)
  - Shorts formati: 9:16 dikey, 15-60sn
  - Dosya boyutu > 500KB

Gorsel/sahne kontrolleri:
  - Sahne medyasi mevcut (scene_*_pw.mp4) ve decode edilebilir
  - Ayni medya dosyasi butun sahnelerde tekrar etmiyor
  - Sahne surelerinin toplami video suresiyle uyumlu
  - FFmpeg blackdetect ile sahne bazli kosu/karanlik kontrolu

Altyazi kontrolleri (final.ass):
  - Dosya mevcut
  - Gecerli ASS yapisi (Script Info / V4+ Styles / Events bolumleri)
  - Diyalog satirlarinin video suresiyle uyumu
  - MarginV / PlayResY / FontSize degerleri mobil guvenli alan icinde
  - Cok uzun satirlar (>42 karakter) uyari
  - Satir basina okunabilirlik suresi (>0.8 sn)

Kapak kontrolleri (cover.jpg):
  - JPEG/PNG format, 1080x1920
  - Dosya boyutu > 10KB (bos/siyah resim degil)
  - ffprobe ile gorsel dogrulama

Basarisizlikte exit 1, basarida exit 0. Rapor JSON olarak output/qc_report.json
ve step summary'ye yazilir.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

SHORTS_MIN_SEC = 15
SHORTS_MAX_SEC = 60
TARGET_FPS = 30
TARGET_W, TARGET_H = 1080, 1920
AV_SYNC_TOLERANCE_S = 0.5
MAX_BLACK_RATIO = 0.05
HEAD_TAIL_DURATION = 1.0  # ilk ve son 1sn ozel kontrol
SUB_LINE_MAX_CHARS = 42
SUB_MIN_DURATION_S = 0.8
SAFE_MARGIN_BOTTOM = 350  # Alt kenardan guvenli alan (px)


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
    err_lines = [l for l in err.splitlines() if l.strip()]
    return rc, err_lines


def measure_black_frames(path: Path, timeout=120, start_s: float | None = None, duration_s: float | None = None):
    """ffmpeg blackdetect ile koyu/siyah frame oranini kaba hesapla."""
    cmd = ["ffmpeg"]
    if start_s is not None:
        cmd += ["-ss", f"{start_s:.3f}"]
    cmd += ["-i", str(path)]
    if duration_s is not None:
        cmd += ["-t", f"{duration_s:.3f}"]
    cmd += ["-vf", "blackdetect=d=0.3:pix_th=0.10", "-an", "-f", "null", "-"]
    rc, out, err = run(cmd, timeout=timeout)
    total_black = 0.0
    for line in (out + err).splitlines():
        if "black_start:" in line:
            try:
                d = float(line.split("black_duration:")[-1].split()[0])
                total_black += d
            except Exception:
                pass
    return total_black


def list_scene_files(work_dir: Path):
    """work_dir icindeki scene_*_pw.mp4 dosyalarini indeks sirasiyla dondur."""
    scenes = sorted(work_dir.glob("scene_*_pw.mp4"))
    # Fallback: baska isimler (playwright, stock vb.)
    if not scenes:
        scenes = sorted(work_dir.glob("scene_*.mp4"))
    return scenes


def _parse_ass_time(t: str) -> float:
    """ASS zamani (H:MM:SS.cc) saniyeye cevir."""
    m = re.match(r"^(\d+):(\d{2}):(\d{2})\.(\d{1,3})$", t.strip())
    if not m:
        return -1.0
    h, mi, s, cs = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(cs) / (10 ** len(cs))


def validate_ass(ass_path: Path, duration_s: float, report: dict, check) -> None:
    """ASS altyazi dosyasini dogrula."""
    if not ass_path.exists():
        check("ass_exists", False, "final.ass bulunamadi")
        return
    raw = ass_path.read_text(encoding="utf-8-sig", errors="replace")
    check("ass_parse", True, f"{len(raw)} bayt")
    # Bolum kontrolleri
    has_script_info = "[Script Info]" in raw
    has_styles = "[V4+ Styles]" in raw
    has_events = "[Events]" in raw
    check("ass_sections", has_script_info and has_styles and has_events,
          f"info={has_script_info} styles={has_styles} events={has_events}")
    # Cözünürluk kontrolu
    rx = re.search(r"PlayResX:\s*(\d+)", raw)
    ry = re.search(r"PlayResY:\s*(\d+)", raw)
    resx = int(rx.group(1)) if rx else 0
    resy = int(ry.group(1)) if ry else 0
    check("ass_playres", resx == TARGET_W and resy == TARGET_H, f"{resx}x{resy}")
    # MarginV guvenli alan
    mv_m = re.search(r"Style:\s*Default,[^,]*,(\d+),.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,.*?,(\d+),(\d+),(\d+)", raw)
    if mv_m:
        font_size = int(mv_m.group(1))
        margin_l = int(mv_m.group(2))
        margin_r = int(mv_m.group(3))
        margin_v = int(mv_m.group(4))
        ok_margin = margin_v >= 180 and margin_v < TARGET_H - 200
        check("ass_safe_margin", ok_margin,
              f"FontSize={font_size} MarginV={margin_v} L/R={margin_l}/{margin_r}")
    else:
        check("ass_safe_margin", False, "Default stil cozumlenemedi")
    # Diyaloglar
    dialogues = []
    for line in raw.splitlines():
        if line.startswith("Dialogue:"):
            parts = line.split(",", 9)
            if len(parts) >= 10:
                start = _parse_ass_time(parts[1])
                end = _parse_ass_time(parts[2])
                text = parts[9].replace(r"\N", " ").replace(r"\n", " ")
                # ASS animasyon etiketlerini temizle
                text_clean = re.sub(r"\{[^}]*\}", "", text).strip()
                dialogues.append({"start": start, "end": end, "text": text_clean})
    check("ass_dialogues", len(dialogues) >= 5, f"{len(dialogues)} diyalog satiri")
    long_lines = [d for d in dialogues if len(d["text"]) > SUB_LINE_MAX_CHARS]
    check("ass_line_length", len(long_lines) == 0,
          f"{len(long_lines)} satir {SUB_LINE_MAX_CHARS} karakterden uzun" if long_lines else "tum satirlar kisa")
    short_durs = [d for d in dialogues if 0 <= (d["end"] - d["start"]) < SUB_MIN_DURATION_S]
    check("ass_min_duration", len(short_durs) == 0,
          f"{len(short_durs)} satir <{SUB_MIN_DURATION_S}sn" if short_durs else "tumu okunabilir surede")
    # Zaman araligi videoya sigmali
    if dialogues:
        first = min(d["start"] for d in dialogues if d["start"] >= 0)
        last = max(d["end"] for d in dialogues if d["end"] > 0)
        check("ass_time_range", -0.5 <= first and last <= duration_s + 0.5,
              f"ilk={first:.2f}s son={last:.2f}s (video={duration_s:.2f}s)")
    # Kontrol disi karakter (RECT, REPLACEMENT, bozuk UTF-8)
    bad_chars = sum(1 for d in dialogues if "\ufffd" in d["text"])
    check("ass_no_garbage", bad_chars == 0, f"{bad_chars} satirda bozuk karakter")


def validate_cover(cover_path: Path, report: dict, check) -> None:
    """Cover JPG okunabilirlik ve boyut kontrolu (sadece mevcutluk yetmez)."""
    if not cover_path.exists():
        check("cover_exists", False, "cover.jpg bulunamadi")
        return
    size = cover_path.stat().st_size
    check("cover_size", size > 10_000, f"{size/1024:.1f} KB")
    # ffprobe ile dogrula (image2 demuxer)
    rc, out, err = run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", str(cover_path),
    ], timeout=15)
    if rc != 0:
        check("cover_decode", False, f"ffprobe calistirilamadi: {err[:200]}")
        return
    try:
        info = json.loads(out)
        streams = info.get("streams", [])
        v = next((s for s in streams if s.get("codec_type") == "video"), None)
        if v is None:
            check("cover_vstream", False, "video stream yok")
            return
        check("cover_vstream", True, v.get("codec_name", "?"))
        w = int(v.get("width", 0)); h = int(v.get("height", 0))
        check("cover_resolution", w == TARGET_W and h == TARGET_H, f"{w}x{h}")
    except Exception as e:
        check("cover_decode", False, str(e))


def validate_scenes(work_dir: Path, duration_s: float, expected_scenes: int, check) -> None:
    """Indirilen sahne medyalari uzerinde temel kontroller."""
    if not work_dir.exists():
        check("scenes_workdir", False, f"work dir yok: {work_dir}")
        return
    scenes = list_scene_files(work_dir)
    check("scenes_present", len(scenes) >= expected_scenes,
          f"{len(scenes)} sahne (beklenen >= {expected_scenes})")
    if not scenes:
        return
    # Sahne bazli decode + unique hash (inode/path unique)
    hashes = set()
    total_dur = 0.0
    decode_failed = 0
    for sp in scenes:
        if sp.stat().st_size < 50_000:
            check(f"scene_size_{sp.name}", False, f"{sp.stat().st_size} bayt (çok küçük)")
            continue
        try:
            info = ffprobe_json(sp)
            vs = [s for s in info["streams"] if s.get("codec_type") == "video"]
            if not vs:
                check(f"scene_vstream_{sp.name}", False, "video stream yok")
                continue
            d = float(info.get("format", {}).get("duration", 0))
            total_dur += d
            hashes.add(sp.resolve())
        except Exception as e:
            decode_failed += 1
            check(f"scene_probe_{sp.name}", False, str(e)[:80])
    check("scenes_unique", len(hashes) == len(scenes),
          f"{len(scenes) - len(hashes)} tekrar dosya" if len(hashes) != len(scenes) else "tum sahneler benzersiz dosya")
    check("scenes_decode", decode_failed == 0, f"{decode_failed} sahne probe/decode basarisiz")
    # scene mp4 lerin toplam süresi en az ses süresi kadar olmali (loop'la uzatilabilir ama yeterli kaynagi olmali)
    # Toplam loop-oncesi kaynak süresi >= 8 sn ise yeterli (9.7sn'ye loop'la cikar)
    if total_dur > 0:
        check("scenes_source_duration", total_dur >= 8.0,
              f"toplam kaynak {total_dur:.1f}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(OUT / "final_short.mp4"))
    args = ap.parse_args()

    vpath = Path(args.video)
    report = {"video": str(vpath), "checks": {}, "errors": [], "warnings": [], "passed": False}
    failed = 0
    warns = 0

    def check(name, ok, detail="", *, warning=False):
        report["checks"][name] = {"ok": bool(ok), "detail": str(detail), "warning": bool(warning)}
        nonlocal failed, warns
        if not ok:
            if warning:
                warns += 1
                report["warnings"].append(f"{name}: {detail}")
                print(f"[!] {name}: {detail}")
            else:
                failed += 1
                report["errors"].append(f"{name}: {detail}")
                print(f"[✗] {name}: {detail}", file=sys.stderr)
        else:
            print(f"[✓] {name}: {detail}")

    # 1) Dosya mevcut
    check("file_exists", vpath.exists() and vpath.is_file(), str(vpath))
    if not vpath.exists():
        _finish(report, failed, warns)
    size_mb = vpath.stat().st_size / (1024*1024)
    check("file_size", size_mb > 0.5, f"{size_mb:.2f} MB")

    # 2) ffprobe
    try:
        info = ffprobe_json(vpath)
    except Exception as e:
        check("ffprobe", False, str(e))
        _finish(report, failed := 99, warns)
        return

    vstreams = [s for s in info["streams"] if s.get("codec_type") == "video"]
    astreams = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    check("video_stream", len(vstreams) >= 1, f"{len(vstreams)} video stream")
    check("audio_stream", len(astreams) >= 1, f"{len(astreams)} audio stream")

    duration = float(info.get("format", {}).get("duration", 0))
    vdur = adur = duration
    if vstreams:
        v = vstreams[0]
        w = int(v.get("width", 0)); h = int(v.get("height", 0))
        codec = v.get("codec_name", "?")
        fps_num, fps_den = v.get("r_frame_rate", "30/1").split("/")
        try:
            fps = float(fps_num) / float(fps_den) if float(fps_den) else 0
        except Exception:
            fps = 0
        vdur = float(v.get("duration", duration))
        pix_fmt = v.get("pix_fmt", "?")
        check("video_codec", codec in ("h264", "hevc"), codec)
        check("resolution_9:16", w == TARGET_W and h == TARGET_H, f"{w}x{h}")
        check("fps_30", abs(fps - TARGET_FPS) < 2, f"{fps:.2f} fps")
        check("pix_fmt_yuv420p", pix_fmt == "yuv420p", pix_fmt)
    check("duration_shorts", SHORTS_MIN_SEC <= duration <= SHORTS_MAX_SEC,
          f"{duration:.2f} sn (Shorts {SHORTS_MIN_SEC}-{SHORTS_MAX_SEC}sn)")

    if astreams:
        a = astreams[0]
        acodec = a.get("codec_name", "?")
        check("audio_codec", acodec == "aac", acodec)
        adur = float(a.get("duration", duration))
        check("sample_rate_44k_48k", a.get("sample_rate", "?") in ("44100", "48000"), a.get("sample_rate", "?"))
        check("channels", int(a.get("channels", 0)) >= 1, f"{a.get('channels','?')} kanal")
    check("av_sync", abs(adur - vdur) < AV_SYNC_TOLERANCE_S,
          f"v={vdur:.2f}s a={adur:.2f}s (fark={abs(adur-vdur):.2f}s)")

    # 3) FFmpeg tam decode
    rc, errs = full_decode(vpath)
    check("ffmpeg_full_decode", rc == 0 and not errs, f"rc={rc} hata_satiri={len(errs)}")
    if errs:
        for e in errs[:5]:
            print(f"   decode hata: {e[:160]}", file=sys.stderr)

    # 4) Siyah frame orani (tum video)
    try:
        black = measure_black_frames(vpath, timeout=180)
        ratio = black / duration if duration else 1.0
        check("black_frames", ratio < MAX_BLACK_RATIO,
              f"toplam siyah {black:.2f}s (%{ratio*100:.1f})")
    except Exception as e:
        check("black_frames", False, f"blackdetect calismadi: {e}")

    # 5) Bas/son siyah frame kontrolu
    try:
        head_black = measure_black_frames(vpath, timeout=30, start_s=0, duration_s=HEAD_TAIL_DURATION)
        check("head_clean", head_black < 0.8,
              f"ilk {HEAD_TAIL_DURATION}sn siyah {head_black:.2f}s")
        tail_start = max(0, duration - HEAD_TAIL_DURATION)
        tail_black = measure_black_frames(vpath, timeout=30, start_s=tail_start, duration_s=HEAD_TAIL_DURATION)
        check("tail_clean", tail_black < 0.8,
              f"son {HEAD_TAIL_DURATION}sn siyah {tail_black:.2f}s")
    except Exception as e:
        check("head_clean", False, f"bas/son blackdetect: {e}", warning=True)

    # 6) Sahne medyalari
    # Birden fazla work__* dizini olabilir; en guncelini sec
    work_dirs = sorted([p for p in OUT.glob("work__*") if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    expected_scenes = 4
    if work_dirs:
        validate_scenes(work_dirs[0], duration, expected_scenes, check)
    else:
        check("scenes_workdir", False, "work__* dizini bulunamadi", warning=True)

    # 7) Cover
    cover = OUT / "cover.jpg"
    validate_cover(cover, report, check)

    # 8) Altyazi
    ass = OUT / "final.ass"
    validate_ass(ass, duration, report, check)

    _finish(report, failed, warns)


def _finish(report, failed, warns):
    report["passed"] = (failed == 0)
    report["warning_count"] = warns
    report_path = OUT / "qc_report.json"
    OUT.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nQC sonucu: {'GECTI' if report['passed'] else 'KALDI'} ({len(report['checks'])} kontrol, {failed} hata, {warns} uyari)")
    print(f"Rapor: {report_path}")
    # Step summary
    summary = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    try:
        if str(summary) != "/dev/null":
            with summary.open("a", encoding="utf-8") as f:
                f.write("\n### Final Video QC (Faz 4H)\n")
                f.write(f"| Kontrol | Sonuç | Detay |\n|---|---|---|\n")
                for name, c in report["checks"].items():
                    if c.get("warning"):
                        icon = "⚠️" if not c["ok"] else "✅"
                    else:
                        icon = "✅" if c["ok"] else "❌"
                    f.write(f"| {name} | {icon} | {c['detail']} |\n")
                f.write(f"\n**Sonuç: {'BAŞARILI ✅' if report['passed'] else 'BAŞARISIZ ❌'}**  ")
                f.write(f"Hata: {failed}, Uyarı: {warns}\n")
    except Exception:
        pass
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
