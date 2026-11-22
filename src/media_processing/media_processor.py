#!/usr/bin/env python3
"""
Faz 3 - Görev 3: Medya İşleme ve FFmpeg Montaj Hattı (media_processor.py)
Gerçek API'ler (Pexels -> Pixabay -> Wikimedia Commons),
gerçek FFmpeg kompleks filtreleri (9:16 scale+crop + concat + Ken Burns zoompan +
ASS dinamik altyazı burn-in + afftdn & sidechaincompress audio ducking),
sıfır basitleştirme.
"""

from __future__ import annotations

import json
import os
from fractions import Fraction
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

# Yol tanımlamaları
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT_JSON_PATH = BASE_DIR / "script.json"
SRT_PATH = BASE_DIR / "voiceover.srt"
VOICEOVER_MP3_PATH = BASE_DIR / "voiceover.mp3"
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
FINAL_OUTPUT = OUTPUT_DIR / "final_short.mp4"

USER_AGENT = "YouTubeShortsAutomation/1.0 (https://github.com/ahmetbysoy/youtube_shorts_automation)"
EXCLUDED_MEDIA_TERMS = (
    "intubation", "surgery", "autopsy", "allograft", "dissection",
    "medical", "clinical", "patient", "endoscopy", "ultrasound", "pathology",
    "parasite", "disease", "laboratory", "tumor", "lesion",
    "bugs_bunny", "bugs bunny", "cartoon", "closing_credits", "credits",
)
STOPWORDS_SIMPLIFY = {"running", "vintage", "cinematic", "dramatic", "footage", "field"}


