"""Actual offline fixture chain. NOT live Gemini, TTS or provider evidence."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import content_engine
from scripts.phase4b_consumer_chain import ROOT, run_consumer_chain, sha256
from src.media_processing.media_providers import MediaCandidate, commons_license
from tests.test_phase4_media import Provider


def offline_catalog(tmp_path):
    video = tmp_path/"synthetic_source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", str(video)], capture_output=True, check=True, timeout=30)
    image = tmp_path/"synthetic_source.jpg"
    Image.linear_gradient("L").resize((1440, 2160)).convert("RGB").save(image, quality=95)
    files, candidates = {}, {}
    for mid, title, kind, width, height in [("fixture-video", "Ocean waves beach synthetic offline fixture", "video", 1280, 720),
                                          ("fixture-image", "Waterfall flowing water synthetic offline fixture", "image", 1440, 2160)]:
        source = f"https://commons.wikimedia.org/wiki/File:{mid}"
        # Fabricated license declarations for an offline regression, not rights
        # evidence about a real Wikimedia file or an external downloaded asset.
        lic = commons_license({"title": "File:"+title}, {"descriptionurl": source, "extmetadata": {
            "Artist": {"value": "Synthetic Fixture Author"}, "AttributionRequired": {"value": "true"},
            "LicenseShortName": {"value": "CC BY 4.0"}, "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"}}})
        c = MediaCandidate("wikimedia", mid, source, f"https://upload.wikimedia.org/{mid}", kind, width, height, 2 if kind == "video" else None,
                           title=title, license=lic, catalog_transport="offline_fixture_not_live")
        candidates[kind] = c; files[mid] = video if kind == "video" else image
    provider = Provider(lambda query: [candidates["video" if query.startswith("ocean") else "image"]], "explicit-offline-fixture")
    def downloader(candidate, path):
        shutil.copyfile(files[candidate.media_id], path)
        return path
    return provider, downloader


def test_actual_root_writer_same_json_strict_wrapper_pre_post_schema_cover_pure_uploader_and_full_decode(tmp_path):
    if not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node")): pytest.skip("FFmpeg/ffprobe/Node required")
    provider, downloader = offline_catalog(tmp_path)
    folder = tmp_path/"chain"
    result = run_consumer_chain(folder, providers=[provider], duration=1.2, offline_downloader=downloader, live_provider_calls=False)
    assert result["status"] == "passed", result
    assert not result["live_provider_calls"] and result["fixture_provider_calls"]
    assert result["producer"]["writer_executed"] and result["producer"]["writer"] == "content_engine.run_content_pipeline"
    assert result["same_json_identity_preserved"] and result["protected_files_unchanged"]
    assert result["real_video_selected"] and result["required_cc_by_selected"]
    assert result["stages"]["pre_media_validator"]["jsonschema_errors"] == result["stages"]["post_media_validator"]["jsonschema_errors"] == 0
    assert result["stages"]["cover_read_only_consumer"]["json_unchanged"]
    assert result["stages"]["cover_read_only_consumer"]["actual_cover_generated_and_overlaid"]
    metadata = result["stages"]["uploader_pure_metadata_consumer"]
    assert not metadata["entrypoint_executed"] and metadata["all_required_credits_preserved"]
    assert metadata["utf16_units"] <= metadata["conservative_utf16_upper_bound"] <= 4900
    assert metadata["uploader_source_sha256"] == sha256(ROOT/"youtube_studio_uploader.js")
    before = json.loads((folder/"pre_media_script.json").read_text()); after = json.loads((folder/"script.json").read_text())
    assert before["generation_id"] == after["generation_id"]
    assert before["storyboard"] == after["storyboard"] and before["fact_check"] == after["fact_check"]
    assert after["fact_check"]["status"] == "unavailable"
    assert [m["scene_id"] for m in after["scene_media"]] == [1, 2]
    assert result["stages"]["full_av_decode"]["status"] == "passed"
    assert not result["timing_verified"] and result["visual_verification"] == "not_performed"


def test_actual_wrapper_with_unfilled_scene_stops_before_render_cover_and_metadata(tmp_path):
    folder = tmp_path/"blocked"
    result = run_consumer_chain(folder, providers=[Provider([])], duration=1.2, live_provider_calls=False)
    assert result["status"] == "blocked_unverified" and result["protected_files_unchanged"]
    assert result["stages"]["pre_media_validator"]["status"] == "passed"
    assert "post_media_validator" not in result["stages"] and "cover_read_only_consumer" not in result["stages"]
    assert not (folder/"consumer.mp4").exists() and not (folder/"isolated_history.json").exists()
    assert (folder/"script.json").read_bytes() == (folder/"pre_media_script.json").read_bytes()


def test_producer_inventory_does_not_misidentify_independent_legacy_writer_as_root():
    from src.content_generation.engine import run_content_pipeline as old_writer
    from src.content_generation import run_content_pipeline as exported_old_writer
    assert old_writer is exported_old_writer and old_writer is not content_engine.run_content_pipeline
    assert old_writer.__module__ == "src.content_generation.engine"
    assert content_engine.run_content_pipeline.__module__ == "content_engine"


def test_motion_evidence_rejects_a_constant_frame_video_despite_valid_container_and_decode(tmp_path):
    from scripts.phase4b_live_evidence import observe_rendered_motion
    video = tmp_path/"constant.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:size=1080x1920:rate=30:duration=1",
                    "-c:v", "libx264", "-preset", "ultrafast", str(video)], capture_output=True, check=True, timeout=30)
    result = observe_rendered_motion(video, {"scene_id": 1, "planned_duration": 1, "resolution": {"width": 1920, "height": 1080}}, 0, tmp_path)
    assert result["status"] == "no_temporal_change_observed" and result["mean_absolute_rgb_difference_0_to_255"] == 0


@pytest.mark.parametrize("fault", [None, "canonical", "creator", "license_link"])
def test_file_page_and_official_license_http_evidence_is_independent_of_api_metadata(fault):
    from unittest.mock import Mock, patch
    from scripts.phase4b_live_evidence import verify_commons_file_pages
    source = "https://commons.wikimedia.org/wiki/File:Fixture.webm"
    canonical = "https://evil.test/other" if fault == "canonical" else source
    creator = "Other creator" if fault == "creator" else "Fixture Author"
    href = "https://creativecommons.org/licenses/by-sa/4.0/deed.en" if fault == "license_link" else "//creativecommons.org/licenses/by/4.0/deed.en"
    body = f'<link rel="canonical" href="{canonical}"><div id="mw-content-text">{creator}<a href="{href}">license</a></div>'
    def http(text):
        r = Mock(status_code=200, text=text); r.__enter__ = Mock(return_value=r); r.__exit__ = Mock(return_value=None)
        return r
    with patch("scripts.phase4b_live_evidence.get_public", side_effect=[http(body), http("Share Adapt Attribution")]):
        scene = {"source_url": source, "license": {"url": "https://creativecommons.org/licenses/by/4.0", "creator": "Fixture Author"}}
        if fault:
            with pytest.raises(ValueError): verify_commons_file_pages(scene)
        else:
            result = verify_commons_file_pages(scene)
            assert result["source_page_http_status"] == result["license_deed_http_status"] == 200
            assert result["canonical_file_identity_matched"] and not result["third_party_rights_verified"]
