"""FAZ 4B live media and actual consumer-chain evidence, never a publication.

The nonzero result for blocked stock coverage is intentional: partial evidence
is not full acceptance. The Commons and each stock result remain independent.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from scripts.media_probe_security import consume_provider_configuration
from scripts.phase4b_consumer_chain import run_consumer_chain
from src.media_processing.media_history import atomic_json
from src.media_processing.media_providers import BrowserStockProvider, PexelsProvider, PixabayProvider, StockTerms, WikimediaProvider, now


def stage_evidence(source: Path, destination: Path, *, commons: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("chain.json", "scene_media_manifest.json", "pre_media_script.json", "script.json", "uploader_pure_metadata.json"):
        if (source/name).is_file(): shutil.copyfile(source/name, destination/name)
    if commons and (source/"consumer.mp4").is_file():
        shutil.copyfile(source/"consumer.mp4", destination/"consumer.mp4")
        for path in source.glob("scene_*_inspection.jpg"): shutil.copyfile(path, destination/path.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=Path("output/phase4b_work"))
    ap.add_argument("--evidence", type=Path, default=Path("output/phase4b_evidence"))
    args = ap.parse_args()
    if args.evidence.exists():
        raise SystemExit("Probe evidence path must be fresh.")
    args.evidence.mkdir(parents=True)
    config = consume_provider_configuration()
    evidence = {"version": 1, "phase": "4B", "started_at": now(), "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_sha": os.environ.get("GITHUB_SHA"), "configuration_presence_only": config.presence,
        "live_provider_calls": True, "live_gemini": False, "live_tts": False, "publishing": False,
        "timing_verified": False, "visual_verification": "not_performed", "full_acceptance": False,
        "two_actions_history_proof": "separate_dedicated_workflow_required", "providers": {}}
    try:
        for name in ("pexels", "pixabay", "wikimedia"):
            terms = StockTerms()
            if name == "wikimedia":
                providers = [WikimediaProvider()]
            else:
                # No other provider, child process or process environment gets
                # this key. Cookie transport is separate and domain filtered.
                api = PexelsProvider(config.key_for(name), terms=terms) if name == "pexels" else PixabayProvider(config.key_for(name), terms=terms)
                providers = [api, BrowserStockProvider(name, terms=terms)]
            folder = args.work/name
            chain = run_consumer_chain(folder, providers=providers, provider=name, live_provider_calls=True)
            item = {"status": chain["status"], "selected_scenes": len(chain.get("selected_media", [])),
                    "chain": f"{name}/chain.json", "live_provider_evidence": chain["status"] == "passed"}
            if name != "wikimedia":
                item["configuration_presence_only"] = {**config.presence["providers"][name],
                    "media_cookie_file_present": any(Path(p).is_file() for p in ("cookies.json", "storage_state.json"))}
            if "failure" in chain: item["failure"] = chain["failure"]
            manifest = folder/"scene_media_manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text())
                # Already sanitized in the selector; never serialize raw browser
                # output, response bodies, URLs or exception text here.
                item["provider_diagnostics"] = [issue for scene in data["scenes"] for issue in scene["provider_errors"]]
            evidence["providers"][name] = item
            stage_evidence(folder, args.evidence/name, commons=name == "wikimedia")
            atomic_json(args.evidence/"evidence.json", evidence)
            print(f"PHASE4B_PROVIDER={name} status={chain['status']} scenes={item['selected_scenes']}", flush=True)
        commons = json.loads((args.evidence/"wikimedia/chain.json").read_text())
        evidence["commons_video_cc_by_chain_passed"] = bool(commons["status"] == "passed" and commons.get("real_video_selected") and commons.get("required_cc_by_selected"))
        evidence["all_providers_verified"] = all(v["live_provider_evidence"] for v in evidence["providers"].values())
        evidence["overall"] = "all_media_chains_passed_history_still_separate" if evidence["all_providers_verified"] else "partial_provider_evidence_full_acceptance_failed"
        evidence["acceptance_blockers"] = [name+"_live_access_unverified" for name, item in evidence["providers"].items() if not item["live_provider_evidence"]]
        if not evidence["commons_video_cc_by_chain_passed"]: evidence["acceptance_blockers"].append("commons_video_cc_by_chain_missing")
    except Exception as exc:
        evidence["overall"] = "probe_failed"
        evidence["error_type"] = type(exc).__name__
    evidence["completed_at"] = now()
    atomic_json(args.evidence/"evidence.json", evidence)
    print("PHASE4B_LIVE_RESULT="+evidence["overall"], flush=True)
    return 0 if evidence.get("all_providers_verified") and evidence.get("commons_video_cc_by_chain_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
