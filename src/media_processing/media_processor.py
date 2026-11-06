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


def _is_real_api_key(val: str | None) -> bool:
    if not val:
        return False
    cleaned = val.strip()
    if not cleaned or "senin_gercek" in cleaned.lower() or "your_" in cleaned.lower():
        return False
    return True


def _resolve_input_file(primary: Path, sample_name: str) -> Path:
    """Dosya kökte yoksa `output/` veya `samples/` dizinlerinden bulur."""
    if primary.exists():
        return primary
    for candidate in (OUTPUT_DIR / sample_name, BASE_DIR / "samples" / sample_name):
        if candidate.exists():
            return candidate
    return primary


def fetch_pexels_video(keyword: str, duration_needed: float) -> Dict[str, Any] | None:
    api_key = os.environ.get("PEXELS_API_KEY")
    if not _is_real_api_key(api_key):
        return None

    headers = {"Authorization": api_key.strip(), "User-Agent": USER_AGENT}
    url = (
        f"https://api.pexels.com/videos/search"
        f"?query={requests.utils.quote(keyword)}&orientation=portrait&per_page=8&min_duration=5"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = data.get("videos") or []
        if videos:
            video = random.choice(videos)
            video_files = [f for f in video.get("video_files", []) if f.get("link")]
            if not video_files:
                return None
            target_file = next(
                (f for f in video_files if f.get("width") == 1080 and f.get("height", 0) >= 1920),
                sorted(video_files, key=lambda x: x.get("height", 0), reverse=True)[0],
            )
            return {
                "url": target_file["link"],
                "duration": float(video.get("duration", 10.0)),
                "provider": "pexels",
                "media_kind": "video",
            }
    except Exception as exc:
        print(f"[UYARI] Pexels API hatası ({keyword}): {exc}", file=sys.stderr)
    return None


def fetch_pixabay_video(keyword: str, duration_needed: float) -> Dict[str, Any] | None:
    api_key = os.environ.get("PIXABAY_API_KEY")
    if not _is_real_api_key(api_key):
        return None

    # Pixabay requires the API key in the query. Never print the URL or an
    # exception containing it; do not forward it through HTTP redirects.
    url = "https://pixabay.com/api/videos/"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT},
                            params={"key": api_key.strip(), "q": keyword, "min_width": 1080, "per_page": 8},
                            timeout=15, allow_redirects=False)
        if 300 <= resp.status_code < 400:
            print("[UYARI] Pixabay yönlendirmesi güvenlik nedeniyle reddedildi.", file=sys.stderr)
            return None
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits") or []
        if hits:
            hit = random.choice(hits)
            videos = hit.get("videos", {})
            target_file = videos.get("large") or videos.get("medium") or {}
            if target_file.get("url"):
                return {
                    "url": target_file["url"],
                    "duration": float(hit.get("duration", 10.0)),
                    "provider": "pixabay",
                    "media_kind": "video",
                }
    except Exception as exc:
        # The exception may contain the full query URL and API key.
        print(f"[UYARI] Pixabay API hatası ({keyword}): {type(exc).__name__}; yerel/diğer yedek deneniyor.", file=sys.stderr)
    return None


def _build_query_variants(keyword: str) -> List[str]:
    variants = [keyword.strip()]
    words = [w for w in keyword.strip().split() if w.lower() not in STOPWORDS_SIMPLIFY]
    if words and " ".join(words) not in variants:
        variants.append(" ".join(words))
    if words and words[0] not in variants:
        variants.append(words[0])
    return variants


def fetch_wikimedia_media(keyword: str, duration_needed: float, used_urls: set[str] | None = None) -> Dict[str, Any] | None:
    """
    Üçüncül Medya Katmanı (sıfır anahtar; dosya bazlı lisans/atıf doğrulaması gerekir):
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
                    "iiprop": "url|size|mime",
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
                    valid_videos.append(url)
            if valid_videos:
                chosen = valid_videos[0]
                return {
                    "url": chosen,
                    "duration": 10.5,
                    "provider": "wikimedia-commons-video",
                    "media_kind": "video",
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
                    "iiprop": "url|size|mime",
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
                    valid_images.append(thumb_url)
            if valid_images:
                chosen = valid_images[0]
                return {
                    "url": chosen,
                    "duration": 10.5,
                    "provider": "wikimedia-commons-archive",
                    "media_kind": "image",
                }
        except Exception as exc:
            print(f"[UYARI] Wikimedia görsel arama hatası ({q}): {exc}", file=sys.stderr)

    return None


def fetch_video_playwright(keyword: str, duration_needed: float, out_path: Path) -> Dict[str, Any] | None:
    """
    API key gerektirmeyen Playwright tabanlı video çekici.
    Pixabay/Pexels oturumunu (cookies.json) kullanarak video indirir.
    video_fetcher.js scriptini çağırır.
    """
    fetcher_js = BASE_DIR / "video_fetcher.js"
    if not fetcher_js.exists():
        print(f"[UYARI] video_fetcher.js bulunamadı: {fetcher_js}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            ["node", str(fetcher_js), keyword, str(out_path)],
            capture_output=True, text=True, timeout=75,
            cwd=str(BASE_DIR)
        )
        # stdout'un son satırı indirilen dosya yolu
        out_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        downloaded = out_lines[-1] if out_lines else ""

        if result.returncode == 0 and downloaded and Path(downloaded).exists():
            size = Path(downloaded).stat().st_size
            if size > 50_000:
                print(f"[INFO] Playwright video indirildi: {downloaded} ({size//1024//1024}MB)", flush=True)
                return {
                    "url": downloaded,
                    "duration": duration_needed,
                    "provider": "playwright-pixabay",
                    "media_kind": "video",
                    "local_path": downloaded,
                }
        print(f"[UYARI] video_fetcher.js başarısız (exit {result.returncode}): {result.stderr[-200:]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[UYARI] video_fetcher.js timeout ({keyword})", file=sys.stderr)
    except Exception as exc:
        print(f"[UYARI] Playwright video hatası ({keyword}): {exc}", file=sys.stderr)
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
            pop_fx = r"{\fscx88\fscy88\t(0,85,\fscx100\fscy100)}"
            events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pop_fx}{text}")

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
        else:
            cmd.extend(["-stream_loop", "-1", "-t", f"{seg_dur:.2f}", "-i", str(clip_path.resolve())])

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
    """Render edilen videonun ffprobe ile tam teknik ve akış bütünlüğü doğrulaması."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate,duration,nb_frames",
        "-of", "json",
        str(output_path.resolve()),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    v_stream = next(s for s in streams if s.get("codec_type") == "video")
    a_stream = next(s for s in streams if s.get("codec_type") == "audio")
    fmt = data.get("format", {})

    size_mb = output_path.stat().st_size / (1024 * 1024)
    duration_sec = float(fmt.get("duration", 0.0))
    v_dur = float(v_stream.get("duration", duration_sec))
    a_dur = float(a_stream.get("duration", duration_sec))
    nb_frames = int(v_stream.get("nb_frames", 0))

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
    keywords: List[str] = script_data.get("visual_keywords") or ["history", "nature", "cinematic"]
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

            # Playwright başarısız → API key varsa klasik yöntem
            if not video_meta:
                video_meta = (
                    fetch_pexels_video(keyword, audio_duration - current_duration)
                    or fetch_pixabay_video(keyword, audio_duration - current_duration)
                    or fetch_wikimedia_media(keyword, audio_duration - current_duration, used_urls=used_urls)
                )

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