def load_env() -> None:
    """Proje kökündeki `.env` dosyasını yükler."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def _resolve_input_file(primary: Path, sample_name: str) -> Path:
    """Dosya kökte yoksa `output/` veya `samples/` dizinlerinden bulur."""
    if primary.exists():
        return primary
    for candidate in (OUTPUT_DIR / sample_name, BASE_DIR / "samples" / sample_name):
        if candidate.exists():
            return candidate
    return primary


def _build_query_variants(keyword: str) -> List[str]:
    variants = [keyword.strip()]
    words = [w for w in keyword.strip().split() if w.lower() not in STOPWORDS_SIMPLIFY]
    if words and " ".join(words) not in variants:
        variants.append(" ".join(words))
    if words and words[0] not in variants:
        variants.append(words[0])
    return variants


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(raw or ""))
    return re.sub(r"\s+", " ", text).strip()


def _extract_wikimedia_credit(page: Dict[str, Any], ii: Dict[str, Any]) -> str:
    """Wikimedia Commons extmetadata alanından CC BY / CC BY-SA lisans ve yazar atfını üretir."""
    ext = (ii or {}).get("extmetadata") or {}
    lic = _strip_html((ext.get("LicenseShortName") or {}).get("value", ""))
    attr_req = str((ext.get("AttributionRequired") or {}).get("value", "")).lower()
    artist = _strip_html((ext.get("Artist") or {}).get("value", "")) or _strip_html((ext.get("Credit") or {}).get("value", ""))
    file_title = str((page or {}).get("title", "")).replace("File:", "").strip()
    needs_attr = ("cc" in lic.lower() and "cc0" not in lic.lower()) or "by" in lic.lower() or attr_req in ("true", "1", "yes")
    if not needs_attr:
        return ""
    parts = [p for p in (file_title[:60], artist[:50], lic or "CC BY-SA") if p]
    return f"Görsel/Video Atfı (Wikimedia Commons): {' — '.join(parts)}"


def fetch_wikimedia_media(keyword: str, duration_needed: float, used_urls: set[str] | None = None) -> Dict[str, Any] | None:
    """
    Üçüncül Medya Katmanı (dosya bazlı otomatik CC BY / CC BY-SA lisans/atıf doğrulamalı):
    Pexels/Pixabay anahtarı yoksa veya kota dolmuşsa Wikimedia Commons resmi API'sinden
    gerçek belgesel/doğa videoları (.webm/.mp4) veya yüksek çözünürlüklü arşiv görselleri çeker.
    """
    used = used_urls or set()
    headers = {"User-Agent": USER_AGENT}
    api_url = "https://commons.wikimedia.org/w/api.php"
    variants = _build_query_variants(keyword)

    # 1. Önce kısa boyutlu (0.5 MB - 28 MB) gerçek .webm/.mp4 video klipleri ara
    for q in variants:
        try:
            resp = requests.get(
                api_url,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"filetype:video {q}",
                    "gsrnamespace": 6,
                    "gsrlimit": 15,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "format": "json",
                },
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            pages = (resp.json().get("query") or {}).get("pages") or {}
            valid_videos = []
            for page in pages.values():
                title_lower = str(page.get("title", "")).lower()
                if any(bad in title_lower for bad in EXCLUDED_MEDIA_TERMS):
                    continue
                ii = (page.get("imageinfo") or [{}])[0]
                url = ii.get("url", "")
                size = int(ii.get("size") or 0)
                mime = str(ii.get("mime", "")).lower()
                if url and url not in used and 500_000 <= size <= 28_000_000 and ("video/webm" in mime or "video/mp4" in mime):
                    valid_videos.append((url, _extract_wikimedia_credit(page, ii)))
            if valid_videos:
                chosen_url, credit = valid_videos[0]
                return {
                    "url": chosen_url,
                    "duration": 10.5,
                    "provider": "wikimedia-commons-video",
                    "media_kind": "video",
                    "credit": credit,
                }
        except Exception as exc:
            print(f"[UYARI] Wikimedia video arama hatası ({q}): {exc}", file=sys.stderr)

    # 2. Uygun video yoksa yüksek çözünürlüklü gerçek arşiv fotoğrafı/tablosu çek
    for q in variants:
        try:
            resp = requests.get(
                api_url,
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"filetype:bitmap {q}",
                    "gsrnamespace": 6,
                    "gsrlimit": 15,
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "iiurlwidth": 1920,
                    "format": "json",
                },
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            pages = (resp.json().get("query") or {}).get("pages") or {}
            valid_images = []
            for page in pages.values():
                title_lower = str(page.get("title", "")).lower()
                if any(bad in title_lower for bad in EXCLUDED_MEDIA_TERMS):
                    continue
                ii = (page.get("imageinfo") or [{}])[0]
                thumb_url = ii.get("thumburl") or ii.get("url") or ""
                mime = str(ii.get("mime", "")).lower()
                if thumb_url and thumb_url not in used and ("image/jpeg" in mime or "image/png" in mime):
                    valid_images.append((thumb_url, _extract_wikimedia_credit(page, ii)))
            if valid_images:
                chosen_url, credit = valid_images[0]
                return {
                    "url": chosen_url,
                    "duration": 10.5,
                    "provider": "wikimedia-commons-archive",
                    "media_kind": "image",
                    "credit": credit,
                }
        except Exception as exc:
            print(f"[UYARI] Wikimedia görsel arama hatası ({q}): {exc}", file=sys.stderr)

    return None


def fetch_video_playwright(keyword: str, duration_needed: float, out_path: Path, *, portrait: bool = False) -> Dict[str, Any] | None:
    """Phase 4D — Cookie-only, domain-izoleli, ffprobe+decode doğrulamalı Playwright video çekici.

    Pexels/Pixabay icin YALNIZCA PEXELS_COOK / PIXABAY_COOK ortam degiskenlerindeki cookie'leri
    kullanir. YouTube cookies.json / storage_state.json / ENV_FILE bu browser context'ine YUKLENMEZ.
    video_fetcher.js kendi içinde:
        - domain filtreleme,
        - host/redirect/timeout/content-type kontrolu,
        - SHA256,
        - ffprobe (codec,cozunurluk,sure),
        - tam FFmpeg decode
    asamalarini yapar; yalnız tamamen gecerli bir video buldugunda exit 0 doner.
    """
    fetcher_js = BASE_DIR / "video_fetcher.js"
    if not fetcher_js.exists():
        print(f"[UYARI] video_fetcher.js bulunamadı: {fetcher_js}", file=sys.stderr)
        return None

    # video_fetcher.js child'ina YALNIZCA güvenli env + medya cookie'lerini ver
    safe_env_names = {"PATH","HOME","USER","LOGNAME","LANG","LC_ALL","LC_CTYPE","DISPLAY",
                      "TMPDIR","TMP","TEMP","XDG_RUNTIME_DIR","PLAYWRIGHT_BROWSERS_PATH",
                      "PEXELS_COOK","PIXABAY_COOK"}
    child_env = {k: v for k, v in os.environ.items() if k in safe_env_names}

    args = ["node", str(fetcher_js), keyword, str(out_path),
            "--provider", "all",
            "--min-width", "854", "--min-height", "480",
            "--min-duration", str(max(2.0, duration_needed * 0.5)),
            "--max-duration", str(max(10.0, duration_needed * 1.5 + 10)),
            "--max-bytes", str(100 * 1024 * 1024)]
    if portrait:
        args.append("--portrait")

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120,
                                cwd=str(BASE_DIR), env=child_env)
        out_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        downloaded = out_lines[-1] if out_lines else ""

        if result.returncode == 0 and downloaded and Path(downloaded).exists():
            size = Path(downloaded).stat().st_size
            if size > 50_000:
                print(f"[INFO] Playwright video indirildi ve dogrulandi: {downloaded} ({size//1024//1024}MB)", flush=True)
                # video_fetcher.js stderr son satiri "w x h, duration sn, MB, codec=" bilgisi icerir
                return {
                    "url": downloaded,
                    "duration": duration_needed,
                    "provider": "playwright-stock",
                    "media_kind": "video",
                    "local_path": downloaded,
                }
        # Hata sinifini guvenli sekilde logla (cookie/URL sorgu icermez)
        err_lines = [l for l in (result.stderr or "").splitlines() if l.strip()]
        err_tail = err_lines[-1][:240] if err_lines else "(no stderr)"
        print(f"[UYARI] video_fetcher.js başarısız (exit {result.returncode}): {err_tail}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[UYARI] video_fetcher.js timeout ({keyword})", file=sys.stderr)
    except Exception as exc:
        print(f"[UYARI] Playwright video hatası ({keyword}): {str(exc)[:200]}", file=sys.stderr)
    return None


def download_media(url: str, save_path: Path) -> bool:
    try:
        print(f"[INFO] İndiriliyor: {url[:95]}...")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=35)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=16384):
                if chunk:
                    f.write(chunk)
        return save_path.exists() and save_path.stat().st_size > 1024
    except Exception as exc:
        print(f"[HATA] Medya indirme hatası: {exc}", file=sys.stderr)
        return False


def _probe_has_video_stream(path: Path) -> bool:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "json", str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        return False
    try:
        streams = (json.loads(res.stdout).get("streams")) or []
        return len(streams) > 0 and int(streams[0].get("width", 0)) > 0
    except Exception:
        return False


def _srt_time_to_ass(srt_ts: str) -> str:
    """SRT zaman damgasını (`00:00:01,492`) ASS formatına (`0:00:01.49`) dönüştürür."""
    cleaned = srt_ts.strip().replace(",", ".")
    hms, _, frac = cleaned.partition(".")
    parts = hms.split(":")
    hours = int(parts[0]) if len(parts) == 3 else 0
    minutes = int(parts[1]) if len(parts) == 3 else 0
    seconds = int(parts[2]) if len(parts) == 3 else 0
    centis = (frac.ljust(3, "0")[:2]) if frac else "00"
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis}"


def convert_srt_to_ass(srt_path: Path, ass_path: Path) -> None:
    """
    SRT altyazısını YouTube Shorts için yüksek kontrastlı, kalın siyah dış hatlı,
    parlak sarı ve mikro-pop animasyonlu 1080x1920 ASS formatına dönüştürür.
    """
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT dosyası bulunamadı: {srt_path}")

    srt_content = srt_path.read_text(encoding="utf-8")

    ass_header = """[Script Info]
