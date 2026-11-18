"""Real HTTP/catalog/download/license evidence, deliberately no uploader imports.

The fixed two-scene scripts are probe inputs, NOT Gemini/real TTS outputs. A local
history file inside the output directory isolates this probe from production state.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

from dotenv import dotenv_values
from io import StringIO

from scripts.validate_script_json import validate_payload
from src.media_processing.media_history import MediaHistory, atomic_json
from src.media_processing.media_processor import assemble_video_ffmpeg, convert_srt_to_ass, validate_output
from src.media_processing.media_providers import BrowserStockProvider, PexelsProvider, PixabayProvider, StockTerms, WikimediaProvider, now
from src.media_processing.scene_media import SceneMediaError, select_storyboard_media


def input_script(provider: str) -> dict:
    common = [
        {"scene_id": 1, "visual_query": "Moon Apollo astronaut", "alternative_queries": ["Apollo 11 Moon Aldrin"], "narration": "Apollo astronot Ay yüzeyinde duruyor."},
        {"scene_id": 2, "visual_query": "Eiffel Tower Paris", "alternative_queries": ["Eiffel Tower Paris France"], "narration": "Paris Eyfel kulesi görülüyor."},
    ]
    stock = [
        {"scene_id": 1, "visual_query": "ocean sea waves", "alternative_queries": ["ocean waves", "sea waves water"], "narration": "Okyanus dalgaları deniz üzerinde hareket ediyor."},
        {"scene_id": 2, "visual_query": "forest green trees", "alternative_queries": ["forest trees", "green forest tree"], "narration": "Orman ağaçları yeşil bir örtü oluşturuyor."},
    ]
    board = common if provider == "wikimedia" else stock
    text = " ".join(s["narration"] for s in board)
    return {"schema_version": "2.0", "generation_id": str(uuid.uuid4()), "generated_at": now(),
            "llm_provider": "fixed-publication-free-probe-input-not-generated", "tts_engine": "synthetic-tone-not-tts",
            "topic": "Phase 4 media-only probe", "title": "Publication-free Phase 4 source proof", "description": "Source/license/download probe only; not for YouTube publication.",
            "hook": board[0]["narration"], "script_text": text, "word_count": len(text.split()), "audio_file": "test_tone.mp3",
            "srt_file": "test.srt", "audio_duration_sec": 6.0, "visual_keywords": [s["visual_query"] for s in board], "word_timestamps": [], "storyboard": board}


def optional_keys_from_existing_secret() -> None:
    # Parse dotenv as DATA, never shell source/eval it; only two allowed names
    # enter this process. Do not write ENV_FILE or unrelated secrets to disk.
    text = os.environ.pop("PHASE4_PROVIDER_ENV", "")
    if text:
        parsed = dotenv_values(stream=StringIO(text), interpolate=False)
        for key in ("PEXELS_API_KEY", "PIXABAY_API_KEY"):
            if not os.environ.get(key) and parsed.get(key): os.environ[key] = parsed[key]


def render_smoke(scenes: list[dict], script: dict, output: Path) -> dict:
    tone = output/"test_tone.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=6", "-c:a", "libmp3lame", str(tone)],
                   check=True, capture_output=True, timeout=30)
    srt = output/"test.srt"
    # Explicit synthetic smoke timestamps. Real narration/word alignment is NOT tested.
    srt.write_text("1\n00:00:00,000 --> 00:00:03,000\nMEDIA PROBE - NOT FOR PUBLICATION\n\n2\n00:00:03,000 --> 00:00:06,000\nPROVISIONAL TIMING - SYNTHETIC TONE\n", encoding="utf-8")
    ass = output/"test.ass"; convert_srt_to_ass(srt, ass)
    video = output/"media_probe.mp4"
    assemble_video_ffmpeg(scenes, tone, script["audio_duration_sec"], ass, video)
    qc = validate_output(video)
    # Two inspection frames, each from the corresponding provisional scene.
    elapsed = 0.0
    for index, scene in enumerate(scenes, 1):
        at = elapsed+scene["duration"]/2
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=360:640", str(output/f"scene_{index}_inspection.jpg")],
                       capture_output=True, check=True, timeout=30)
        elapsed += scene["duration"]
    return {"status": "passed", "audio_source": "synthetic_test_tone_not_tts", "timing_verified": False,
            "format": qc.get("format", {}), "streams": qc.get("streams", []), "file": str(video.name)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["all", "pexels", "pixabay", "wikimedia"], default="all")
    parser.add_argument("--output", type=Path, default=Path("output/phase4_probe"))
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    optional_keys_from_existing_secret()
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = {"version": 1, "started_at": now(), "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_sha": os.environ.get("GITHUB_SHA"),
                "live_provider_calls": True, "mock_provider_calls": False, "publishing": False, "production_history_modified": False,
                "timing_verified": False, "providers": {}, "overall": "not_accepted"}
    names = ["pexels", "pixabay", "wikimedia"] if args.provider == "all" else [args.provider]
    for name in names:
        folder = args.output/name; folder.mkdir(exist_ok=True)
        terms = StockTerms()
        configured = True
        if name == "wikimedia": providers = [WikimediaProvider()]
        else:
            key_present = bool(os.environ.get("PEXELS_API_KEY" if name == "pexels" else "PIXABAY_API_KEY"))
            cookie_present = any(Path(p).exists() for p in ("cookies.json", "storage_state.json"))
            configured = key_present or cookie_present
            providers = [PexelsProvider(terms=terms) if name == "pexels" else PixabayProvider(terms=terms), BrowserStockProvider(name, terms=terms)]
        item = {"configured": configured, "live_selection": "not_run", "selected_scenes": 0, "catalog_transports": []}
        evidence["providers"][name] = item
        if not configured:
            item["live_selection"] = "not_configured_unverified"
            print(f"PROVIDER={name} status=not_configured_unverified", flush=True)
            continue
        data = input_script(name)
        try:
            scenes, report = select_storyboard_media(data, folder/"media", providers=providers, history=MediaHistory(folder/"history.json"), report_path=folder/"manifest.json")
            errors = validate_payload(data)
            if errors: raise ValueError("post_selection_schema_rejected")
            atomic_json(folder/"script.json", data)
            item.update(live_selection="passed", selected_scenes=len(scenes), catalog_transports=sorted({r["media"]["catalog_transport"] for r in report["scenes"]}),
                        manifest=f"{name}/manifest.json", license_evidence=[{"name": r["license"]["name"], "url": r["license"]["url"], "evidence_url": r["license"]["evidence_url"], "method": r["license"]["evidence_method"]} for r in report["scenes"]])
            if args.render and name == "wikimedia": item["render_smoke"] = render_smoke(scenes, data, folder)
            print(f"PROVIDER={name} status=passed scenes={len(scenes)} relevance=metadata_supported visual_verification=not_performed", flush=True)
        except SceneMediaError as exc:
            item["live_selection"] = "blocked_unverified"
            item["failure"] = exc.report["failure"]
            print(f"PROVIDER={name} status=blocked_unverified", flush=True)
        except Exception as exc:
            item["live_selection"] = "failed"
            item["error_type"] = type(exc).__name__
            print(f"PROVIDER={name} status=failed type={type(exc).__name__}", flush=True)
        atomic_json(args.output/"evidence.json", evidence)
    passed = [k for k, v in evidence["providers"].items() if v["live_selection"] == "passed"]
    evidence["all_requested_providers_verified"] = len(passed) == len(names)
    evidence["overall"] = "all_requested_providers_passed" if len(passed) == len(names) else "partial_provider_evidence" if passed else "no_live_provider_success"
    evidence["completed_at"] = now()
    atomic_json(args.output/"evidence.json", evidence)
    print(f"PHASE4_LIVE_RESULT={evidence['overall']}", flush=True)
    # Unavailable provider coverage stays explicit in the evidence; do not turn
    # missing API keys into a false green provider-integration claim.
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
