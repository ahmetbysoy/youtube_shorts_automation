"""Bounded, publication-free Commons A-L diagnostics, NOT a consumer substitute."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.phase4b_consumer_chain import fixture_draft
from scripts.phase4b_live_evidence import verify_commons_file_pages
from src.media_processing.media_history import atomic_json
from src.media_processing.media_io import MediaIOError, download_candidate, io_evidence, probe_media
from src.media_processing.media_providers import WikimediaProvider, now, public_url
from src.media_processing.scene_media import evaluate, provider_issue, scene_plan


def diagnose_commons(work: Path, *, provider=None, downloader=download_candidate, prober=probe_media,
                     license_checker=verify_commons_file_pages, live_provider_calls=True) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    provider = WikimediaProvider() if provider is None else provider
    result = {"version": 1, "started_at": now(), "live_provider_calls": live_provider_calls,
        "publishing": False, "raw_media_staged": False, "candidate_limit": 2, "candidates": [],
        "source_metadata_http": {"status": "not_reached"}, "status": "failed"}
    draft = fixture_draft("wikimedia")
    scene = scene_plan({"storyboard": draft["storyboard"], "audio_duration_sec": 6.0})[0]
    query = scene["primary_query"]
    try:
        candidates = provider.search(query)[:8]
        result["source_metadata_http"] = {"status": "passed", "responses": getattr(provider, "last_diagnostics", {}).get("metadata_http_responses", [])}
        eligible = [(c, evaluate(c, scene, query, used=set(), recent=[])) for c in candidates]
        eligible = [(c, v) for c, v in eligible if c.media_type == "video" and v["eligible"]]
        eligible.sort(key=lambda x: (-x[1]["score"], x[0].key))
        with TemporaryDirectory(prefix="commons-io-", dir=work) as temporary:
            for index, (candidate, verdict) in enumerate(eligible[:2]):
                stages = {"source_metadata_http": result["source_metadata_http"], "license_evidence_http": {"status": "not_reached"},
                    **io_evidence(), "consumer_render": {"status": "not_reached"}, "final_mp4_qc": {"status": "not_reached"}}
                item = {"provider": "wikimedia", "media_id": candidate.media_id, "scene_id": scene["scene_id"], "query": query,
                    "source_url": public_url(candidate.source_url), "download_url": public_url(candidate.download_url),
                    "license": asdict(candidate.license), "metadata_assessment": verdict, "stages": stages, "status": "failed"}
                result["candidates"].append(item)
                license_trace = {}
                try:
                    proof = license_checker({"source_url": candidate.source_url, "license": asdict(candidate.license)}, evidence=license_trace)
                    stages["license_evidence_http"] = {"status": "passed", "http_stages": license_trace, "proof": proof}
                except Exception:
                    stages["license_evidence_http"] = {"status": "failed", "error_class": "license_evidence_failed", "http_stages": license_trace}
                # Metadata license gates already passed. Diagnose IO independently
                # even when the supplemental File/deed HTTP fails; NEVER assign a
                # scene or call this full source/license/consumer acceptance.
                path = Path(temporary)/f"candidate_{index}.webm"
                try:
                    downloader(candidate, path, evidence=stages)
                    measured = prober(path, "video", evidence=stages)
                    item["measured_file"] = measured
                    item["status"] = "download_probe_decode_passed_not_consumer"
                except MediaIOError as exc:
                    item["safe_error_class"] = exc.safe_error_class
                except Exception:
                    item["safe_error_class"] = "probe_failed"
        result["status"] = "io_evidence_collected" if result["candidates"] else "no_metadata_eligible_video"
    except Exception as exc:
        result["source_metadata_http"] = {"status": "failed", **provider_issue(provider, query, exc)}
    result["completed_at"] = now()
    return result


def link_actual_consumer(diagnostics: dict, chain: dict) -> None:
    """Only link matching ID AND byte SHA; independent diagnostic != render."""
    selected = {s["media_id"]: s for s in chain.get("selected_media", [])}
    stages = chain.get("stages", {})
    diagnostics["actual_chain_status"] = chain["status"]
    for item in diagnostics["candidates"]:
        match = selected.get(item["media_id"])
        same_bytes = bool(match and match["sha256"] == item.get("measured_file", {}).get("sha256"))
        render = stages.get("strict_media_wrapper", {})
        qc, decode = stages.get("final_qc", {}), stages.get("full_av_decode", {})
        if same_bytes and render.get("status") == "passed":
            item["stages"]["consumer_render"] = {"status": "passed", "same_source_id_and_sha256": True, "proof": render,
                "full_chain_status_separate": chain["status"]}
            if qc:
                status = "passed" if qc.get("status") == decode.get("status") == "passed" else "failed" if "failed" in (qc.get("status"), decode.get("status")) else "incomplete"
                item["stages"]["final_mp4_qc"] = {"status": status, "proof": qc, "full_av_decode": decode}
        elif same_bytes and render.get("error_class") == "consumer_render_failed":
            item["stages"]["consumer_render"] = {"status": "failed", "same_source_id_and_sha256": True, "error_class": "consumer_render_failed"}
        elif render.get("status") == "passed":
            item["stages"]["consumer_render"] = {"status": "not_associated_with_this_candidate"}
        # A failed selection leaves render/QC explicitly not_reached. A later
        # license failure never erases an already measured successful render.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    atomic_json(args.output, diagnose_commons(args.work))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
