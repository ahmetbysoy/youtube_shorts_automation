"""Fail-closed storyboard→media selection. Offline metadata evidence ≠ visual verification.

Phase 5 owns real TTS timestamp alignment. This module only creates provisional
narration-weighted durations, explicit still/contain framing, and an auditable manifest.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
import uuid
from dataclasses import replace
from pathlib import Path

from .media_history import MediaHistory, atomic_json
from .media_io import download_candidate, probe_media
from .media_providers import DOWNLOAD_HOSTS, SOURCE_HOSTS, MediaCandidate, default_providers, now, public_url, valid_url

METHOD = "metadata_lexical_technical_license_v1"
STOP = set("the a an of and or in on at with for from this that is are to bir ve bu su ile icin olan olarak da de daha gibi goruntu goruntusu gosterir gosteriyor gorulur footage video image photo images photos view scene scenic cinematic closeup close up landscape background beautiful generic stock nature space surface planet historical history science city old new photograph file jpg jpeg png webm mp4 shows showing birer uzerinde".split())
# Deliberately small, explicit bilingual vocabulary, not a hidden model or a claim
# that unknown Turkish paraphrases were translated/visually understood.
ALIASES = {
    "ay": "moon", "ayin": "moon", "ayda": "moon", "aydan": "moon", "lunar": "moon",
    "astronauts": "astronaut", "waves": "wave", "trees": "tree", "agaclari": "tree",
    "astronot": "astronaut", "astronotlar": "astronaut", "astronotun": "astronaut",
    "venus": "venus", "venuste": "venus", "venusun": "venus",
    "dunya": "earth", "dunyanin": "earth", "dunyada": "earth",
    "yanardag": "volcano", "yanardagin": "volcano", "volkan": "volcano", "volcanic": "volcano",
    "eyfel": "eiffel", "kulesi": "tower", "kulesinin": "tower", "pariste": "paris",
    "okyanus": "ocean", "okyanusta": "ocean", "balina": "whale", "deniz": "sea",
    "kaplumbaga": "turtle", "krater": "crater", "kraterler": "crater", "craters": "crater",
    "dalga": "wave", "dalgalar": "wave", "dalgalari": "wave", "sahil": "beach", "sahilde": "beach",
    "selale": "waterfall", "selalede": "waterfall", "selalenin": "waterfall", "akan": "flowing", "su": "water", "suyun": "water",
    "apollo": "apollo", "gunes": "sun", "gunesin": "sun", "gezegen": "planet",
    "agac": "tree", "agaclar": "tree", "orman": "forest", "ormanlar": "forest",
    "saturnun": "saturn", "saturn": "saturn", "jupiterin": "jupiter", "marsin": "mars",
    "atmosfer": "atmosphere", "atmosferi": "atmosphere", "bulut": "cloud", "clouds": "cloud",
}
BLOCKED = {"cartoon", "credits", "porn", "autopsy", "surgery", "tumor", "intubation", "compares", "comparison", "slideshow"}


def terms(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", str(text).replace("ı", "i").replace("İ", "i").casefold())
    tokens = re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c)))
    mapped = (ALIASES.get(t, t) for t in tokens if t not in STOP and not t.isdigit())
    return {t for t in mapped if len(t) > 2 and t not in STOP}


def uploader_description_upper_bound(script: dict, description: str) -> int:
    """Conservative UTF-16 budget for the UNCHANGED Studio description builder.

    buildFinalDescription can prepend affiliate/CTA blocks and append hashtags
    before JS .slice(0, 4900). Reserve them even if already present: occasional
    over-rejection is safer than silently cutting a mandatory source credit.
    This is not an upload and must never import/execute the uploader entrypoint.
    """
    field = lambda key: str(script.get(key) or "").strip()
    affiliate = field("affiliate_hook") or field("affiliate_cta")
    if not affiliate and field("affiliate_link"):
        affiliate = "İncele: "+field("affiliate_link")
    top = "\n\n".join(v for v in (affiliate, field("cta_line")) if v)
    hashtags = " ".join(str(h).strip() for h in script.get("viral_hashtags", []) if str(h).strip())
    # Count all hashtags (not just the builder's first three) conservatively.
    upper = "\n\n".join(v for v in (top, description, hashtags) if v)
    return len(upper.encode("utf-16-le", errors="surrogatepass"))//2


class SceneMediaError(RuntimeError):
    def __init__(self, reason: str, report: dict):
        super().__init__(reason)
        self.report = report


def scene_plan(script: dict) -> list[dict]:
    board = script.get("storyboard")
    if not isinstance(board, list) or not 1 <= len(board) <= 12:
        raise ValueError("invalid_storyboard_fail_closed")
    total = float(script.get("audio_duration_sec", 0))
    if not math.isfinite(total) or not 0 < total <= 180:
        raise ValueError("invalid_audio_duration")
    seen = set(); plan = []
    weights = []
    for scene in board:
        if not isinstance(scene, dict) or type(scene.get("scene_id")) is not int or scene["scene_id"] in seen or scene["scene_id"] <= 0:
            raise ValueError("invalid_or_duplicate_scene_id")
        seen.add(scene["scene_id"])
        if not all(isinstance(scene.get(k), str) and scene[k].strip() for k in ["visual_query", "narration"]):
            raise ValueError("missing_scene_query_or_narration")
        alternatives = scene.get("alternative_queries", [])
        if not isinstance(alternatives, list) or len(alternatives) > 3 or not all(isinstance(q, str) and q.strip() for q in alternatives):
            raise ValueError("invalid_alternative_queries")
        queries = list(dict.fromkeys(q.strip() for q in [scene["visual_query"], *alternatives]))
        if any(len(q) > 180 for q in queries):
            raise ValueError("query_length_limit")
        if not terms(scene["visual_query"]) & terms(scene["narration"]):
            raise ValueError("query_narration_alignment_unknown")
        weights.append(max(1, len(scene["narration"].split())))
        plan.append({"scene_id": scene["scene_id"], "narration": scene["narration"], "queries": queries,
                     "primary_query": queries[0], "media_type": scene.get("media_type")})
    for scene, weight in zip(plan, weights):
        scene["duration"] = round(total*weight/sum(weights), 3)
        if scene["duration"] < 0.5:
            raise ValueError("scene_duration_too_short")
    plan[-1]["duration"] = round(total-sum(s["duration"] for s in plan[:-1]), 3)
    return plan


def evaluate(candidate: MediaCandidate, scene: dict, query: str, *, used: set[str], recent: list[dict], measured: bool = False) -> dict:
    reasons = []
    lic = candidate.license
    if candidate.provider not in SOURCE_HOSTS or not candidate.media_id or not valid_url(candidate.source_url, SOURCE_HOSTS.get(candidate.provider, set())):
        reasons.append("untrusted_or_missing_source_identity")
    if not valid_url(candidate.download_url, DOWNLOAD_HOSTS.get(candidate.provider, set())):
        reasons.append("untrusted_download_url")
    if not lic.verified or not lic.name or not lic.evidence_url or lic.attribution_required is None:
        reasons.append(lic.rejection_reason or "missing_license_evidence")
    if lic.attribution_required and not lic.attribution:
        reasons.append("missing_required_attribution")
    if candidate.key in used or public_url(candidate.source_url) in used or public_url(candidate.download_url) in used:
        reasons.append("duplicate_in_video")
    if candidate.media_type not in {"image", "video"}:
        reasons.append("unsupported_media_type")
    if scene.get("media_type") in {"animation", "generated"}:
        reasons.append("requested_generation_not_supported")
    elif scene.get("media_type") in {"image", "video"} and candidate.media_type != scene["media_type"]:
        reasons.append("media_type_mismatch")
    # Only provider/source metadata is evidence. NEVER concatenate the search
    # query into candidate metadata: that would make every search result pass.
    evidence = terms(" ".join((candidate.title, candidate.description, *candidate.tags)))
    qterms, nterms, primary = terms(query), terms(scene["narration"]), terms(scene["primary_query"])
    query_coverage = len(evidence & qterms)/max(1, len(qterms))
    narration_overlap = sorted(evidence & nterms)
    primary_overlap = sorted(evidence & primary & nterms)
    minimum_anchors = min(2, len(primary & nterms))
    if query_coverage < 0.5 or not minimum_anchors or len(primary_overlap) < minimum_anchors or not narration_overlap:
        reasons.append("relevance_unproven_or_unrelated")
    if evidence & BLOCKED:
        reasons.append("blocked_or_sensitive_metadata")
    # Unknown dimensions/duration may proceed ONLY to download+probe, never to
    # the final accepted scene. Advertised values are rechecked against the file.
    w, h = candidate.width, candidate.height
    ratio = w/h if w and h else None
    if w is not None and h is not None:
        if min(w, h) < 720 or max(w, h) < 1080:
            reasons.append("insufficient_resolution")
        if ratio is None or not 0.4 <= ratio <= 2.2:
            reasons.append("unsupported_aspect_ratio")
    elif measured:
        reasons.append("missing_measured_resolution")
    if candidate.media_type == "video":
        if candidate.duration is not None:
            if not math.isfinite(candidate.duration) or candidate.duration+0.05 < scene["duration"]:
                reasons.append("insufficient_duration")
        elif measured:
            reasons.append("missing_measured_duration")
    recent_hit = any(r.get("key") == candidate.key or r.get("source_url") == public_url(candidate.source_url) for r in recent)
    components = {
        "query_metadata": round(30*query_coverage, 2),
        "narration_metadata": 20 if primary_overlap else 0,
        "resolution": min(15, round(min(w or 0, h or 0)/1080*15, 2)),
        "aspect_ratio": 10 if ratio and 0.45 <= ratio <= 0.8 else 6 if ratio and 0.4 <= ratio <= 2.2 else 0,
        "duration": 10 if candidate.media_type == "image" or candidate.duration is not None and candidate.duration >= scene["duration"] else 0,
        "provider_provenance": 5 if candidate.provider in SOURCE_HOSTS else 0,
        "license_evidence": 10 if lic.verified else 0,
        "recent_use_penalty": -25 if recent_hit else 0,
    }
    return {"eligible": not reasons, "score": round(max(0, sum(components.values())), 2), "components": components,
            "rejection_reasons": reasons, "relevance_status": "metadata_supported" if not ("relevance_unproven_or_unrelated" in reasons) else "unproven",
            "visual_verification": "not_performed", "query_coverage": round(query_coverage, 3), "primary_narration_overlap": primary_overlap,
            "quality_basis": "measured_dimensions_duration_and_full_decode" if measured else "provider_advertised_metadata_only",
            "framing": "contain_letterbox"}


def provider_issue(provider, query: str, exc: Exception | None = None) -> dict:
    """Never serialize arbitrary diagnostics/exception text from a transport.

    A browser 403 is restricted to provider, status, query ID and a safe class.
    The raw (non-secret) fixture queries remain separately in queries_tried.
    """
    diagnostics = getattr(provider, "last_diagnostics", {})
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    status = diagnostics.get("search_http_status")
    status = status if type(status) is int and 100 <= status <= 599 else None
    error = "NoCatalogCandidates"
    if status and status != 200:
        error = "BrowserHTTPBlocked" if status == 403 else "BrowserHTTPError"
    elif diagnostics.get("status") in {"api_key_not_configured_or_placeholder", "media_cookie_configuration_absent"}:
        error = diagnostics["status"]
    if exc is not None:
        message = str(exc)
        match = re.fullmatch(r"(pexels|pixabay|commons)_catalog_http_([0-9]{3})", message)
        if match:
            status, error = int(match[2]), message
        else:
            error = "browser_catalog_failed" if message == "browser_catalog_failed" else type(exc).__name__
    return {"provider": provider.name, "http_status": status,
            "query_id": "q-"+hashlib.sha256(query.encode()).hexdigest()[:12], "error_type": error}


def select_storyboard_media(script: dict, work_dir: Path, *, providers=None, history: MediaHistory | None = None,
                            downloader=None, prober=None, report_path: Path | None = None) -> tuple[list[dict], dict]:
    downloader = download_candidate if downloader is None else downloader
    prober = probe_media if prober is None else prober
    providers = default_providers() if providers is None else providers
    history = history if history is not None else MediaHistory.from_environment()
    report = {"version": 1, "status": "blocked", "method": METHOD, "created_at": now(),
              "visual_verification": "not_performed", "timing_basis": "narration_word_weighted_provisional_not_tts_aligned",
              "history_scope": "github_contents_cas" if history.url else "local_atomic_file",
              "scenes": [], "failure": None}
    work_dir.mkdir(parents=True, exist_ok=True)
    runtime = []; used: set[str] = set(); history_entries = []
    generation = str(script.get("generation_id") or uuid.uuid4())
    try:
        plan = scene_plan(script)
        recent = history.recent()
        for scene in plan:
            record = {"scene_id": scene["scene_id"], "narration": scene["narration"], "planned_duration": scene["duration"],
                      "timing_basis": report["timing_basis"], "queries_tried": [], "provider_errors": [], "rejections": [],
                      "measured_candidates": [], "ranking_scope": "at_most_four_downloads_per_scene_measured_rerank",
                      "selected_provider": None, "selected_media_id": None, "source_url": None, "license": None,
                      "attribution": None, "duration": None, "resolution": None, "aspect_ratio": None,
                      "selection_score": None, "rejection_reason": "not_selected", "fallback_used": False}
            report["scenes"].append(record)
            selected = None; downloads = 0
            for qi, query in enumerate(scene["queries"]):
                record["queries_tried"].append(query)
                ranked = []
                for pi, provider in enumerate(providers):
                    try:
                        candidates = provider.search(query)[:8]
                        if not candidates:
                            record["provider_errors"].append(provider_issue(provider, query))
                        for candidate in candidates:
                            verdict = evaluate(candidate, scene, query, used=used, recent=recent)
                            if verdict["eligible"]:
                                ranked.append((candidate, verdict, pi))
                            else:
                                record["rejections"].append({"key": candidate.key, "query": query, "source_url": public_url(candidate.source_url), "reasons": verdict["rejection_reasons"]})
                    except Exception as exc:
                        record["provider_errors"].append(provider_issue(provider, query, exc))
                ranked.sort(key=lambda x: (-x[1]["score"], x[2], x[0].key))
                measured_pool = []
                catalog_seen = set()
                for candidate, _pre, pi in ranked:
                    identities = {candidate.key, public_url(candidate.source_url), public_url(candidate.download_url)}
                    if identities & catalog_seen:
                        continue
                    catalog_seen.update(identities)
                    if downloads >= 4:
                        break
                    downloads += 1
                    path = work_dir/f"scene_{scene['scene_id']}_{downloads}.{'jpg' if candidate.media_type == 'image' else 'mp4'}"
                    try:
                        downloader(candidate, path)
                        probe = prober(path, candidate.media_type)
                        measured = replace(candidate, width=probe["width"], height=probe["height"], duration=probe["duration"], download_status="downloaded_and_decoded")
                        verdict = evaluate(measured, scene, query, used=used, recent=recent, measured=True)
                        if probe.get("decode_status") != "passed":
                            verdict["rejection_reasons"].append("decode_not_confirmed")
                        if probe["sha256"] in used:
                            verdict["rejection_reasons"].append("duplicate_content_in_video")
                        if verdict["rejection_reasons"]:
                            record["rejections"].append({"key": candidate.key, "query": query, "reasons": verdict["rejection_reasons"]})
                            path.unlink(missing_ok=True); continue
                        hash_hit = any(x.get("sha256") == probe["sha256"] for x in recent)
                        if hash_hit and not verdict["components"]["recent_use_penalty"]:
                            verdict["components"]["recent_use_penalty"] = -25
                            verdict["score"] = max(0, verdict["score"]-25)
                        evidence = {"media": measured.record(), "file_probe": probe, "assessment": verdict,
                                    "recent_hash_match": hash_hit, "decision": "not_selected_lower_measured_rank"}
                        record["measured_candidates"].append(evidence)
                        measured_pool.append((measured, verdict, pi, path, probe, evidence))
                    except Exception as exc:
                        path.unlink(missing_ok=True)
                        record["rejections"].append({"key": candidate.key, "query": query, "reasons": ["download_or_decode_failed"], "error_type": type(exc).__name__})
                # Measure a bounded pool, THEN choose. A new URL/ID may hide a
                # recent byte hash, and advertised dimensions may be wrong. A
                # post-download penalty without reranking does not avoid reuse.
                measured_pool.sort(key=lambda x: (-x[1]["score"], x[2], x[0].key))
                if measured_pool:
                    measured, verdict, pi, path, probe, evidence = measured_pool[0]
                    evidence["decision"] = "selected_highest_measured_rank"
                    for losing in measured_pool[1:]:
                        losing[3].unlink(missing_ok=True)
                    record.update({"selected_provider": measured.provider, "selected_media_id": measured.media_id,
                                   "source_url": public_url(measured.source_url), "license": measured.record()["license"], "attribution": measured.license.attribution,
                                   "duration": measured.duration, "resolution": {"width": measured.width, "height": measured.height},
                                   "aspect_ratio": round(measured.width/measured.height, 6), "selection_score": verdict["score"],
                                   "rejection_reason": None, "fallback_used": qi > 0 or pi > 0,
                                   "selected_query": query, "assessment": verdict, "media": measured.record(), "file_probe": probe,
                                   "media_type": measured.media_type, "fit_mode": "contain", "download_status": "downloaded_and_decoded"})
                    selected = {"path": path, "duration": scene["duration"], "media_kind": measured.media_type,
                                "provider": measured.provider, "credit": measured.license.attribution, "scene_id": scene["scene_id"],
                                "fit_mode": "contain", "loop_allowed": False}
                    used.update({measured.key, public_url(measured.source_url), public_url(measured.download_url), probe["sha256"]})
                    history_entries.append({"key": measured.key, "source_url": public_url(measured.source_url), "sha256": probe["sha256"], "selected_at": now(), "generation_id": generation})
                    break
            if selected is None:
                record["rejection_reason"] = "no_acceptable_media_after_bounded_queries"
                raise ValueError(f"scene_{scene['scene_id']}_has_no_acceptable_media")
            runtime.append(selected)
        # Preserve attribution IN FULL. Never slice away mandatory credits.
        credits = list(dict.fromkeys(r["attribution"] for r in report["scenes"] if r["attribution"]))
        description = str(script.get("description") or "").strip()
        missing = [credit for credit in credits if credit not in description]
        merged = (description+"\n\n"+"\n".join(missing)).strip()
        if len(merged.encode("utf-16-le", errors="surrogatepass"))//2 > 4900:
            raise ValueError("description_cannot_preserve_required_attribution")
        if any(r["license"]["attribution_required"] for r in report["scenes"]) and uploader_description_upper_bound(script, merged) > 4900:
            raise ValueError("uploader_description_budget_cannot_preserve_required_attribution")
        history.remember(history_entries)
        script["description"] = merged
        script["media_credits"] = list(dict.fromkeys([*script.get("media_credits", []), *credits]))
        script["scene_media"] = report["scenes"]
        report["status"] = "selected_metadata_and_technical_checks_passed"
        script["media_selection"] = {key: value for key, value in report.items() if key != "scenes"}
        if report_path: atomic_json(report_path, report)
        return runtime, report
    except Exception as exc:
        report["failure"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        if report_path: atomic_json(report_path, report)
        raise SceneMediaError("storyboard_media_selection_blocked", report) from None
