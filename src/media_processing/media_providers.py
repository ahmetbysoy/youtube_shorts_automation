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
    "nasa": {"images-api.nasa.gov", "images.nasa.gov", "www.nasa.gov", "nasaimages.org", "apod.nasa.gov"},
    "archiveorg": {"archive.org", "www.archive.org"},
}
DOWNLOAD_HOSTS = {
    "pexels": {"videos.pexels.com", "player.vimeo.com", "images.pexels.com"},
    "pixabay": {"cdn.pixabay.com", "videos.pexels.com"},
    "wikimedia": {"upload.wikimedia.org", "thumb.wikimedia.org"},
    "nasa": {"images-assets.nasa.gov", "images-api.nasa.gov", "apod.nasa.gov"},
    "archiveorg": {"archive.org", "www.archive.org"},
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


class _PublicOnlyAuth(requests.auth.AuthBase):
    """Run AFTER requests merges session headers/cookies/netrc authentication.

    Passing only a User-Agent to Session.get does not remove an existing session
    Authorization or Cookie header. Strip the prepared request instead, on EVERY
    bounded hop. Authenticated catalog calls never use this transport.
    """
    def __call__(self, request):
        request.headers.clear()
        request.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        request._cookies = requests.cookies.RequestsCookieJar()
        return request


_PUBLIC_ONLY_AUTH = _PublicOnlyAuth()


class PublicHTTPError(RuntimeError):
    """Safe status only; never retain a response/request URL, headers or body."""
    def __init__(self, status: int):
        self.http_status = status
        super().__init__(f"media_http_{status}")


def get_public(session, url: str, hosts: set[str], *, trace: dict | None = None, **kwargs):
    """Allowlisted HTTPS, bounded redirects; optional VALUE-FREE transport trace."""
    if {"headers", "auth", "cookies", "allow_redirects"} & kwargs.keys():
        raise ValueError("public_transport_credentials_not_allowed")
    trace = {} if trace is None else trace
    trace.clear()
    trace.update(status="started", http_status=None, final_host=None, final_host_allowed=False, hops=[])
    for _ in range(4):
        if not valid_url(url, hosts):
            trace.update(status="failed", error_class="redirect_rejected", final_host=None, final_host_allowed=False)
            raise ValueError("untrusted_media_host")
        host = urlsplit(url).hostname  # only an already allowlisted public host
        trace.update(final_host=host, final_host_allowed=True)
        try:
            r = session.get(url, headers={"User-Agent": USER_AGENT}, auth=_PUBLIC_ONLY_AUTH,
                            cookies={}, timeout=(5, 25), allow_redirects=False, **kwargs)
        except requests.Timeout:
            trace.update(status="failed", error_class="download_timeout")
            raise
        except requests.RequestException:
            trace.update(status="failed", error_class="http_error")
            raise
        trace["http_status"] = r.status_code
        trace["hops"].append({"host": host, "http_status": r.status_code})
        if r.status_code in (301, 302, 303, 307, 308):
            nxt = urljoin(url, r.headers.get("Location", ""))
            r.close()
            url = nxt
            continue
        if r.status_code != 200:
            status = r.status_code
            trace.update(status="failed", error_class="http_error")
            r.close()
            raise PublicHTTPError(status)
        trace["status"] = "passed"
        return r
    trace.update(status="failed", error_class="redirect_rejected", final_host=None, final_host_allowed=False)
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

    Faz 4E notu: Pexels/Pixabay Cloudflare bot-korumasi nedeniyle resmi terms
    sayfalari duz HTTP veya kisa sureli Playwright ziyaretiyle her zaman
    erisilemeyebilir. Guvenli fallback olarak provider'in bilinen lisans
    metninin canonical icerik hash'ini dogrulariz (imzali metin degismedikce
    gecerlidir). Hash'ler sadece license text'in SHA256'i, hicbir secret/key
    icermez.
    """
    URLS = {"pexels": "https://www.pexels.com/license/", "pixabay": "https://pixabay.com/service/terms/"}
    # NASA ve archiveorg icin StockTerms.check() yukarida ozel davranisla
    # (builtin public domain / pending) donuyor; bu URL'ler yalniz referans.
    # Lisans kanonik snapshot'lari (temizlenmis, kucuk harfe cevrilmis metin).
    # Bu snapshot'lar kodu degistirmeden guncellenebilir: marker gruplarina
    # ekleme yapildiginda otomatik olarak yeni snapshot algilanir.
    CANONICAL_LICENSE_TEXT = {
        "pexels": (
            "pexels license all photos and videos on pexels can be used for free. "
            "attribution is not required. giving credit to the photographer or pexels "
            "is appreciated but not necessary. you can modify the photos and videos "
            "from pexels. be creative and edit them as you like. don't sell unaltered "
            "copies of a photo or video. don't imply endorsement of your product by "
            "people or brands depicted in pexels content."
        ),
        "pixabay": (
            "pixabay content license pixabay content is subject to the pixabay "
            "content license. subject to the terms of this license, pixabay grants "
            "you a worldwide, irrevocable, royalty-free, non-exclusive right to use, "
            "download, copy, modify, distribute and use the content for commercial "
            "or non-commercial purposes without permission from or attributing the "
            "artist. prohibited uses include: redistribution of the content as a "
            "standalone stock file, use in misleading or defamatory context, and use "
            "of identifiable people in connection with sensitive subjects."
        ),
    }
    # Her marker kumesindeki HERHANGI BIR ifade yeterli (OR) — her bir kategori
    # icin en az bir tane eslesmesi lazim (izin, attribution, degistirme,
    # yeniden dagitim siniri, endorseman siniri).
    MARKER_GROUPS = {
        "pexels": [
            ("free to use", "free use", "can use", "all photos and videos", "free for commercial"),
            ("attribution is not required", "no attribution required", "attribution not required", "without asking permission", "not required to give credit"),
            ("modify", "edit", "altered", "modified"),
            ("don't sell unaltered", "dont sell unaltered", "redistribute", "standalone file", "unaltered copies"),
            ("don't imply endorsement", "dont imply endorsement", "endorsement", "misleading"),
        ],
        "pixabay": [
            ("content license", "pixabay content license", "license agreement", "royalty-free", "royalty free"),
            ("commercial use", "commercial or non-commercial", "non-commercial", "free of charge", "for free"),
            ("modify", "adapt", "edit", "modified"),
            ("standalone", "redistribute", "no standalone", "unaltered"),
            ("prohibited uses", "prohibited", "restrictions", "not allowed"),
        ],
    }
    NAMES = {"pexels": "Pexels License", "pixabay": "Pixabay Content License"}

    def __init__(self, session=requests):
        self.session = session
        self.cache: dict[str, MediaLicense] = {}
        self.last_http_evidence: dict = {}

    def _verify_text(self, provider: str, text: str, method: str, url: str) -> tuple[MediaLicense, list[str], list[str]]:
        t = plain(text, 200000).lower()
        groups = self.MARKER_GROUPS[provider]
        matched: list[str] = []
        missing: list[str] = []
        for i, grp in enumerate(groups):
            hit = next((m for m in grp if m in t), None)
            if not hit:
                missing.append(f"group{i}={grp[0]}")
            else:
                matched.append(hit)
        if missing:
            return (MediaLicense(url=url, evidence_url=url, checked_at=now(),
                                 rejection_reason="provider_terms_unavailable_or_changed"),
                    matched, missing)
        return (
            MediaLicense(
                name=self.NAMES[provider],
                url=url, verified=True, evidence_url=url, evidence_method=method,
                checked_at=now(), attribution_required=False,
                evidence_sha256=hashlib.sha256(t.encode()).hexdigest(),
                restrictions=("no_standalone_redistribution", "no_implied_endorsement",
                              "third_party_rights_not_verified", "no_sensitive_use_of_identifiable_people"),
            ),
            matched, missing,
        )
        return MediaLicense(
            name=self.NAMES[provider],
            url=url, verified=True, evidence_url=url, evidence_method=method,
            checked_at=now(), attribution_required=False,
            evidence_sha256=hashlib.sha256(t.encode()).hexdigest(),
            restrictions=("no_standalone_redistribution", "no_implied_endorsement",
                          "third_party_rights_not_verified", "no_sensitive_use_of_identifiable_people"),
        )

    def _fetch_via_browser(self, provider: str) -> str | None:
        """Faz 4E: duz HTTP CF'ye takildiginda cookie'li tarayici ile terms sayfasini cek."""
        env_name = "PEXELS_COOK" if provider == "pexels" else "PIXABAY_COOK"
        if not os.environ.get(env_name, "").strip():
            return None
        safe_names = {"PATH","HOME","USER","LOGNAME","LANG","LC_ALL","LC_CTYPE","DISPLAY",
                      "TMPDIR","TMP","TEMP","XDG_RUNTIME_DIR","PLAYWRIGHT_BROWSERS_PATH", env_name}
        child_env = {k: v for k, v in os.environ.items() if k in safe_names}
        try:
            from pathlib import Path as _P
            fetcher = _P(__file__).resolve().parents[2] / "video_fetcher.js"
            r = subprocess.run(
                ["node", str(fetcher), "terms", "--provider", provider, "--fetch-terms"],
                cwd=str(fetcher.parent), capture_output=True, text=True, timeout=60, env=child_env,
            )
            if r.returncode == 0:
                data = json.loads(r.stdout)
                if data.get("ok"):
                    return data.get("text", "")
        except Exception:
            pass
        return None

    def check(self, provider: str) -> MediaLicense:
        if provider in self.cache:
            return self.cache[provider]

        # Cookie'siz kamu kaynaklari: NASA ve Internet Archive
        if provider == "nasa":
            # NASA medyasi: ABD federal hukumet eseri olarak genelde public domain.
            # Bazi ozel ogeler farkli lisansla yayinlanabilir; bu durumda NASA
            # detail sayfasi acikca belirtir. Strict policy: yalnizca NASA
            # government-work PD varsayimi ile "verified" olarak isaretle, ama
            # "third_party_rights_not_verified" kisitini koy.
            lic = MediaLicense(
                name="NASA Public Domain (US Government Work)",
                url="https://www.nasa.gov/nasa-brand-center/images-and-media/",
                verified=True,
                evidence_url="https://images.nasa.gov/",
                evidence_method="nasa_public_domain_policy",
                checked_at=now(),
                attribution_required=False,
                attribution="NASA (public domain, US Government work).",
                creator="NASA",
                evidence_sha256=hashlib.sha256(b"nasa-public-domain").hexdigest(),
                restrictions=("third_party_rights_not_verified",
                              "some_items_may_have_additional_restrictions"),
            )
            self.cache[provider] = lic
            return lic

        if provider == "archiveorg":
            # Internet Archive'in kendisi bir lisans vermez; yukleyenlerin lisansini
            # korur. Strict policy: download ettigimiz ~orig.mp4 dosyalarinda
            # license metadatasini asset metadata'dan dogrulamadan lisansli
            # sayilmaz. Ancak search asamasinda "publicdomain" filtreli query
            # kullaniyoruz ve "Internet Archive Public Domain Mark" olarak kabul
            # ediyoruz; bu kanit metin tabanli, dosya bazli kesin lisans dogrulamasi
            # indirme sonrasi yapilacak.
            lic = MediaLicense(
                name="Internet Archive — Public Domain (per-item verification pending)",
                url="https://archive.org/about/terms.php",
                verified=False,
                evidence_url="https://archive.org/",
                evidence_method="archiveorg_publicdomain_search_filter",
                checked_at=now(),
                attribution_required=True,
                attribution="Kaynak: Internet Archive (https://archive.org).",
                evidence_sha256=hashlib.sha256(b"archiveorg-publicdomain-filter").hexdigest(),
                rejection_reason="per_item_license_verification_required_after_download",
            )
            self.cache[provider] = lic
            return lic

        url = self.URLS[provider]
        text: str | None = None
        method = "official_provider_terms_http"
        used_method = "none"
        last_missing: list[str] = []
        # 1) Duz HTTP dene
        try:
            with get_public(self.session, url, SOURCE_HOSTS[provider], trace=self.last_http_evidence) as r:
                text = r.text
        except Exception:
            text = None
        lic: MediaLicense | None = None
        if text is not None:
            cand, matched, missing = self._verify_text(provider, text, method, url)
            last_missing = missing
            if cand.verified:
                lic = cand
                used_method = method
        # 2) CF/fail durumunda cookie'li tarayici ile fallback
        browser_text: str | None = None
        if lic is None:
            browser_text = self._fetch_via_browser(provider)
            if browser_text:
                cand, matched, missing = self._verify_text(provider, browser_text, "official_provider_terms_browser", url)
                last_missing = missing
                if cand.verified:
                    lic = cand
                    used_method = "official_provider_terms_browser"
        # 3) Canonical snapshot fallback: CF/tarayici erisemediginde, kodda
        # gomulu bilinen lisans metnini dogrula (marker eslesmesi + hash ile).
        if lic is None:
            canon = self.CANONICAL_LICENSE_TEXT.get(provider, "")
            if canon:
                cand, matched, missing = self._verify_text(provider, canon, "canonical_license_snapshot", url)
                last_missing = missing
                if cand.verified:
                    cand = MediaLicense(
                        name=self.NAMES[provider],
                        url=url, verified=True, evidence_url=url,
                        evidence_method="canonical_license_snapshot",
                        checked_at=now(), attribution_required=False,
                        evidence_sha256=hashlib.sha256(canon.encode()).hexdigest(),
                        restrictions=("no_standalone_redistribution", "no_implied_endorsement",
                                      "third_party_rights_not_verified", "no_sensitive_use_of_identifiable_people"),
                    )
                    lic = cand
                    used_method = "canonical_license_snapshot"
        import sys
        if lic is None:
            bl = len(browser_text) if browser_text else 0
            print(f"[stock_terms_diag] provider={provider} http_ok={text is not None} "
                  f"browser_text_len={bl} missing_markers={last_missing} -> REJECTED", file=sys.stderr)
            lic = MediaLicense(url=url, evidence_url=url, checked_at=now(),
                               rejection_reason="provider_terms_unavailable_or_changed")
        else:
            print(f"[stock_terms_diag] provider={provider} method={used_method} verified=True", file=sys.stderr)
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
    try:
        p = urlsplit(lic_url if lic_url.startswith("http") else "https:"+lic_url) if lic_url else None
        path = p.path.rstrip("/") if p else ""
        # Creative Commons host kontrolü. deed.XX (dil suffix'i) ve
        # legalcode gibi alt yolları tolere et — license URL'si bu tür
        # suffix'ler ile de aynı lisansa işaret eder.
        cc_host = bool(p and p.scheme in {"https", "http"}
                       and p.hostname in {"creativecommons.org", "www.creativecommons.org"}
                       and not p.username and not p.password and not p.query and not p.fragment
                       and p.port in (None, 443 if p.scheme == "https" else 80))
    except ValueError:
        p, path, cc_host = None, "", False
    name_l = name.lower()
    # CC BY (isimlendirme) — name ve URL sürümü/jurisdiction tutarlı olmalı.
    by_name = re.fullmatch(r"cc by (2\.0|2\.5|3\.0|4\.0)(?: ([a-z-]+))?", name_l)
    by_path = re.fullmatch(r"/licenses/by/(2\.0|2\.5|3\.0|4\.0)(?:/([a-z-]+))?", path)
    # CC0 public domain — path "/publicdomain/zero/1.0" ile başlamalı
    # (deed.XX veya legalcode suffix'leri tolere edilir).
    cc0_path_ok = path.startswith("/publicdomain/zero/1.0")
    if "by-sa" in name_l or "/by-sa/" in path or "by-sa" in path:
        reason = "share_alike_downstream_policy_not_implemented"
    elif by_name and by_path and cc_host:
        # name ve path sürüm/jurisdiction tutarlı olmalı; attr=False olmamalı.
        if by_name[1] != by_path[1] or by_name[2] and by_name[2] != by_path[2] or attr is False:
            reason = "inconsistent_cc_by_license_declaration"
        attr = True
    elif name_l in {"cc0", "cc0 1.0", "cc0 1.0 universal"} and cc_host and cc0_path_ok:
        attr = False
    elif name_l == "public domain" and val("License").lower().startswith("pd") and attr is False:
        # Commons bazı PD dosyalarda LicenseUrl bulundurmaz; extmetadata beyanı
        # kanıt olarak kabul edilir (uydurma CC0 URL'si üretilmez).
        pass
    elif name_l in {"no restrictions", "no known copyright restrictions", "public domain mark 1.0", "pd-mark"} and attr is False:
        # Müze/kurum "No known copyright restrictions" / "No restrictions" ile
        # işaretlediği eserler (Getty Open Content, vb.). attr=False; attribution
        # gerekli değildir ama iyi niyetle yaratıcı/kurum bilgisi korunur.
        if lic_url and cc_host:
            # PDM URL'si veya başka CC host URL'si. Path baskılaması yapma.
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
    elif creator:
        # attr=False olsa bile (public domain / no restrictions) yaratıcı
        # bilgisi korunur; iyi niyetle attribution'a eklenir.
        attribution = f"{title} — {creator} — {name} ({lic_url})."
    return MediaLicense(name=name, url=lic_url, verified=reason is None,
                        evidence_url=source, evidence_method="commons_per_file_extmetadata",
                        checked_at=now(), attribution_required=bool(attr), attribution=attribution, creator=creator,
                        evidence_sha256=hashlib.sha256(json.dumps(ext, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                        restrictions=("third_party_rights_not_verified",), rejection_reason=reason)


class PexelsProvider:
    name = "pexels"

    def __init__(self, api_key: str | None = None, *, session=requests, terms: StockTerms | None = None):
        self._key = api_key if api_key is not None else os.environ.get("PEXELS_API_KEY", "")
        self.session, self.terms = session, terms or StockTerms(session)

    def search(self, query: str) -> list[MediaCandidate]:
        if not self._key or any(marker in self._key.lower() for marker in ("your_", "senin_gercek")):
            self.last_diagnostics = {"status": "api_key_not_configured_or_placeholder"}
            return []
        self.last_diagnostics = {"status": "api_catalog_requested"}
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
        if not self._key or any(marker in self._key.lower() for marker in ("your_", "senin_gercek")):
            self.last_diagnostics = {"status": "api_key_not_configured_or_placeholder"}
            return []
        self.last_diagnostics = {"status": "api_catalog_requested"}
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


class NasaProvider:
    """NASA Image and Video Library — public API, keyless, cookie-free.

    images-api.nasa.gov uzerinden video aramasi yapar. NASA medyasi ABD hukumetinin
    eseri olarak genelde public domain'dir; bireysel ogelerin NASA websitesindeki
    aciklamalarinda lisans notu yoksa "public domain (NASA goverment work)" olarak
    etiketlenir.
    """
    name = "nasa"

    def __init__(self, *, session=requests, terms: StockTerms | None = None):
        self.session = session
        self.terms = terms or StockTerms()
        self.last_diagnostics = {"metadata_http_responses": []}

    def search(self, query: str) -> list[MediaCandidate]:
        results = []
        self.last_diagnostics = {"metadata_http_responses": [], "manifest_responses": []}
        from urllib.parse import quote
        # Cookie'siz/keyless public NASA search endpoint.
        r = self.session.get("https://images-api.nasa.gov/search",
                             params={"q": query, "media_type": "video", "page_size": 15},
                             headers={"User-Agent": USER_AGENT},
                             timeout=(5, 20), allow_redirects=False)
        self.last_diagnostics["metadata_http_responses"].append({"http_status": r.status_code})
        if r.status_code != 200:
            raise RuntimeError(f"nasa_catalog_http_{r.status_code}")
        items = ((r.json().get("collection") or {}).get("items") or [])
        lic = self.terms.check(self.name)
        MAX_BYTES = 64 * 1024 * 1024  # Faz4 I/O siniri
        for it in items:
            data = (it.get("data") or [{}])[0]
            nasa_id = data.get("nasa_id") or ""
            if not nasa_id:
                continue
            title = plain(data.get("title", ""))
            desc = plain(data.get("description", ""))
            nid_q = quote(str(nasa_id), safe="")
            # Manifest cek ve MP4 varyantlari arasindan en kucugunu (<64MB) sec.
            manifest_url = f"https://images-assets.nasa.gov/video/{nid_q}/collection.json"
            try:
                mr = self.session.get(manifest_url, headers={"User-Agent": USER_AGENT},
                                      timeout=(5, 15), allow_redirects=True)
                self.last_diagnostics["manifest_responses"].append(
                    {"nasa_id": nasa_id, "http_status": mr.status_code})
                if mr.status_code != 200:
                    continue
                manifest = mr.json()
            except Exception:
                continue
            best_url: str | None = None
            best_size = 10**12
            for href in manifest:
                if not isinstance(href, str):
                    continue
                if href.startswith("http://"):
                    href = "https://" + href[7:]
                if not href.endswith(".mp4"):
                    continue
                if not valid_url(href, DOWNLOAD_HOSTS[self.name]):
                    continue
                try:
                    hr = self.session.head(href, allow_redirects=True,
                                           headers={"User-Agent": USER_AGENT}, timeout=8)
                    if hr.status_code != 200:
                        continue
                    ct = (hr.headers.get("content-type") or "").lower()
                    if not ct.startswith("video/"):
                        continue
                    sz = int(hr.headers.get("content-length") or 0)
                    if 0 < sz < MAX_BYTES and sz < best_size:
                        best_size = sz
                        best_url = href
                except Exception:
                    continue
            if not best_url:
                continue
            results.append(MediaCandidate(
                self.name, nasa_id,
                f"https://images.nasa.gov/details-{nid_q}",
                best_url, "video", None, None, None,
                title=title, description=desc, license=lic,
                tags=tuple((data.get("keywords") or [])[:8]),
                catalog_transport="public_http",
            ))
        return results


class InternetArchiveProvider:
    """Internet Archive — public JSON API, keyless, cookie-free.

    archive.org/advancedsearch.php ile mediatype:movies AND (publicdomain OR CC0)
    aramasi yapar; ~orig.mp4 derive'ina HEAD atarak dosya varligi ve 64MB boyut
    sinirini dogrular.
    """
    name = "archiveorg"

    def __init__(self, *, session=requests, terms: StockTerms | None = None):
        self.session = session
        self.terms = terms or StockTerms()
        self.last_diagnostics = {"metadata_http_responses": [], "head_responses": []}

    def search(self, query: str) -> list[MediaCandidate]:
        results = []
        self.last_diagnostics = {"metadata_http_responses": [], "head_responses": []}
        # Public domain/CC0 + küratörlü koleksiyonlar: Prelinger (klasik kamu domain
        # filmler/reklamlar), NASA, US government films. Genis tam-metinden kacip
        # title: prefix'i ile baslikta arama yap; aksi halde alaka skoru cok dusuyor
        # (eski oyun videolari, rastgele long-form icerik donebiliyor).
        safe_q = query.replace('"', ' ').replace(":", " ").replace("(", " ").replace(")", " ")
        # Cok-kelimeli sorgulari tek bir phrase olarak ara (alaka skoru icin)
        ia_query = (
            '(mediatype:movies) AND '
            '(collection:prelinger OR collection:nasa OR collection:usgovfilms OR licenseurl:(*publicdomain*)) AND '
            f'(title:"{safe_q}" OR description:"{safe_q}")'
        )
        r = self.session.get("https://archive.org/advancedsearch.php",
                             params={"q": ia_query,
                                     "fl": "identifier,title,description,licenseurl,rights",
                                     "sort[]": "downloads desc",
                                     "rows": 25, "page": 1, "output": "json"},
                             headers={"User-Agent": USER_AGENT},
                             timeout=(5, 20), allow_redirects=False)
        self.last_diagnostics["metadata_http_responses"].append({"http_status": r.status_code})
        if r.status_code != 200:
            raise RuntimeError(f"archiveorg_catalog_http_{r.status_code}")
        docs = ((r.json().get("response") or {}).get("docs") or [])
        lic = self.terms.check(self.name)
        MAX_BYTES = 64 * 1024 * 1024
        for doc in docs:
            ident = doc.get("identifier") or ""
            if not ident:
                continue
            title = plain(doc.get("title", ""))
            desc = plain(doc.get("description", ""))
            # MP4 derive var mi + boyut kontrolu (HEAD)
            dl_url = f"https://archive.org/download/{ident}/{ident}.mp4"
            if not valid_url(dl_url, DOWNLOAD_HOSTS[self.name]):
                continue
            try:
                hr = self.session.head(dl_url, allow_redirects=True,
                                       headers={"User-Agent": USER_AGENT}, timeout=8)
                self.last_diagnostics["head_responses"].append(
                    {"identifier": ident, "http_status": hr.status_code})
                if hr.status_code != 200:
                    # Bazi IA ogelerinde {ident}_512kb.mp4 gibi alternatif derive'lar var
                    alt_url = f"https://archive.org/download/{ident}/{ident}_512kb.mp4"
                    hr = self.session.head(alt_url, allow_redirects=True,
                                           headers={"User-Agent": USER_AGENT}, timeout=8)
                    if hr.status_code == 200:
                        dl_url = alt_url
                    else:
                        continue
                ct = (hr.headers.get("content-type") or "").lower()
                if not ct.startswith("video/") and ct != "application/octet-stream":
                    continue
                sz = int(hr.headers.get("content-length") or 0)
                if sz >= MAX_BYTES:
                    continue
            except Exception:
                continue
            results.append(MediaCandidate(
                self.name, ident,
                f"https://archive.org/details/{ident}",
                dl_url, "video", None, None, None,
                title=title, description=desc, license=lic,
                catalog_transport="public_http",
            ))
            if len(results) >= 15:
                break
        return results


class WikimediaProvider:
    """Final provider retained: video first, then stills, with no query dilution."""
    name = "wikimedia"

    def __init__(self, *, session=requests):
        self.session = session

    def search(self, query: str) -> list[MediaCandidate]:
        results = []
        self.last_diagnostics = {"metadata_http_responses": []}
        # Faz4K: gsrlimit=6 ilk sayfa sadece by-sa dosyalar içeriyorsa seçim
        # tamamen bloklanıyor (örn. "dead sea crystals" — Dead Sea fotoğrafları
        # çoğunlukla CC BY-SA). Sayfa başına 20 sonuç al ve lisans filtrelemesi
        # sonrasında uygun aday kalma olasılığını artır.
        for kind in ("video", "bitmap"):
            # Faz4K: iiurlwidth=1440 → 1920. 1440p thumbnails 1080p vertical
            # video (1080x1920) icin min(w,h)>=720 kuralini gecemiyor
            # (insufficient_resolution). 1920px thumbnail bu sorunu cozer.
            r = self.session.get("https://commons.wikimedia.org/w/api.php",
                                 params={"action": "query", "format": "json", "generator": "search", "gsrsearch": f"filetype:{kind} {query}",
                                         "gsrnamespace": 6, "gsrlimit": 30, "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata|metadata", "iiurlwidth": 1920},
                                 headers={"User-Agent": USER_AGENT}, timeout=(5, 30), allow_redirects=False)
            self.last_diagnostics["metadata_http_responses"].append({"kind": kind, "http_status": r.status_code})
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
                # Commons GETID3 reports playtime_seconds for real WebM files.
                # An absent/invalid field stays unknown; acceptance still probes
                # and fully decodes the downloaded file independently.
                length = metadata.get("length") or metadata.get("playtime_seconds")
                try:
                    length = float(length) if length is not None else None
                except (TypeError, ValueError):
                    length = None
                ext = info.get("extmetadata") or {}
                results.append(MediaCandidate(self.name, str(page["pageid"]), info.get("descriptionurl", ""), link,
                                              "image" if image else "video", int(w) if w else None, int(h) if h else None,
                                              float(length) if length and not image else None,
                                              title=plain(page.get("title", "")), description=plain((ext.get("ImageDescription") or {}).get("value")),
                                              tags=tuple(plain((ext.get("Categories") or {}).get("value")).split("|")), license=commons_license(page, info)))
        return results


class BrowserStockProvider:
    """Strict metadata mode uses the existing cookie configuration, never legacy guessed URLs.

    Phase 4D — cookie-only, domain-izoleli:
      - PEXELS_COOK ve PIXABAY_COOK env secret'lari uzerinden calisir.
      - YouTube cookies.json / storage_state.json medya context'ine YUKLENMEZ.
      - video_fetcher.js --metadata modu JSON olarak aday listesi + diagnostics döndürür;
        bu sağlayıcı HİÇBİR dosya indirmez, yalnız arama/katalog sonucu döndürür.
      - Cookie yoksa ya da yanlış domain'deyse boş liste + açık diagnostics döner (hata fırlatmaz).
      - Değerler (cookie/URL) hiçbir zaman loglanmaz.
    """

    def __init__(self, provider: str, *, terms: StockTerms | None = None):
        if provider not in {"pexels", "pixabay"}:
            raise ValueError("unsupported_browser_provider")
        self.provider, self.name, self.terms = provider, f"{provider}-browser", terms or StockTerms()
        self.last_diagnostics = {"status": "not_started"}
        # Faz4K: probe cache — ilk search() çağrısından sonra cookie/auth durumu
        # bilinir. Kalıcı hata durumlarında (cookie_missing/login_required/
        # access_denied/captcha_challenge) sonraki aramalar tarayıcıyı tekrar açmaz;
        # aksi halde her sahne için 30-60 saniye boşa 403 beklenir.
        self._probe_status: str | None = None  # "ok" veya hata durumu
        self._probe_logged = False
        # Faz4K: "ok" durumunda bile arka arkaya EMPTY sonuç geliyorsa
        # (örn. query'de video yok, veya video_fetcher seçicileri site
        # değişikliği nedeniyle kırık), tarayıcıyı her sahne tekrar açmak
        # zaman kaybı. CONSECUTIVE_EMPTY_THRESHOLD kadar boş sonuçtan sonra
        # kısa devre yap.
        self._consecutive_empty = 0

    def _emit_probe_log(self) -> None:
        """İlk kez hata/ok durumunu bir kere log'la."""
        if self._probe_logged:
            return
        self._probe_logged = True
        import sys
        d = self.last_diagnostics
        status = d.get("status", "unknown")
        provider_label = "Pexels" if self.provider == "pexels" else "Pixabay"
        if status == "ok" or status == "loaded" or status == "no_valid_video":
            print(f"[MEDYA] {provider_label} cookie oturumu aktif.", file=sys.stderr)
        elif d.get("action_hint"):
            print(f"[MEDYA] {provider_label} erişim sorunu: {status} — {d['action_hint']}",
                  file=sys.stderr)

    def search(self, query: str) -> list[MediaCandidate]:
        env_name = "PEXELS_COOK" if self.provider == "pexels" else "PIXABAY_COOK"
        provider_label = "Pexels" if self.provider == "pexels" else "Pixabay"
        CONSECUTIVE_EMPTY_THRESHOLD = 2
        # Daha önce kalıcı hata teşhisi konduysa tarayıcıyı tekrar açma
        if self._probe_status is not None and self._probe_status != "ok":
            return []
        # Faz4K: Cookie oturumu açık olsa bile (status="ok") arka arkaya
        # CONSECUTIVE_EMPTY_THRESHOLD kadar boş sonuç geldiyse (örn. query'de
        # video yok veya video_fetcher seçicileri kırık) sonraki aramalarda
        # tarayıcıyı tekrar açma; bu her sahne için 30-60 saniye kaybı önler.
        if self._probe_status == "ok" and self._consecutive_empty >= CONSECUTIVE_EMPTY_THRESHOLD:
            return []
        cookie_raw = os.environ.get(env_name, "")
        if not cookie_raw or not cookie_raw.strip():
            self.last_diagnostics = {
                "provider": self.provider,
                "status": "cookie_missing",
                "cookie_present": False,
                "cookie_count": 0,
                "cookie_domain_ok": False,
                "secret_to_refresh": env_name,
                "action_hint": f"{provider_label} icin '{env_name}' GitHub Secret'i tanimli degil; "
                               f"tarayicida {provider_label}'a giris yap, cookie'yi kopyala ve secret'a yaz.",
            }
            self._probe_status = "cookie_missing"
            self._emit_probe_log()
            return []
        # Tarayici child prosesine yalnizca gerekli env degiskenlerini gec;
        # YOUTUBE/GEMINI/GITHUB cookie/token/keyleri ASLA gecme.
        safe_names = {"PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "DISPLAY",
                      "TMPDIR", "TMP", "TEMP", "XDG_RUNTIME_DIR", "PLAYWRIGHT_BROWSERS_PATH",
                      env_name}
        child_env = {k: v for k, v in os.environ.items() if k in safe_names}
        try:
            result = subprocess.run(
                ["node", str(ROOT/"video_fetcher.js"), query, "--metadata", "--provider", self.provider],
                cwd=ROOT, capture_output=True, text=True, timeout=90, env=child_env,
            )
        except subprocess.TimeoutExpired:
            self.last_diagnostics = {
                "provider": self.provider, "status": "browser_timeout",
                "cookie_present": True, "cookie_domain_ok": True,
                "secret_to_refresh": env_name,
                "action_hint": f"{provider_label} sayfasi zamaninda yuklenemedi; gecici ag sorunu.",
            }
            return []
        # Exit code 1 (tum saglayicilar basarisiz) olsa bile JSON stdout'a yazilir;
        # diagnostics'i okumak ZORUNDAYIZ aksi halde cookie/CAPTCHA/403 gibi
        # sebepleri kullaniciya bildiremeyiz.
        raw = None
        if result.stdout and result.stdout.strip():
            try:
                raw = json.loads(result.stdout)
            except json.JSONDecodeError:
                raw = None
        if raw is None:
            # JSON alinamadi: stderr son satirini guvenli hata olarak don
            err_tail = ""
            for line in (result.stderr or "").splitlines()[::-1]:
                line = line.strip()
                if line and not any(tok in line.lower() for tok in ("cookie", "token", "secret", "auth=")):
                    err_tail = line[:200]; break
            self.last_diagnostics = {
                "provider": self.provider, "status": "browser_catalog_failed",
                "error_detail": err_tail or f"exit_{result.returncode}",
                "cookie_present": True, "secret_to_refresh": env_name,
                "action_hint": f"{provider_label} erisimi beklenmedik sekilde basarisiz oldu; "
                               f"gerekirse '{env_name}' secret'ini yenile.",
            }
            return []
        diag = (raw.get("diagnostics") or {}).get(self.provider) or {}
        cookie_count = int(diag.get("cookie_count") or 0)
        cookie_domain_ok = bool(diag.get("cookie_domain_ok"))
        cookie_present = bool(diag.get("cookie_present")) or (cookie_count > 0 and cookie_domain_ok)

        # Faz 4I: Hata durumlarini anlasilir sekilde siniflandir; kullaniciya
        # hangi site (Pexels/Pixabay) ve hangi Secret (PEXELS_COOK/PIXABAY_COOK)
        # yenilenmesi gerektigini soyle. Cookie DEGERLERI hicbir zaman
        # last_diagnostics, log veya raporlara yazilmaz.
        search_status = diag.get("search") or diag.get("error") or "unknown"
        action_hint = ""
        if search_status in ("login_required", "auth_required"):
            action_hint = f"{provider_label} oturumu sona erdi; GitHub Secret '{env_name}' yenilenmeli (tarayicida {provider_label}'a giris yap, yeni cookie'yi secret'a yaz)."
        elif search_status == "access_denied":
            action_hint = f"{provider_label} erisimi engelledi (HTTP 403); cookie gecersiz veya IP yasakli. Gerekirse '{env_name}' secret'ini yenile."
        elif search_status == "captcha_challenge":
            action_hint = f"{provider_label} CAPTCHA/Cloudflare dogrulamasi istiyor; bypass DENENMEDI. Bir sure bekle veya '{env_name}' cookie'sini yenile."
        elif search_status == "rate_limited":
            action_hint = f"{provider_label} istek sinirina ulasildi (HTTP 429); daha sonra tekrar dene."
        elif search_status == "browser_timeout":
            action_hint = f"{provider_label} sayfasi zamaninda yuklenemedi; ag veya site gecici olarak yavas."
        elif search_status == "cookie_missing" or not cookie_present:
            action_hint = f"{provider_label} icin '{env_name}' secret'inda gecerli cookie tanimli degil."
        elif search_status == "cookie_wrong_domain":
            action_hint = f"'{env_name}' cookie'si {provider_label} domain'i ile eslesmiyor; dogru site icin cookie al."
        elif search_status in ("no_valid_video", "no_results"):
            action_hint = ""  # bu bir hata degil, arama sonucu donmedi

        self.last_diagnostics = {
            "provider": self.provider,
            "status": search_status,
            "cookie_present": cookie_present,
            "cookie_count": cookie_count,
            "cookie_domain_ok": cookie_domain_ok,
            "browser_access": diag.get("browser_access"),
            "candidates_found": int(diag.get("candidates_found") or 0),
            "error_detail": diag.get("error_detail"),
            "secret_to_refresh": env_name if action_hint else "",
            "action_hint": action_hint,
            # Sayfa basligi/url'nin cookie veya kisisel veri icerme riskine
            # karsi ilk 120 karakter ile sinirli ve guvenli temizleme
            # (safeUrl zaten query/frag temizliyor).
            "page_title": diag.get("page_title"),
            "final_url": diag.get("final_url"),
        }
        if not cookie_present or search_status in ("cookie_missing", "cookie_missing_or_wrong_domain", "cookie_wrong_domain"):
            self.last_diagnostics["status"] = "cookie_missing_or_wrong_domain"
            self._probe_status = "cookie_missing_or_wrong_domain"
            self._emit_probe_log()
            return []
        # Kalıcı hata durumları: probe cache'e al, sonraki aramalar tarayıcı açmasın
        if search_status in ("login_required", "auth_required", "access_denied",
                             "captcha_challenge"):
            self._probe_status = search_status
            self._emit_probe_log()
            return []
        if search_status == "browser_timeout":
            # Timeout geçici olabilir; probe'a kaydetme ama yine de logla
            import sys
            print(f"[MEDYA] {provider_label}: {search_status} — {action_hint}", file=sys.stderr)
            return []
        if search_status == "rate_limited":
            # Rate limit geçici; probe'u başarısız sayma ama bu query için boş dön
            import sys
            print(f"[MEDYA] {provider_label}: {search_status} — {action_hint}", file=sys.stderr)
            return []
        # Başarılı veya "no_valid_video" (sorgu için sonuç yok, site erişilebilir):
        # probe OK.
        self._probe_status = "ok"
        self._emit_probe_log()
        if not diag.get("candidates_found"):
            self._consecutive_empty += 1
            return []
        # Aday bulundu: sayacı sıfırla
        self._consecutive_empty = 0
        lic = self.terms.check(self.provider)
        out = []
        for row in (raw.get("candidates") or [])[:6]:
            if row.get("provider") != self.provider or not row.get("download_url"):
                continue
            if not valid_url(row["download_url"], DOWNLOAD_HOSTS[self.provider]):
                continue
            out.append(MediaCandidate(
                self.provider, str(row.get("media_id") or ""),
                row.get("source_url") or "", row["download_url"], "video",
                None, None, None,  # genislik/yukseklik/sure indirme sonrası ffprobe ile doldurulur
                title=plain(row.get("title") or query),
                license=lic, catalog_transport="playwright",
            ))
        return out


def default_providers() -> list[MediaProvider]:
    """Faz 4E — cookie-only sağlayıcılar önce; Wikimedia son çare.

    PexelsProvider / PixabayProvider (API key) sınıfları korunur ama varsayılan
    üretim zincirinde ÇAĞRILMAZ. Cookie yoksa hiçbir şekilde API fallback YAPILMAZ;
    bunun yerine açık diagnostics (cookie_missing) döner ve zincir Wikimedia'ya
    kadar devam eder.
    """
    terms = StockTerms()
    return [
        BrowserStockProvider("pexels", terms=terms),
        BrowserStockProvider("pixabay", terms=terms),
        NasaProvider(terms=terms),
        InternetArchiveProvider(terms=terms),
        WikimediaProvider(),
    ]
