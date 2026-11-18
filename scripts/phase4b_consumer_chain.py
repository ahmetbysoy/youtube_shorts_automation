"""Actual JSON writer/strict wrapper/cover/pure-JS chain with explicit fixtures.

Scenario generation and speech synthesis are REPLACED at their input boundary:
this is not live Gemini, live TTS, fact validation or Phase 5 timing evidence.
Provider catalogs/downloads are real in the live probe, explicit offline fixtures
in CI. No main.py, uploader entrypoint, YouTube, pruner or publisher is imported.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import content_engine
from scripts import embed_cover_frame
from scripts.gemini_web_story import draft_to_script_metadata
from scripts.phase4b_live_evidence import observe_rendered_motion, verify_commons_file_pages
from scripts.validate_script_json import validate_payload
from src.media_processing import media_processor as mp, scene_media
from src.media_processing.media_history import MediaHistory, atomic_json
from src.media_processing.media_providers import now

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = (".used_topics.json", ".media_history.json", ".gemini_topic_ledger.json", "samples/script.json",
             "main.py", "content_engine.py", "src/content_generation/engine.py", "youtube_studio_uploader.js",
             "scripts/embed_cover_frame.py", "scripts/generate_fallback_thumbnail.py",
             ".github/workflows/daily_shorts.yml", ".github/workflows/hourly_pruner.yml", ".github/workflows/draft_publisher.yml")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safety_snapshot() -> dict:
    return {name: sha256(ROOT/name) if (ROOT/name).is_file() else None for name in PROTECTED}


def fixture_draft(provider: str = "wikimedia") -> dict:
    # Curated acceptance input, not a generated production story rewritten to
    # accommodate an unrelated search result. The same board survives every stage.
    board = [
        {"scene_id": 1, "visual_query": "ocean waves beach", "narration": "Okyanus dalgaları sahilde hareket halinde görülüyor.", "media_type": "video"},
        {"scene_id": 2, "visual_query": "waterfall flowing water", "narration": "Şelalede akan suyun görüntüsü burada yer alıyor.", "media_type": "image"},
    ]
    if provider != "wikimedia":
        board[1] = {"scene_id": 2, "visual_query": "forest green trees", "narration": "Orman ağaçları yeşil bir örtü oluşturuyor.", "media_type": "video"}
    text = " ".join(s["narration"] for s in board)
    return {"provider": "explicit_phase4b_fixture_not_live_gemini", "topic": "Yayınsız Faz 4B tüketici testi",
            "title": "Okyanus ve şelale 🌊 — yalnız test #Shorts", "description": "Explicit publication-free fixture; not generated Gemini content, not fact-checked or publishable.",
            "source": {"name": "Explicit test fixture, not a factual research source", "url": "https://commons.wikimedia.org/"},
            "fact_check": {"status": "unavailable", "notes": "Fixture only; no semantic/factual approval.", "claims": []},
            "hook": board[0]["narration"], "script_text": text, "cta_line": "Bu yayınsız bir entegrasyon testidir.",
            "thumbnail_prompt": "Fixture only; no image-generation service may be called.",
            "viral_hashtags": ["#fixture", "#ocean", "#shorts"], "storyboard": board}


def write_fixture_with_actual_root_producer(folder: Path, *, provider: str = "wikimedia", duration: float = 6.0) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    draft = fixture_draft(provider)
    metadata = draft_to_script_metadata(draft)  # actual intermediate transformation
    scenario = {**metadata, "provider": draft["provider"], "word_count": len(draft["script_text"].split()),
                "affiliate_link": None, "affiliate_cta": "Yayınsız fixture CTA; satış bağlantısı yok."}

    def synthetic_speech(*, text, voice, rate, audio_out):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=440:sample_rate=48000:duration={duration}", "-c:a", "libmp3lame", str(audio_out)],
                       check=True, capture_output=True, timeout=30)
        words = text.split()
        timestamps = [{"word": word, "start_ms": round(i*duration*1000/len(words), 3),
                       "end_ms": round((i+1)*duration*1000/len(words), 3)} for i, word in enumerate(words)]
        return "synthetic_test_tone_not_tts_provisional_timestamps", duration, timestamps

    # Execute the ACTUAL root writer, not the independent old package writer.
    # Only these two external-input boundaries are fixture adapters.
    with patch.object(content_engine, "generate_scenario", return_value=scenario), \
         patch.object(content_engine, "synthesize_voiceover", side_effect=synthetic_speech):
        data = content_engine.run_content_pipeline(concept=draft["topic"], gemini_web_only=True,
            audio_out=folder/"voiceover.mp3", txt_out=folder/"script.txt", json_out=folder/"script.json", srt_out=folder/"voiceover.srt")
    if data["storyboard"] != draft["storyboard"]:
        raise ValueError("fixture_storyboard_changed_in_root_writer")
    return data


def validate_file(path: Path) -> dict:
    errors = validate_payload(json.loads(path.read_text()))
    if errors:
        raise ValueError("consumer_chain_schema_rejected")
    # Also exercise the actual CLI gate used by main.py, without executing main.
    result = subprocess.run([sys.executable, "-m", "scripts.validate_script_json", "--input", str(path)],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError("consumer_chain_validator_cli_failed")
    return {"status": "passed", "jsonschema_errors": 0, "runtime_validator_cli_exit": 0, "sha256": sha256(path)}


def full_av_decode(path: Path) -> dict:
    result = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=120)
    if result.returncode or result.stderr.strip():
        raise ValueError("consumer_full_av_decode_failed")
    return {"status": "passed", "sha256": sha256(path), "bytes": path.stat().st_size}


def run_consumer_chain(folder: Path, *, providers: list, provider: str = "wikimedia", duration: float = 6.0,
                       offline_downloader=None, live_provider_calls: bool = True, exercise_cover: bool = True) -> dict:
    folder = folder.resolve()
    before = safety_snapshot()
    report = {"version": 1, "status": "started", "started_at": now(), "live_provider_calls": live_provider_calls,
              "fixture_provider_calls": not live_provider_calls, "publishing": False, "timing_verified": False,
              "visual_verification": "not_performed", "stages": {},
              "producer": {"writer": "content_engine.run_content_pipeline", "writer_executed": False,
                           "transformation": "scripts.gemini_web_story.draft_to_script_metadata",
                           "scenario_boundary": "explicit_fixture_not_live_gemini", "tts_boundary": "synthetic_test_tone_not_tts",
                           "independent_legacy_writer": "src/content_generation/engine.py inventoried, not executed"}}
    try:
        data = write_fixture_with_actual_root_producer(folder, provider=provider, duration=duration)
        report["producer"]["writer_executed"] = True
        original_board = json.loads(json.dumps(data["storyboard"]))
        generation = data["generation_id"]; uuid.UUID(generation)
        report["generation_id"] = generation
        (folder/"pre_media_script.json").write_bytes((folder/"script.json").read_bytes())
        report["stages"]["pre_media_validator"] = validate_file(folder/"script.json")
        # Configure isolated paths and the provider/history factories only. The
        # public run_media_pipeline -> strict wrapper -> selector -> persistence
        # -> real ASS/FFmpeg/QC code is NOT replaced or bypassed.
        paths = {"BASE_DIR": folder, "SCRIPT_JSON_PATH": folder/"script.json", "SRT_PATH": folder/"voiceover.srt",
                 "VOICEOVER_MP3_PATH": folder/"voiceover.mp3", "OUTPUT_DIR": folder, "ASSETS_DIR": folder/"assets",
                 "FINAL_OUTPUT": folder/"consumer.mp4"}
        with ExitStack() as stack:
            for name, value in paths.items(): stack.enter_context(patch.object(mp, name, value))
            stack.enter_context(patch.object(scene_media, "default_providers", return_value=providers))
            stack.enter_context(patch.object(scene_media.MediaHistory, "from_environment", return_value=MediaHistory(folder/"isolated_history.json")))
            if offline_downloader is not None:
                stack.enter_context(patch.object(scene_media, "download_candidate", side_effect=offline_downloader))
            video = mp.run_media_pipeline()  # actual public wrapper, not assembler-only smoke
        report["stages"]["strict_media_wrapper"] = {"status": "passed", "entrypoint": "run_media_pipeline", "legacy_fallback_used": False,
                                                     "history_scope": "isolated_local_selection_history_not_cross_actions_proof"}
        # Reload EXACTLY the same JSON path written by the actual media wrapper.
        persisted = json.loads((folder/"script.json").read_text())
        if persisted["generation_id"] != generation or persisted["storyboard"] != original_board:
            raise ValueError("same_json_identity_or_storyboard_changed")
        if [s["scene_id"] for s in persisted["scene_media"]] != [s["scene_id"] for s in original_board]:
            raise ValueError("consumer_scene_coverage_mismatch")
        report["stages"]["post_media_validator"] = validate_file(folder/"script.json")
        media_hash = sha256(folder/"script.json")
        report["stages"]["pre_cover_decode"] = full_av_decode(video)
        # Read-only JSON consumer, real no-network cover main on the isolated
        # video. Best-effort return 0 is NOT enough: require an actual cover and
        # changed video. No AI/free-vision/Gemini service or Studio is executed.
        if exercise_cover:
            cover = folder/"cover.jpg"; old_video_hash = sha256(video)
            argv = ["embed_cover_frame.py", "--video", str(video), "--script", str(folder/"script.json"),
                    "--cover-out", str(cover), "--seconds", str(min(0.5, duration/4)), "--no-ai"]
            with patch.object(sys, "argv", argv):
                exit_code = embed_cover_frame.main()
            if exit_code or not cover.is_file() or cover.stat().st_size <= 5000 or sha256(video) == old_video_hash:
                raise ValueError("actual_offline_cover_consumer_failed")
            if sha256(folder/"script.json") != media_hash:
                raise ValueError("cover_consumer_mutated_json")
            report["stages"]["cover_read_only_consumer"] = {"status": "passed", "entrypoint": "embed_cover_frame.main --no-ai",
                "json_unchanged": True, "same_json_sha256": media_hash, "actual_cover_generated_and_overlaid": True,
                "ai_or_network_called": False, "semantic_cover_approval": False}
        else:
            report["stages"]["cover_read_only_consumer"] = {"status": "not_requested"}
        pure = subprocess.run(["node", str(ROOT/"scripts/uploader_metadata_probe.cjs")], input=json.dumps(persisted),
                              capture_output=True, text=True, check=True, timeout=20)
        metadata = json.loads(pure.stdout)
        credits = [s["attribution"] for s in persisted["scene_media"] if s["license"]["attribution_required"]]
        if not all(c in persisted["description"] and c in persisted["media_credits"] and c in metadata["description"] for c in credits):
            raise ValueError("required_credit_not_preserved_across_consumers")
        upper = scene_media.uploader_description_upper_bound(persisted, persisted["description"])
        if metadata["utf16_units"] > upper or upper > 4900 or sha256(folder/"script.json") != media_hash:
            raise ValueError("pure_metadata_credit_budget_or_json_identity_failed")
        atomic_json(folder/"uploader_pure_metadata.json", metadata)
        report["stages"]["uploader_pure_metadata_consumer"] = {"status": "passed", "utf16_units": metadata["utf16_units"],
            "conservative_utf16_upper_bound": upper, "budget": 4900, "required_credits_count": len(credits), "all_required_credits_preserved": True,
            "entrypoint_executed": False, "uploader_source_sha256": metadata["uploader_source_sha256"],
            "extracted_functions_sha256": metadata["extracted_functions_sha256"]}
        report["stages"]["final_qc"] = {"status": "passed", **mp.validate_output(video)}
        report["stages"]["full_av_decode"] = full_av_decode(video)
        if live_provider_calls and provider == "wikimedia":
            report["stages"]["actual_source_and_license_http"] = {str(s["scene_id"]): verify_commons_file_pages(s) for s in persisted["scene_media"]}
        else:
            report["stages"]["actual_source_and_license_http"] = {"status": "not_run_offline_fixture_or_non_commons"}
        elapsed = 0.0
        report["motion_evidence"] = {}
        for index, scene in enumerate(persisted["scene_media"]):
            if scene["media_type"] == "video":
                motion = observe_rendered_motion(video, scene, elapsed, folder,
                    cover_seconds=min(0.5, duration/4) if exercise_cover and index == 0 else 0)
                report["motion_evidence"][str(scene["scene_id"])] = motion
                if motion["status"] != "temporal_pixel_change_observed":
                    raise ValueError("moving_video_evidence_not_observed")
            at = elapsed+scene["planned_duration"]/2
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=360:640", str(folder/f"scene_{scene['scene_id']}_inspection.jpg")], check=True, capture_output=True, timeout=30)
            elapsed += scene["planned_duration"]
        report["selected_media"] = [{"scene_id": s["scene_id"], "provider": s["selected_provider"], "media_id": s["selected_media_id"],
            "source_url": s["source_url"], "download_url": s["media"]["download_url"], "media_type": s["media_type"], "license": s["license"],
            "sha256": s["file_probe"]["sha256"], "measured_resolution": s["resolution"], "measured_aspect_ratio": s["aspect_ratio"],
            "measured_duration": s["duration"], "decode_status": s["file_probe"]["decode_status"],
            "acceptance_rationale": "source_and_file_license_gates_plus_full_decode_and_measured_technical_gates; metadata_supported_not_visual_approval",
            "consumer_result": "passed"} for s in persisted["scene_media"]]
        report["real_video_selected"] = any(s["media_type"] == "video" for s in persisted["scene_media"])
        report["required_cc_by_selected"] = any(s["license"]["attribution_required"] and s["license"]["name"].startswith("CC BY ") for s in persisted["scene_media"])
        report["same_json_identity_preserved"] = True
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "blocked_unverified" if isinstance(exc, scene_media.SceneMediaError) else "failed"
        report["error_type"] = type(exc).__name__
        if isinstance(exc, scene_media.SceneMediaError): report["failure"] = exc.report["failure"]
    finally:
        after = safety_snapshot()
        report["protected_files_unchanged"] = before == after
        report["protected_file_sha256"] = after
        if before != after: report["status"] = "failed_production_isolation"
        report["completed_at"] = now()
        atomic_json(folder/"chain.json", report)
    return report
