"""Additional acceptance evidence; not production visual/factual approval."""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image

from src.media_processing.media_providers import get_public, public_url


def _same_file_url(left: str, right: str) -> bool:
    a, b = urlsplit(left), urlsplit(right)
    return a.hostname == b.hostname == "commons.wikimedia.org" and unquote(a.path).replace("_", " ") == unquote(b.path).replace("_", " ")


def verify_commons_file_pages(scene: dict, *, evidence: dict | None = None) -> dict:
    """API declaration + canonical File page + official deed; safe HTTP stages."""
    evidence = {} if evidence is None else evidence
    evidence.update(source_page_http={"status": "not_reached"}, license_deed_http={"status": "not_reached"})
    def fetch_text(url, hosts, key):
        trace = {}; evidence[key] = trace
        try:
            with get_public(requests, url, hosts, trace=trace) as r:
                text, status = r.text, r.status_code
            trace.update(status="passed", http_status=status)
            return text, status
        except Exception:
            trace.update(status="failed", error_class=trace.get("error_class", "license_evidence_failed"))
            raise
    source, license_url = scene["source_url"], scene["license"]["url"]
    license_path = urlsplit(license_url).path.rstrip("/")
    if not re.fullmatch(r"/licenses/by/(2\.0|2\.5|3\.0|4\.0)(?:/[a-z-]+)?", license_path):
        raise ValueError("live_cc_by_deed_declaration_not_supported")
    fetched = {}; http_failed = False
    for key, url, hosts in (("source_page_http", source, {"commons.wikimedia.org"}),
                            ("license_deed_http", license_url, {"creativecommons.org", "www.creativecommons.org"})):
        try:
            fetched[key] = fetch_text(url, hosts, key)
        except Exception:
            http_failed = True
    if http_failed:
        raise ValueError("live_source_or_license_http_failed") from None
    html, source_status = fetched["source_page_http"]
    deed_html, deed_status = fetched["license_deed_http"]
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"]')
    if not canonical or not _same_file_url(source, canonical.get("href", "")):
        raise ValueError("live_file_page_canonical_identity_unproven")
    def matching_deed(url):
        p = urlsplit(urljoin(source, url))
        return p.hostname in {"creativecommons.org", "www.creativecommons.org"} and not p.query and not p.fragment and (
            p.path.rstrip("/") == license_path or p.path.startswith(license_path+"/deed.") or p.path.startswith(license_path+"/legalcode"))
    observed = any(matching_deed(a.get("href", "")) for a in soup.select("a[href]"))
    text = " ".join((soup.select_one("#mw-content-text") or soup).get_text(" ").split())
    creator_observed = bool(scene["license"]["creator"] and scene["license"]["creator"].casefold() in text.casefold())
    if not observed or not creator_observed:
        raise ValueError("live_file_page_license_or_creator_not_observed")
    deed = BeautifulSoup(deed_html, "html.parser")
    deed_text = " ".join(deed.get_text(" ").lower().split())
    if not all(word in deed_text for word in ("share", "adapt", "attribution")):
        raise ValueError("official_cc_by_deed_permissions_unrecognized")
    return {"status": "passed", "source_page_http_status": source_status, "license_deed_http_status": deed_status,
            "source_page_url": public_url(source), "license_deed_url": public_url(license_url),
            "canonical_file_identity_matched": True, "declared_license_link_observed_on_file_page": True,
            "declared_creator_text_observed_on_file_page": True,
            "source_page_sha256": hashlib.sha256(html.encode()).hexdigest(),
            "license_deed_sha256": hashlib.sha256(deed_html.encode()).hexdigest(),
            "method": "actual_commons_api_plus_canonical_file_html_plus_official_cc_deed_http",
            "third_party_rights_verified": False}


def observe_rendered_motion(video: Path, scene: dict, elapsed: float, folder: Path, *, cover_seconds: float = 0.0) -> dict:
    """Two decoded samples in the visible content area, after the cover.

    Pixel change is evidence of temporal variation, NOT recognition of an action,
    subject, era, author, or source truth. Constant-frame videos fail this probe.
    """
    visible = scene["planned_duration"]-cover_seconds
    if visible < 0.15: raise ValueError("insufficient_visible_video_for_motion_probe")
    times = [elapsed+cover_seconds+visible*fraction for fraction in (0.2, 0.8)]
    w, h = scene["resolution"]["width"], scene["resolution"]["height"]
    scale = min(1080/w, 1920/h)
    # Sample the central 80% of the contained source, not black letterboxing or
    # the bottom subtitle area of this landscape proof clip.
    cw, ch = max(2, int(w*scale*0.8)//2*2), max(2, int(h*scale*0.8)//2*2)
    x, y = (1080-cw)//2, (1920-ch)//2
    raw_samples, files = [], []
    for label, at in zip(("a", "b"), times):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.6f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"crop={cw}:{ch}:{x}:{y},scale=160:90", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"],
                           capture_output=True, check=True, timeout=30)
        if len(r.stdout) != 160*90*3: raise ValueError("motion_probe_frame_missing")
        raw_samples.append(r.stdout)
        name = f"scene_{scene['scene_id']}_motion_{label}_inspection.jpg"
        Image.frombytes("RGB", (160, 90), r.stdout).save(folder/name, quality=92)
        files.append(name)
    mean_difference = sum(abs(a-b) for a, b in zip(*raw_samples))/len(raw_samples[0])
    changed = mean_difference > 0.1
    return {"status": "temporal_pixel_change_observed" if changed else "no_temporal_change_observed",
            "sample_times_seconds": times, "mean_absolute_rgb_difference_0_to_255": round(mean_difference, 6),
            "decoded_sample_sha256": [hashlib.sha256(raw).hexdigest() for raw in raw_samples], "inspection_files": files,
            "sampled_contained_content_rectangle": {"x": x, "y": y, "width": cw, "height": ch},
            "cover_excluded": True, "semantic_visual_verification": "not_performed"}