Title: Shorts Dynamic Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat-Bold,56,&H0000FFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,1.5,0,1,5,3,2,70,70,250,1
Style: Hook,Montserrat-Bold,62,&H0026FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2.0,0,1,6,4,2,70,70,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events: List[str] = []
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.strip().splitlines() if ln.strip()]
        if len(lines) >= 3 and " --> " in lines[1]:
            start_raw, end_raw = lines[1].split(" --> ", 1)
            start_ass = _srt_time_to_ass(start_raw)
            end_ass = _srt_time_to_ass(end_raw)
            text = " ".join(lines[2:]).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
            is_hook = start_ass.startswith(("0:00:00.", "0:00:01.", "0:00:02."))
            style_name = "Hook" if is_hook else "Default"
            pop_fx = (
                r"{\fscx82\fscy82\bord6\t(0,90,\fscx106\fscy106)\t(90,150,\fscx100\fscy100)}"
                if is_hook
                else r"{\fscx88\fscy88\t(0,85,\fscx100\fscy100)}"
            )
            events.append(f"Dialogue: 0,{start_ass},{end_ass},{style_name},,0,0,0,,{pop_fx}{text}")

    ass_path.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
    print(f"[INFO] ASS altyazı dosyası oluşturuldu: {ass_path} ({len(events)} dinamik blok)")


