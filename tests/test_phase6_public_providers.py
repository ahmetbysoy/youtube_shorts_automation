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
    NasaProvider, InternetArchiveProvider, MixkitProvider, StockTerms, default_providers,
    DOWNLOAD_HOSTS, SOURCE_HOSTS, valid_url,
)


# ---------- Helpers ----------

class FakeResp:
    def __init__(self, status=200, json_data=None, headers=None, text="", url=None):
        self.status_code = status
        self._json = json_data or {}
        self.headers = headers or {"content-type": "video/mp4", "content-length": "1048576"}
        self.text = text
        self.url = url or ""
        self.content = text.encode("utf-8") if text else b""

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
            r = table[url]
            if r.url == "":
                r.url = url
            return r
        for prefix, resp in table.items():
            if url.startswith(prefix):
                if resp.url == "":
                    resp.url = url
                return resp
        for needle, resp in table.items():
            if needle in url:
                if resp.url == "":
                    resp.url = url
                return resp
        return None

    def get(self, url, **kw):
        self.calls.append(("get", url, kw))
        r = self._match(url, self.get_map)
        if r is None:
            return FakeResp(404, url=url)
        return r

    def head(self, url, **kw):
        self.calls.append(("head", url, kw))
        r = self._match(url, self.head_map)
        if r is None:
            return FakeResp(404, url=url)
        return r


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

def test_default_providers_includes_nasa_ia_mixkit():
    names = [p.name for p in default_providers()]
    assert "nasa" in names
    assert "archiveorg" in names
    assert "mixkit" in names
    assert "pexels-browser" in names
    assert "pixabay-browser" in names
    # Sira: pexels-browser, pixabay-browser, mixkit, nasa, archiveorg, wikimedia
    assert names.index("pixabay-browser") < names.index("mixkit")
    assert names.index("mixkit") < names.index("nasa")
    assert names.index("nasa") < names.index("archiveorg")
    assert names.index("archiveorg") < names.index("wikimedia")
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


# ---------- Mixkit tests ----------

def test_mixkit_hosts():
    assert "assets.mixkit.co" in DOWNLOAD_HOSTS["mixkit"]
    assert "mixkit.co" in SOURCE_HOSTS["mixkit"]
    assert not valid_url("https://evil.com/v.mp4", DOWNLOAD_HOSTS["mixkit"])
    assert valid_url(
        "https://assets.mixkit.co/videos/9949/9949-720.mp4",
        DOWNLOAD_HOSTS["mixkit"],
    )


def test_stock_terms_mixkit_verified_free_license():
    terms = StockTerms(session=FakeSession())
    lic = terms.check("mixkit")
    assert lic.verified is True
    assert "Mixkit" in lic.name
    assert lic.attribution_required is False
    assert "no_standalone_redistribution" in lic.restrictions


def test_mixkit_slug():
    mk = MixkitProvider(session=FakeSession())
    assert mk._slug("Solar Flare!") == "solar-flare"
    assert mk._slug("cats & dogs") == "cats-dogs"
    assert mk._slug("OCEAN") == "ocean"


def test_mixkit_parse_category_page_picks_highest_resolution():
    html = '''
    <html><body>
      <a href="/free-stock-video/a-cute-cat-video-1779/" title="Cute cat video">Cute cat</a>
      <video><source src="https://assets.mixkit.co/videos/1779/1779-360.mp4"></video>
      <video><source src="https://assets.mixkit.co/videos/1779/1779-720.mp4"></video>
      <video><source src="https://assets.mixkit.co/videos/1779/1779-1080.mp4"></video>
      <a href="/free-stock-video/dogs-playing-222/">Dogs</a>
      <video><source src="https://assets.mixkit.co/videos/222/222-360.mp4"></video>
      <video><source src="https://assets.mixkit.co/videos/222/222-2160.mp4"></video> <!-- 4K premium -->
    </body></html>
    '''
    mk = MixkitProvider(session=FakeSession())
    items = mk._parse_category_page(html)
    assert len(items) == 2
    by_id = {it["id"]: it for it in items}
    # 1779: en yuksek free res 1080 secilmeli
    assert by_id["1779"]["resolution"] == 1080
    assert by_id["1779"]["download_url"].endswith("1779-1080.mp4")
    assert "Cute cat" in by_id["1779"]["title"]
    # 222: 2160 premium atlanip 360 secilmeli
    assert by_id["222"]["resolution"] == 360
    assert by_id["222"]["download_url"].endswith("222-360.mp4")


def test_mixkit_search_filters_head_failures():
    """HTTP 200 + 200 + mp4 content-type + size <64MB olani secmeli."""
    html = '''
    <html><body>
      <a href="/free-stock-video/cute-cat-100/" title="Cute cat 100">Cat 100</a>
      <video><source src="https://assets.mixkit.co/videos/100/100-720.mp4"></video>
      <a href="/free-stock-video/cute-cat-200/" title="Cute cat 200">Cat 200</a>
      <video><source src="https://assets.mixkit.co/videos/200/200-720.mp4"></video>
    </body></html>
    '''
    get_map = {"https://mixkit.co/free-stock-video/cat/": FakeResp(200, text=html)}
    head_map = {
        # ilk aday 200, video/mp4, 5MB
        "https://assets.mixkit.co/videos/100/100-720.mp4":
            FakeResp(200, headers={"content-type": "video/mp4", "content-length": str(5*1024*1024)}),
        # ikinci aday 403
        "https://assets.mixkit.co/videos/200/200-720.mp4": FakeResp(403),
    }
    sess = FakeSession(get_map=get_map, head_map=head_map)
    mk = MixkitProvider(session=sess)
    cands = mk.search("cat")
    assert len(cands) == 1
    assert cands[0].media_id == "100"
    assert cands[0].download_url.endswith("100-720.mp4")
    assert cands[0].license.verified is True


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
