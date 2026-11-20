"""Faz6: cookie-free public providers — NasaProvider & InternetArchiveProvider.

Bu testler dis agya CIKMAZ; HTTP session mock'lanir. Amac:
- URL host allowlist dogrulamasi (download_url NASA/IA disinda ise reddeder).
- License/StockTerms davranisi (NASA: verified PD, IA: per-item verification).
- Search response parsing (manifest/HEAD filtreleri).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from types import SimpleNamespace

from src.media_processing.media_providers import (
    NasaProvider, InternetArchiveProvider, StockTerms, default_providers,
    DOWNLOAD_HOSTS, SOURCE_HOSTS, valid_url,
)


# ---------- Helpers ----------

class FakeResp:
    def __init__(self, status=200, json_data=None, headers=None, text=""):
        self.status_code = status
        self._json = json_data or {}
        self.headers = headers or {"content-type": "video/mp4", "content-length": "1048576"}
        self.text = text

    def json(self):
        return self._json

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")


class FakeSession:
    """Verilen URL -> cevap eslemesiyle mock HTTP session.

    Eslesme: tam URL ya da URL'nin basi (parametreli istekler icin).
    """

    def __init__(self, get_map=None, head_map=None):
        self.get_map = dict(get_map or {})
        self.head_map = dict(head_map or {})
        self.calls = []

    def _match(self, url, table):
        if url in table:
            return table[url]
        for prefix, resp in table.items():
            if url.startswith(prefix):
                return resp
        # Icinde gecen
        for needle, resp in table.items():
            if needle in url:
                return resp
        return None

    def get(self, url, **kw):
        self.calls.append(("get", url, kw))
        r = self._match(url, self.get_map)
        return r if r is not None else FakeResp(404)

    def head(self, url, **kw):
        self.calls.append(("head", url, kw))
        r = self._match(url, self.head_map)
        return r if r is not None else FakeResp(404)


# ---------- Host allowlist ----------

def test_nasa_hosts_allow_only_nasa_domains():
    assert "images-assets.nasa.gov" in DOWNLOAD_HOSTS["nasa"]
    assert "images-api.nasa.gov" in DOWNLOAD_HOSTS["nasa"]
    assert "images-api.nasa.gov" in SOURCE_HOSTS["nasa"]
    # Dis domain reddedilmeli
    assert not valid_url("https://evil.com/mars.mp4", DOWNLOAD_HOSTS["nasa"])
    # Dogru host kabul
    assert valid_url(
        "https://images-assets.nasa.gov/video/JPL/JPL~small.mp4",
        DOWNLOAD_HOSTS["nasa"],
    )


def test_archiveorg_hosts():
    assert "archive.org" in DOWNLOAD_HOSTS["archiveorg"]
    assert not valid_url("https://evil.com/video.mp4", DOWNLOAD_HOSTS["archiveorg"])
    assert valid_url(
        "https://archive.org/download/Felix/Felix.mp4",
        DOWNLOAD_HOSTS["archiveorg"],
    )


# ---------- Default provider wiring ----------

def test_default_providers_includes_nasa_and_ia():
    names = [p.name for p in default_providers()]
    assert "nasa" in names
    assert "archiveorg" in names
    # Sira: pexels, pixabay, nasa, archiveorg, wikimedia
    assert names.index("nasa") < names.index("archiveorg")
    assert names.index("archiveorg") < names.index("wikimedia")


# ---------- StockTerms ----------

def test_stock_terms_nasa_is_verified_public_domain():
    terms = StockTerms(session=FakeSession())
    lic = terms.check("nasa")
    assert lic.verified is True
    assert "Public Domain" in lic.name or "public domain" in lic.name.lower()
    assert lic.attribution_required is False
    assert "third_party_rights_not_verified" in lic.restrictions


def test_stock_terms_ia_pending_per_item():
    terms = StockTerms(session=FakeSession())
    lic = terms.check("archiveorg")
    # Per-item lisans dogrulamasi indirme sonrasi gerekir; search asamasinda
    # verified=False donmesi guvenli varsayimdir.
    assert lic.verified is False
    assert lic.rejection_reason == "per_item_license_verification_required_after_download"


# ---------- NASA search parsing ----------

NASA_SEARCH_RESP = {
    "collection": {
        "items": [
            {
                "data": [{"nasa_id": "TEST_NASA_001", "title": "Mars Rover Test",
                          "description": "A test video of Mars",
                          "keywords": ["mars", "rover"]}],
                "links": [{"render": "image", "href": "https://images-assets.nasa.gov/thumb.jpg"}],
            },
            {"nope": "no-data"},  # gecersiz kayit — atlanmali
            {
                "data": [{"nasa_id": "TEST_NO_MANIFEST", "title": "Missing Manifest Video",
                          "description": "Manifest 404 donecek"}],
            },
        ]
    }
}

NASA_MANIFEST_RESP = [
    "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~orig.mp4",
    "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~medium.mp4",
    "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~small.mp4",
    "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~mobile.mp4",
]


def test_nasa_search_picks_smallest_mp4_under_64mb():
    get_map = {
        "https://images-api.nasa.gov/search":
            FakeResp(200, json_data=NASA_SEARCH_RESP),
        "https://images-assets.nasa.gov/video/TEST_NASA_001/collection.json":
            FakeResp(200, json_data=NASA_MANIFEST_RESP),
        "https://images-assets.nasa.gov/video/TEST_NO_MANIFEST/collection.json":
            FakeResp(404),
    }
    # HEAD cevaplari: sadece mobile.mp4 kucuk (10 MB), digerleri 200+ MB
    head_map = {
        "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~orig.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(800*1024*1024)}),
        "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~medium.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(200*1024*1024)}),
        "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~small.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(80*1024*1024)}),
        "https://images-assets.nasa.gov/video/TEST_NASA_001/TEST_NASA_001~mobile.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(10*1024*1024)}),
    }
    sess = FakeSession(get_map=get_map, head_map=head_map)
    nasa = NasaProvider(session=sess)
    cands = nasa.search("mars")
    assert len(cands) == 1, f"1 aday bekleniyor (no-manifest elenmeli), {len(cands)} bulundu"
    c = cands[0]
    assert c.provider == "nasa"
    assert c.media_id == "TEST_NASA_001"
    # En kucuk MP4 secilmeli: mobile.mp4
    assert c.download_url.endswith("~mobile.mp4")
    assert c.license.verified is True


# ---------- IA search parsing ----------

IA_SEARCH_RESP = {
    "response": {
        "docs": [
            {"identifier": "Felix_BoldKingCole", "title": "Felix the Cat",
             "description": "Public domain cartoon"},
            {"identifier": "no_mp4_here", "title": "No MP4 derive"},
            {"identifier": "too_big", "title": "Massive video"},
        ]
    }
}


def test_ia_search_head_filters_mp4_under_64mb():
    get_map = {
        "https://archive.org/advancedsearch.php": FakeResp(200, json_data=IA_SEARCH_RESP),
    }
    head_map = {
        "https://archive.org/download/Felix_BoldKingCole/Felix_BoldKingCole.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(20*1024*1024)}),
        "https://archive.org/download/no_mp4_here/no_mp4_here.mp4":
            FakeResp(404),
        "https://archive.org/download/no_mp4_here/no_mp4_here_512kb.mp4":
            FakeResp(404),
        "https://archive.org/download/too_big/too_big.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(200*1024*1024)}),
    }
    sess = FakeSession(get_map=get_map, head_map=head_map)
    ia = InternetArchiveProvider(session=sess)
    cands = ia.search("felix cat")
    # yalnizca Felix gecmeli (no_mp4 404, too_big >64MB)
    assert len(cands) == 1, f"1 aday bekleniyor, {len(cands)}: {[c.title for c in cands]}"
    c = cands[0]
    assert c.provider == "archiveorg"
    assert c.media_id == "Felix_BoldKingCole"
    assert c.download_url.endswith("Felix_BoldKingCole.mp4")
    # IA lisans per-item pending
    assert c.license.verified is False


# ---------- Calistir ----------

if __name__ == "__main__":
    import traceback
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception:
            print(f"FAIL  {t.__name__}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