def _escape_ffmpeg_filter_path(path: Path) -> str:
    """FFmpeg `ass=` filtresi için dosya yolundaki özel karakterleri kaçırır."""
    raw = str(path.resolve())
    return raw.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def assemble_video_ffmpeg(
    scenes: List[Dict[str, Any]],
    voiceover_path: Path,
    audio_duration: float,
    ass_path: Path,
    output_path: Path,
) -> None:
    """
    Profesyonel FFmpeg kompleks filtre grafiği (Tek Geçişli Filtre-Tabanlı Concat):
      - Her sahneyi bağımsız decode ederek kodek/SPS-PPS uyumsuzluğunu sıfırlar
      - 1080x1920 dikey kadraj (scale + crop + setsar) + sahne bazlı Ken Burns (zoompan, 30fps)
      - 1080x1920 yerel çözünürlüklü ASS altyazı gömme (burn-in)
      - `afftdn` gürültü temizleme + `sidechaincompress` dinamik ses kısma (ducking) + `amix`
    """
    if not scenes:
        raise ValueError("İşlenecek sahne klibi bulunamadı!")

    cmd: List[str] = ["ffmpeg", "-y"]
    v_filter_parts: List[str] = []
    concat_inputs: List[str] = []

    for idx, scene in enumerate(scenes):
        clip_path: Path = scene["path"]
        seg_dur: float = float(scene["duration"])
        media_kind: str = scene["media_kind"]
        if media_kind == "image":
            cmd.extend(["-loop", "1", "-t", f"{seg_dur:.2f}", "-i", str(clip_path.resolve())])
        elif scene.get("loop_allowed", True):
            # Legacy path retains looping; strict storyboard clips must be long enough.
            cmd.extend(["-stream_loop", "-1", "-t", f"{seg_dur:.2f}", "-i", str(clip_path.resolve())])
        else:
            cmd.extend(["-t", f"{seg_dur:.3f}", "-i", str(clip_path.resolve())])

        if scene.get("fit_mode") == "contain":
            # Preserve the whole subject rather than cropping unknown off-centre
            # objects. Real voice/timestamp alignment remains Phase 5 work.
            v_filter_parts.append(
                f"[{idx}:v]fps=30,scale=1080:1920:force_original_aspect_ratio=decrease:out_range=tv,"
                f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setparams=range=limited,"
                f"trim=duration={seg_dur:.3f},setpts=PTS-STARTPTS[v{idx}]"
            )
            concat_inputs.append(f"[v{idx}]")
            continue

        v_filter_parts.append(
            f"[{idx}:v]fps=30,"
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,setsar=1,format=yuv420p,"
            f"unsharp=5:5:1.0:5:5:0.0,"
            f"eq=contrast=1.15:saturation=1.2:brightness=0.05,"
            f"zoompan=z='min(zoom+0.0015,1.5)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
            f"trim=duration={seg_dur:.2f},setpts=PTS-STARTPTS[v{idx}]"
        )
        concat_inputs.append(f"[v{idx}]")

    vo_idx = len(scenes)
    cmd.extend(["-i", str(voiceover_path.resolve())])

    bg_music = ASSETS_DIR / "background_music.mp3"
    has_bg = bg_music.exists()
    if has_bg:
        bg_idx = vo_idx + 1
        cmd.extend(["-stream_loop", "-1", "-i", str(bg_music.resolve())])
        audio_filter = (
            f"[{vo_idx}:a]volume=1.0,asplit=2[vo_sc][vo_mix];"
            f"[{bg_idx}:a]afftdn=nf=-20,volume=0.22[bg_clean];"
            f"[bg_clean][vo_sc]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=300[bg_ducked];"
            f"[vo_mix][bg_ducked]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[a_out]"
        )
    else:
        print("[UYARI] Arka plan müziği bulunamadı, yalnızca seslendirme ile devam ediliyor.", file=sys.stderr)
        audio_filter = f"[{vo_idx}:a]volume=1.0[a_out]"

    escaped_ass = _escape_ffmpeg_filter_path(ass_path)
    concat_chain = f"{''.join(concat_inputs)}concat=n={len(scenes)}:v=1:a=0[v_scaled]"
    sub_chain = (
        f"[v_scaled]subtitles='{escaped_ass}':"
        f"force_style='FontName=Montserrat-Bold,FontSize=56,PrimaryColour=&H0000FFFF,"
        f"OutlineColour=&H00000000,Outline=5,Shadow=3,Alignment=2,MarginV=250'[v_sub]"
    )
    filter_complex = ";".join(v_filter_parts + [concat_chain, sub_chain, audio_filter])

    # Full-range JPEG inputs propagate range flags on FFmpeg 8. Explicitly
    # normalize only the new strict path; don't weaken final yuv420p QC.
    if any(scene.get("fit_mode") == "contain" for scene in scenes):
        cmd.extend(["-color_range", "tv", "-r", "30", "-fps_mode", "cfr"])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[v_sub]",
        "-map", "[a_out]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", f"{audio_duration:.3f}",
        str(output_path.resolve()),
    ])

    print("[INFO] FFmpeg Mobil-Optimize Cinematic filtre zinciri aktif: unsharp=5:5:1.0:5:5:0.0 | eq=contrast=1.15:saturation=1.2:brightness=0.05 | FontSize=56,MarginV=250")
    print("[INFO] FFmpeg render başlatılıyor...")
    print(f"[INFO] [CMD] {' '.join(cmd)}")

    try:
        # Render süresi video uzunluğuna göre değişir; 10 dakikalık sert sınır.
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
        print("[BAŞARILI] FFmpeg render tamamlandı!", flush=True)
    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)
        print("[HATA] FFmpeg render 600 saniyede tamamlanmadı; geçici çıktı silindi.", file=sys.stderr, flush=True)
        raise RuntimeError("FFmpeg render timeout (600s)") from exc
    except subprocess.CalledProcessError as exc:
        output_path.unlink(missing_ok=True)
        print(f"[HATA] FFmpeg başarısız oldu!\nStdout: {exc.stdout}\nStderr: {exc.stderr}", file=sys.stderr)
        raise


