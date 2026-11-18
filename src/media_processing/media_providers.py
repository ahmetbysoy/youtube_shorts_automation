"""Phase 4 provider catalog. No selection by search rank, random choice, or CDN URL alone.

All network failures are reduced to safe status/type codes; API keys, cookies and
query-bearing request/exception objects must never be logged or serialized.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

USER_AGENT = "YouTubeShortsAutomation/Phase4 (https://github.com/ahmetbysoy/youtube_shorts_automation)"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_HOSTS = {
    "pexels": {"www.pexels.com", "pexels.com"},
    "pixabay": {"pixabay.com", "www.pixabay.com"},
    "wikimedia": {"commons.wikimedia.org"},
}
DOWNLOAD_HOSTS = {
    "pexels": {"videos.pexels.com", "player.vimeo.com", "images.pexels.com"},
    "pixabay": {"cdn.pixabay.com", "videos.pexels.com"},
    "wikimedia": {"upload.wikimedia.org", "thumb.wikimedia.org"},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def plain(value: object, limit: int = 6000) -> str:
    text = str(value or "")[:50000]
    if "<" in text:
        text = BeautifulSoup(text, "html.parser").get_text(" ")
    return " ".join(html.unescape(text).split())[:limit]


def valid_url(url: str, hosts: set[str]) -> bool:
    try:
        p = urlsplit(str(url))
        return p.scheme == "https" and p.hostname in hosts and not p.username and not p.password and p.port in (None, 443)
    except ValueError:
        return False


def public_url(url: str) -> str:
    """For reports/history only; strip signed query strings and all fragments."""
    try:
        p = urlsplit(url)
        return urlunsplit((p.scheme, p.netloc, p.path, "", "")) if not p.username and not p.password else ""
    except ValueError:
        return ""


def get_public(session, url: str, hosts: set[str], **kwargs):
    """Allowlisted HTTPS, bounded redirects; never forwards credentials/cookies."""
    for _ in range(4):
        if not valid_url(url, hosts):
            raise ValueError("untrusted_media_host")
        r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=(5, 25), allow_redirects=False, **kwargs)
        if r.status_code in (301, 302, 303, 307, 308):
            nxt = urljoin(url, r.headers.get("Location", ""))
            r.close()
            url = nxt
            continue
        if r.status_code != 200:
            status = r.status_code
            r.close()
            raise RuntimeError(f"media_http_{status}")
        return r
    raise RuntimeError("media_redirect_limit")


@dataclass(frozen=True)
class MediaLicense:
    name: str = ""
    url: str = ""
    verified: bool = False
    evidence_url: str = ""
    evidence_method: str = "unavailable"
    checked_at: str = ""
    attribution_required: bool | None = None
    attribution: str = ""
    creator: str = ""
    evidence_sha256: str = ""
    restrictions: tuple[str, ...] = ()
    rejection_reason: str | None = None


@dataclass(frozen=True)
class MediaCandidate:
    provider: str
    media_id: str
    source_url: str
    download_url: str
    media_type: str
    width: int | None
    height: int | None
    duration: float | None
    title: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    license: MediaLicense = field(default_factory=MediaLicense)
    download_status: str = "not_downloaded"
    catalog_transport: str = "api"

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.media_id}"

    def record(self) -> dict:
        d = asdict(self)
        d["download_url"] = public_url(self.download_url)
        d["media_url"] = d["download_url"]
        d["source_url"] = public_url(self.source_url)
        d["aspect_ratio"] = round(self.width / self.height, 6) if self.width and self.height else None
        return d


class MediaProvider(Protocol):
    name: str

    def search(self, query: str) -> list[MediaCandidate]: ...


class StockTerms:
    """Observed provider-wide permission + restrictive terms, NOT a rights release.

    Fail closed if the official page cannot be fetched or expected clauses change.
    No claim that metadata proves model/property/privacy/brand clearances.
    """
    URLS = {"pexels": "https://www.pexels.com/license/", "pixabay": "https://pixabay.com/service/terms/"}

    def __init__(self, session=requests):
        self.session = session
        self.cache: dict[str, MediaLicense] = {}

    def check(self, provider: str) -> MediaLicense:
        if provider in self.cache:
            return self.cache[provider]
        url = self.URLS[provider]
        try:
            with get_public(self.session, url, SOURCE_HOSTS[provider]) as r:
                text = plain(r.text, 100000).lower()
            # Check permission and restriction clauses together, not a title alone.
            markers = (
                ("free to use", "attribution is not required", "modify", "don't sell unaltered", "don't imply endorsement")
                if provider == "pexels" else
                ("content license", "royalty-free", "commercial or non-commercial", "standalone", "prohibited uses")
            )
            if not all(marker in text for marker in markers):
                raise ValueError("terms_not_recognized")
            lic = MediaLicense(
                name="Pexels License" if provider == "pexels" else "Pixabay Content License",
                url=url, verified=True, evidence_url=url, evidence_method="official_provider_terms_http",
                checked_at=now(), attribution_required=False,
                evidence_sha256=hashlib.sha256(text.encode()).hexdigest(),
                restrictions=("no_standalone_redistribution", "no_implied_endorsement", "third_party_rights_not_verified", "no_sensitive_use_of_identifiable_people"),
            )
        except Exception:
            lic = MediaLicense(url=url, evidence_url=url, checked_at=now(), rejection_reason="provider_terms_unavailable_or_changed")
        self.cache[provider] = lic
        return lic


def commons_license(page: dict, info: dict) -> MediaLicense:
    ext = info.get("extmetadata") or {}
    val = lambda key: plain((ext.get(key) or {}).get("value", ""))
    name, lic_url = val("LicenseShortName"), val("LicenseUrl")
    source = info.get("descriptionurl") or ""
    creator = val("Artist") or val("Credit")
    reason = None
    attr_raw = val("AttributionRequired").lower()
    attr = True if attr_raw in {"true", "1", "yes"} else False if attr_raw in {"false", "0", "no"} else None
    p = urlsplit(lic_url if lic_url.startswith("http") else "https:"+lic_url) if lic_url else None
    path = p.path.rstrip("/") if p else ""
    cc_host = p and p.hostname in {"creativecommons.org", "www.creativecommons.org"}
    if "by-sa" in name.lower() or "by-sa" in path:
        reason = "share_alike_downstream_policy_not_implemented"
    elif "cc by" in name.lower() and re.fullmatch(r"/licenses/by/(?:2\.0|2\.5|3\.0|4\.0)(?:/[a-z-]+)?", path) and cc_host:
        attr = True
    elif name.lower() in {"cc0", "cc0 1.0", "cc0 1.0 universal"} and cc_host and path == "/publicdomain/zero/1.0":
        attr = False
    elif name.lower() == "public domain" and val("License").lower().startswith("pd") and attr is False:
        # Commons sometimes omits LicenseUrl for PD. Preserve that absence;
        # the per-file declaration is the evidence, not an invented CC0 URL.
        pass
    else:
        reason = "missing_or_unsupported_file_license"
    if not valid_url(source, SOURCE_HOSTS["wikimedia"]):
        reason = "missing_license_source_page"
    if attr and not creator:
        reason = "missing_required_creator"
    if attr is None:
        reason = "attribution_requirement_unknown"
    title = plain(page.get("title", "")).removeprefix("File:")
    attribution = ""
    if attr:
        attribution = f"{title} — {creator} — {name} ({lic_url}); {source}; değişiklikler: ölçekleme/kadraj, süre ve altyazı montajı."
    return MediaLicense(name=name, url=lic_url, verified=reason is None,
                        evidence_url=source, evidence_method="commons_per_file_extmetadata",
                        checked_at=now(), attribution_required=attr, attribution=attribution, creator=creator,
                        evidence_sha256=hashlib.sha256(json.dumps(ext, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                        restrictions=("third_party_rights_not_verified",), rejection_reason=reason)


class PexelsProvider:
    name = "pexels"

    def __init__(self, api_key: str | None = None, *, session=requests, terms: StockTerms | None = None):
        self._key = api_key if api_key is not None else os.environ.get("PEXELS_API_KEY", "")
        self.session, self.terms = session, terms or StockTerms(session)

    def search(self, query: str) -> list[MediaCandidate]:
        if not self._key or "your_" in self._key.lower():
            return []
        # No redirects for authenticated requests. Never raise/print response URLs.
        r = self.session.get("https://api.pexels.com/videos/search", params={"query": query, "per_page": 8},
                             headers={"Authorization": self._key, "User-Agent": USER_AGENT}, timeout=(5, 20), allow_redirects=False)
        if r.status_code != 200:
            raise RuntimeError(f"pexels_catalog_http_{r.status_code}")
        rows = r.json().get("videos") or []
        lic = self.terms.check(self.name)
        results = []
        for row in rows:
            files = sorted((f for f in row.get("video_files", []) if f.get("link") and f.get("width") and f.get("height")),
                           key=lambda f: (int(f["height"]) >= 1080, int(f["width"])*int(f["height"])), reverse=True)
            if not files or not row.get("id") or not valid_url(row.get("url", ""), SOURCE_HOSTS[self.name]):
                continue
            f = files[0]
            slug = unquote(urlsplit(row["url"]).path).strip("/").replace("/", " ").replace("-", " ")
            results.append(MediaCandidate(self.name, str(row["id"]), row["url"], f["link"], "video", int(f["width"]), int(f["height"]),
                                          float(row["duration"]) if row.get("duration") else None, title=plain(row.get("title") or slug),
                                          description=plain(row.get("description")), license=lic))
        return results


class PixabayProvider:
    name = "pixabay"

    def __init__(self, api_key: str | None = None, *, session=requests, terms: StockTerms | None = None):
        self._key = api_key if api_key is not None else os.environ.get("PIXABAY_API_KEY", "")
        self.session, self.terms = session, terms or StockTerms(session)

    def search(self, query: str) -> list[MediaCandidate]:
        if not self._key or "your_" in self._key.lower():
            return []
        r = self.session.get("https://pixabay.com/api/videos/", params={"key": self._key, "q": query, "per_page": 8},
                             headers={"User-Agent": USER_AGENT}, timeout=(5, 20), allow_redirects=False)
        if r.status_code != 200:
            raise RuntimeError(f"pixabay_catalog_http_{r.status_code}")
        rows = r.json().get("hits") or []
        lic = self.terms.check(self.name)
        results = []
        for row in rows:
            files = [f for f in (row.get("videos") or {}).values() if f.get("url") and f.get("width") and f.get("height")]
            files.sort(key=lambda f: int(f["width"])*int(f["height"]), reverse=True)
            if not files or not row.get("id") or not valid_url(row.get("pageURL", ""), SOURCE_HOSTS[self.name]):
                continue
            f = files[0]; tags = tuple(x.strip() for x in str(row.get("tags", "")).split(",") if x.strip())
            results.append(MediaCandidate(self.name, str(row["id"]), row["pageURL"], f["url"], "video", int(f["width"]), int(f["height"]),
                                          float(row["duration"]) if row.get("duration") else None, title=" ".join(tags), tags=tags, license=lic))
        return results


class WikimediaProvider:
    """Final provider retained: video first, then stills, with no query dilution."""
    name = "wikimedia"

    def __init__(self, *, session=requests):
        self.session = session

    def search(self, query: str) -> list[MediaCandidate]:
        results = []
        for kind in ("video", "bitmap"):
            r = self.session.get("https://commons.wikimedia.org/w/api.php",
                                 params={"action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:{kind} {query}",
                                         "gsrnamespace": 6, "gsrlimit": 6, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata|metadata", "iiurlwidth": 1440},
                                 headers={"User-Agent": USER_AGENT}, timeout=(5, 25), allow_redirects=False)
            if r.status_code != 200:
                raise RuntimeError(f"commons_catalog_http_{r.status_code}")
            for page in ((r.json().get("query") or {}).get("pages") or {}).values():
                info = (page.get("imageinfo") or [{}])[0]
                mime = info.get("mime", "")
                if mime not in {"video/webm", "video/mp4", "video/ogg", "image/jpeg", "image/png"}:
                    continue
                image = mime.startswith("image/")
                # Use actual thumbnail dimensions, never claim original size for a thumbnail.
                link = (info.get("thumburl") or info.get("url", "")) if image else info.get("url", "")
                w = info.get("thumbwidth") or info.get("width") if image else info.get("width")
                h = info.get("thumbheight") or info.get("height") if image else info.get("height")
                metadata = {item.get("name"): item.get("value") for item in info.get("metadata", [])}
                length = metadata.get("length")
                ext = info.get("extmetadata") or {}
                results.append(MediaCandidate(self.name, str(page["pageid"]), info.get("descriptionurl", ""), link,
                                              "image" if image else "video", int(w) if w else None, int(h) if h else None,
                                              float(length) if length and not image else None,
                                              title=plain(page.get("title", "")), description=plain((ext.get("ImageDescription") or {}).get("value")),
                                              tags=tuple(plain((ext.get("Categories") or {}).get("value")).split("|")), license=commons_license(page, info)))
        return results


class BrowserStockProvider:
    """Strict metadata mode uses the existing cookie configuration, never legacy guessed URLs."""

    def __init__(self, provider: str, *, terms: StockTerms | None = None):
        if provider not in {"pexels", "pixabay"}:
            raise ValueError("unsupported_browser_provider")
        self.provider, self.name, self.terms = provider, f"{provider}-browser", terms or StockTerms()

    def search(self, query: str) -> list[MediaCandidate]:
        if not any((ROOT/p).exists() for p in ("cookies.json", "storage_state.json")):
            return []
        result = subprocess.run(["node", str(ROOT/"video_fetcher.js"), query, "--metadata", "--provider", self.provider],
                                cwd=ROOT, capture_output=True, text=True, timeout=85)
        if result.returncode != 0:
            raise RuntimeError("browser_catalog_failed")
        raw = json.loads(result.stdout)
        lic = self.terms.check(self.provider)
        out = []
        for row in raw.get("candidates", [])[:6]:
            if row.get("provider") != self.provider or not row.get("license_link_observed"):
                continue
            out.append(MediaCandidate(self.provider, str(row["media_id"]), row["source_url"], row["download_url"], "video",
                                      row.get("width"), row.get("height"), row.get("duration"), title=plain(row.get("title")),
                                      description=plain(row.get("description")), license=lic, catalog_transport="playwright"))
        return out


def default_providers() -> list[MediaProvider]:
    terms = StockTerms()
    return [PexelsProvider(terms=terms), PixabayProvider(terms=terms),
            BrowserStockProvider("pixabay", terms=terms), BrowserStockProvider("pexels", terms=terms), WikimediaProvider()]
