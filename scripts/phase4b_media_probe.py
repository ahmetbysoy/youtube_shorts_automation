"""Publication-free live probe. Cookie-only means NO API key/ENV_FILE usage.

Every provider and access method has its own verdict. Green CI/local artifacts
never turn blocked live coverage into acceptance. No uploader entrypoint.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from scripts.media_probe_security import consume_provider_configuration
from scripts.phase4b_consumer_chain import run_consumer_chain
from scripts.phase4c_commons_diagnostics import diagnose_commons, link_actual_consumer
from src.media_processing.media_history import atomic_json
from src.media_processing.media_providers import BrowserStockProvider, PexelsProvider, PixabayProvider, StockTerms, WikimediaProvider, now


def stage_evidence(source: Path, destination: Path, *, commons: bool) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("chain.json", "scene_media_manifest.json", "pre_media_script.json", "script.json", "uploader_pure_metadata.json"):
        if (source/name).is_file(): shutil.copyfile(source/name, destination/name)
    chain = json.loads((source/"chain.json").read_text()) if (source/"chain.json").is_file() else {}
    if commons and chain.get("status") == "passed" and (source/"consumer.mp4").is_file():
        shutil.copyfile(source/"consumer.mp4", destination/"consumer.mp4")
        for path in source.glob("scene_*_inspection.jpg"): shutil.copyfile(path, destination/path.name)


def stock_providers(name: str, mode: str, config=None) -> list:
    terms = StockTerms()
    if mode == "cookie_only":
        return [BrowserStockProvider(name, terms=terms)]
    # Historical CLI route retained, but no separate-method success is inferred.
    api = PexelsProvider(config.key_for(name), terms=terms) if name == "pexels" else PixabayProvider(config.key_for(name), terms=terms)
    return [api, BrowserStockProvider(name, terms=terms)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, default=Path("output/phase4b_work"))
    ap.add_argument("--evidence", type=Path, default=Path("output/phase4b_evidence"))
    ap.add_argument("--stock-access-mode", choices=["cookie_only", "auto"], default="auto")
    args = ap.parse_args(); cookie_only = args.stock_access_mode == "cookie_only"
    if args.evidence.exists() and {p.name for p in args.evidence.iterdir()} != {"preflight.json"}:
        raise SystemExit("Probe evidence path must be fresh apart from safe preflight.")
    if cookie_only:
        pre = args.evidence/"preflight.json"
        if not pre.is_file(): raise SystemExit("Cookie-only preflight required.")
        gate = json.loads(pre.read_text())
        if gate.get("status") != "passed" or gate.get("access_mode") != "cookie_only" or not Path("cookies.json").is_file():
            raise SystemExit("Cookie-only preflight did not pass.")
        # Do not even parse API credentials/ENV_FILE in the user-approved mode.
        for name in ("PHASE4_PROVIDER_ENV", "PEXELS_API_KEY", "PIXABAY_API_KEY"):
            os.environ.pop(name, None)
        config = None
        presence = {"api_credentials_evaluated": False, "api_credentials_loaded": False, "env_file_read": False,
            "providers": {p: {"api_key_present": False, "presence_scope": "not_supplied_to_cookie_only_probe"} for p in ("pexels", "pixabay")}}
    else:
        config = consume_provider_configuration(); presence = config.presence
    args.evidence.mkdir(parents=True, exist_ok=True)
    evidence = {"version": 2, "phase": "4C" if cookie_only else "4B", "started_at": now(), "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_sha": os.environ.get("GITHUB_SHA"), "stock_access_mode": args.stock_access_mode, "configuration_presence_only": presence,
        "live_provider_calls": True, "live_gemini": False, "live_tts": False, "publishing": False,
        "timing_verified": False, "visual_verification": "not_performed", "full_acceptance": False,
        "two_actions_history_proof": "historical_separate_proof_must_be_revalidated_by_blob_identity", "providers": {}}
    try:
        for name in ("pexels", "pixabay", "wikimedia"):
            providers = [WikimediaProvider()] if name == "wikimedia" else stock_providers(name, args.stock_access_mode, config)
            diagnostics = diagnose_commons(args.work/"commons_diagnostic_temporary") if name == "wikimedia" else None
            folder = args.work/name
            chain = run_consumer_chain(folder, providers=providers, provider=name, live_provider_calls=True)
            item = {"status": chain["status"], "selected_scenes": len(chain.get("selected_media", [])),
                "chain": f"{name}/chain.json", "live_provider_evidence": chain["status"] == "passed"}
            if name != "wikimedia":
                item["configuration_presence_only"] = {**presence["providers"][name], "media_cookie_file_present": Path("cookies.json").is_file()}
                item["api_access"] = {"status": "not_requested_cookie_only" if cookie_only else "not_independently_measured_legacy_auto", "key_used": False if cookie_only else "not_inferred"}
                browser = next(p for p in providers if isinstance(p, BrowserStockProvider))
                observed = getattr(browser, "last_diagnostics", {})
                item["cookie_access"] = {"method": "provider_filtered_cookie_browser", "status": chain["status"] if cookie_only else "not_independently_measured_legacy_auto",
                    "http_status": observed.get("search_http_status"), "source_http_statuses": observed.get("source_http_statuses", []),
                    "license_http_status": observed.get("license_http_status"), "session_validity_inferred_from_cookie_file": False}
            else:
                item["api_access"] = {"status": "public_commons_api_no_key"}
                item["cookie_access"] = {"status": "not_applicable"}
            if "failure" in chain: item["failure"] = chain["failure"]
            manifest = folder/"scene_media_manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text())
                item["provider_diagnostics"] = [issue for scene in data["scenes"] for issue in scene["provider_errors"]]
            evidence["providers"][name] = item
            stage_evidence(folder, args.evidence/name, commons=name == "wikimedia")
            if diagnostics is not None:
                link_actual_consumer(diagnostics, chain)
                atomic_json(args.evidence/name/"io_diagnostics.json", diagnostics)
                item["io_diagnostics"] = name+"/io_diagnostics.json"
            atomic_json(args.evidence/"evidence.json", evidence)
            print(f"PHASE4B_PROVIDER={name} status={chain['status']} scenes={item['selected_scenes']}", flush=True)
        commons = json.loads((args.evidence/"wikimedia/chain.json").read_text())
        evidence["commons_video_cc_by_chain_passed"] = bool(commons["status"] == "passed" and commons.get("real_video_selected") and commons.get("required_cc_by_selected"))
        evidence["all_providers_verified"] = all(v["live_provider_evidence"] for v in evidence["providers"].values())
        evidence["overall"] = "all_media_chains_passed_history_ci_still_separate" if evidence["all_providers_verified"] else "partial_provider_evidence_full_acceptance_failed"
        evidence["acceptance_blockers"] = [name+"_live_access_unverified" for name, item in evidence["providers"].items() if not item["live_provider_evidence"]]
        if not evidence["commons_video_cc_by_chain_passed"]: evidence["acceptance_blockers"].append("commons_video_cc_by_chain_missing")
    except Exception as exc:
        evidence["overall"] = "probe_failed"; evidence["error_type"] = type(exc).__name__
    evidence["completed_at"] = now(); atomic_json(args.evidence/"evidence.json", evidence)
    print("PHASE4B_LIVE_RESULT="+evidence["overall"], flush=True)
    return 0 if evidence.get("all_providers_verified") and evidence.get("commons_video_cc_by_chain_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