def validate_output(output_path: Path) -> Dict[str, Any]:
    """Render edilmiş videoyu yüklemeden önce fail-closed teknik QC'den geçir."""
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"Video çıktısı yok veya boş: {output_path}")

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries",
        (
            "format=duration,size,bit_rate:"
            "stream=codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,"
            "pix_fmt,duration,nb_frames,sample_rate,channels"
        ),
        "-of", "json",
        str(output_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe geçerli JSON döndürmedi; video yayınlanamaz.") from exc

    streams = data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video_streams) != 1 or len(audio_streams) != 1:
        raise RuntimeError(
            f"Tam olarak 1 video ve 1 ses akışı bekleniyordu; video={len(video_streams)}, audio={len(audio_streams)}"
        )
    v_stream, a_stream = video_streams[0], audio_streams[0]
    fmt = data.get("format", {})

    size_mb = output_path.stat().st_size / (1024 * 1024)
    try:
        duration_sec = float(fmt.get("duration", 0.0))
        v_dur = float(v_stream.get("duration", duration_sec))
        a_dur = float(a_stream.get("duration", duration_sec))
        nb_frames = int(v_stream.get("nb_frames", 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("ffprobe video/ses süre veya kare bilgisi eksik/geçersiz.") from exc

    if duration_sec <= 0 or v_dur <= 0 or a_dur <= 0 or nb_frames <= 0:
        raise RuntimeError("Video süresi, akış süresi ve kare sayısı pozitif olmalı.")
    if int(v_stream.get("width", 0)) != 1080 or int(v_stream.get("height", 0)) != 1920:
        raise RuntimeError(
            f"Video dikey 1080x1920 olmalı; bulunan {v_stream.get('width')}x{v_stream.get('height')}"
        )
    if v_stream.get("codec_name") != "h264" or a_stream.get("codec_name") != "aac":
        raise RuntimeError(
            f"Codec uyumsuz: video={v_stream.get('codec_name')}, audio={a_stream.get('codec_name')} (h264/aac bekleniyor)"
        )
    if v_stream.get("pix_fmt") != "yuv420p":
        raise RuntimeError(f"Piksel biçimi yuv420p olmalı; bulunan {v_stream.get('pix_fmt')}")

    # r_frame_rate kesirini güvenli biçimde oku; 29.97 gibi yakın değerleri küçük toleransla kabul et.
    try:
        frame_rate = float(Fraction(str(v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate"))))
    except (ValueError, ZeroDivisionError):
        frame_rate = 0.0
    if abs(frame_rate - 30.0) > 0.25:
        raise RuntimeError(f"Kare hızı 30 FPS olmalı; bulunan {frame_rate:g} FPS")

    if abs(v_dur - a_dur) > 0.6:
        raise RuntimeError(
            f"Video ve ses akışı süre uyumsuzluğu! Video={v_dur:.2f}s, Ses={a_dur:.2f}s"
        )

    print("\n" + "=" * 60)
    print(" 🚀 VİDEO DOĞRULAMA RAPORU 🚀")
    print("=" * 60)
    print(f" Dosya          : {output_path.name}")
    print(f" Boyut (Disk)   : {size_mb:.2f} MB")
    print(f" Süre (Toplam)  : {duration_sec:.2f} saniye (Video: {v_dur:.2f}s / Ses: {a_dur:.2f}s)")
    print(f" Toplam Kare    : {nb_frames} kare ({v_stream.get('r_frame_rate', '30/1')} fps)")
    print(f" Çözünürlük     : {v_stream['width']}x{v_stream['height']} (Dikey 9:16)")
    print(f" Video Kodek    : {v_stream['codec_name']}")
    print(f" Ses Kodek      : {a_stream['codec_name']}")
    print("=" * 60 + "\n")
    return data


def get_visual_search_queries(script_data: Dict[str, Any]) -> List[str]:
    """Prefer validated per-scene storyboard queries; preserve the legacy fallback."""
    storyboard = script_data.get("storyboard")
    if isinstance(storyboard, list) and storyboard:
        queries = [
            str(scene.get("visual_query", "")).strip()
            for scene in storyboard
            if isinstance(scene, dict) and str(scene.get("visual_query", "")).strip()
        ]
        if queries:
            return queries
    legacy = script_data.get("visual_keywords")
    if isinstance(legacy, list):
        queries = [str(item).strip() for item in legacy if str(item).strip()]
        if queries:
            return queries
    return ["history", "nature", "cinematic"]


def run_storyboard_pipeline(script_data: dict, script_json: Path, srt_file: Path, voiceover_mp3: Path) -> Path:
    """Phase 4 strict scene path. Any unfilled scene stops before montage/upload."""
    # main.py still invokes this file directly; keep that public entrypoint and
    # resolve the repository package without relying on runner PYTHONPATH.
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from src.media_processing.scene_media import select_storyboard_media
    from src.media_processing.media_history import atomic_json

    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR, prefix="storyboard_") as work:
        scenes, _report = select_storyboard_media(script_data, Path(work), report_path=OUTPUT_DIR/"scene_media_manifest.json")
        # The post-media validator in main.py will also validate these new fields.
        atomic_json(script_json, script_data)
        ass_path = OUTPUT_DIR/"final.ass"
        convert_srt_to_ass(srt_file, ass_path)
        assemble_video_ffmpeg(scenes, voiceover_mp3, float(script_data["audio_duration_sec"]), ass_path, FINAL_OUTPUT)
    validate_output(FINAL_OUTPUT)
    return FINAL_OUTPUT


def run_media_pipeline() -> Path:
    load_env()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    script_json = _resolve_input_file(SCRIPT_JSON_PATH, "script.json")
    srt_file = _resolve_input_file(SRT_PATH, "voiceover.srt")
    voiceover_mp3 = _resolve_input_file(VOICEOVER_MP3_PATH, "voiceover.mp3")

    if not script_json.exists():
        raise FileNotFoundError(f"Faz 2 çıktısı (script.json) bulunamadı: {script_json}")

    script_data = json.loads(script_json.read_text(encoding="utf-8"))
    # Presence, not truthiness: malformed/empty storyboards must not silently
    # fall through to the generic legacy search path.
    if "storyboard" in script_data:
        return run_storyboard_pipeline(script_data, script_json, srt_file, voiceover_mp3)
    keywords = get_visual_search_queries(script_data)
    audio_duration = float(script_data.get("audio_duration_sec", 30.0))
    per_scene_sec = max(8.0, round((audio_duration + 2.0) / max(1, len(keywords)), 2))

    print(f"[INFO] Hedef süre: {audio_duration:.2f} saniye | Sahne başı: ~{per_scene_sec:.1f}s | Anahtar kelimeler: {keywords}")

    with tempfile.TemporaryDirectory(dir=OUTPUT_DIR, prefix="work_") as work_str:
        work_dir = Path(work_str)
        scenes: List[Dict[str, Any]] = []
        used_urls: set[str] = set()
        current_duration = 0.0
        clip_index = 0

        while current_duration < (audio_duration + 1.0) and clip_index < min(len(keywords) * 2, 8):
            keyword = keywords[clip_index % len(keywords)]
            print(f"[INFO] Aranan kelime ({clip_index + 1}): {keyword}")

            # Önce Playwright (cookie-tabanlı, API key gerektirmez)
            pw_out = work_dir / f"scene_{clip_index}_pw.mp4"
            video_meta = fetch_video_playwright(keyword, audio_duration - current_duration, pw_out)

            # Playwright başarısız → keyless public Wikimedia
            # NOT: Pexels/Pixabay API fallback yolu 2026-11-22'te kullanıcı
            # kararıyla kaldırıldı; stok video yalnız cookie/Playwright ile yürür.
            if not video_meta:
                video_meta = fetch_wikimedia_media(keyword, audio_duration - current_duration, used_urls=used_urls)

            if video_meta and (video_meta.get("url") or video_meta.get("local_path")):
                media_kind = video_meta.get("media_kind", "video")
                # Playwright zaten indirdiyse tekrar indirme
                local_path = video_meta.get("local_path")
                if local_path and Path(local_path).exists():
                    raw_clip = Path(local_path)
                    already_downloaded = True
                else:
                    used_urls.add(video_meta["url"])
                    ext = ".jpg" if media_kind == "image" else ".webm"
                    raw_clip = work_dir / f"scene_{clip_index}{ext}"
                    already_downloaded = download_media(video_meta["url"], raw_clip)
                if already_downloaded and _probe_has_video_stream(raw_clip):
                    scenes.append({
                        "path": raw_clip,
                        "duration": per_scene_sec,
                        "media_kind": media_kind,
                        "provider": video_meta["provider"],
                        "credit": str(video_meta.get("credit") or "").strip(),
                    })
                    current_duration += per_scene_sec
                    print(
                        f"[INFO] Klip eklendi ({video_meta['provider']}, {per_scene_sec:.1f}s). "
                        f"Toplam hazır görüntü süresi: {current_duration:.1f}s"
                    )
                else:
                    print(f"[UYARI] İndirilen medyada geçerli video akışı bulunamadı, atlanıyor: {keyword}")
            else:
                print(f"[UYARI] '{keyword}' için medya bulunamadı, sıradakine geçiliyor.")

            clip_index += 1

        if not scenes:
            raise RuntimeError("Hiçbir video/medya klibi indirilemedi! API anahtarlarını veya ağı kontrol et.")

        # Wikimedia Commons CC BY / CC BY-SA klipleri kullanıldıysa lisans/yazar atfını açıklamaya otomatik ekle
        credits = list(dict.fromkeys(s["credit"] for s in scenes if s.get("credit")))
        if credits:
            desc = str(script_data.get("description") or "").strip()
            missing_credits = [c for c in credits if c not in desc]
            if missing_credits:
                script_data["description"] = (desc + "\n\n" + "\n".join(missing_credits)).strip()[:4900]
                script_Data_credits = list(dict.fromkeys((script_data.get("media_credits") or []) + credits))
                script_data["media_credits"] = script_Data_credits
                script_json.write_text(json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"[LİSANS] {len(missing_credits)} adet Wikimedia CC BY/BY-SA atfı script.json açıklamasına eklendi.")

        ass_path = OUTPUT_DIR / "final.ass"
        convert_srt_to_ass(srt_file, ass_path)

        assemble_video_ffmpeg(
            scenes=scenes,
            voiceover_path=voiceover_mp3,
            audio_duration=audio_duration,
            ass_path=ass_path,
            output_path=FINAL_OUTPUT,
        )

    validate_output(FINAL_OUTPUT)
    return FINAL_OUTPUT


if __name__ == "__main__":
    run_media_pipeline()
