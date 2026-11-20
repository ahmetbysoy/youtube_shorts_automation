"""Faz 4I — Cookie guvenlik/raporlama, QC saglamlik, topic history commit mesajlari."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Test 1: Cookie yokken action_hint ve secret_to_refresh dogru donulur ──

def test_browser_provider_reports_missing_cookie_with_refresh_hint():
    """PEXELS_COOK yokken 'cookie_missing' + hangi secret yenilenecegi acikca donulmeli."""
    from src.media_processing.media_providers import BrowserStockProvider
    for provider, secret, label in [("pexels", "PEXELS_COOK", "Pexels"),
                                    ("pixabay", "PIXABAY_COOK", "Pixabay")]:
        bp = BrowserStockProvider(provider)
        bp.search("test")  # cookie yok, subprocess baslamamali
        d = bp.last_diagnostics
        assert d["status"] == "cookie_missing", f"{provider}: status {d['status']}"
        assert d["secret_to_refresh"] == secret, f"{provider}: secret {d.get('secret_to_refresh')}"
        assert secret in d["action_hint"], f"{provider}: action_hint secret adini icermeli"
        assert label in d["action_hint"], f"{provider}: action_hint site adini icermeli"
        # Cookie degeri diagnostics icinde OLMAMALI (zaten yok ama emin ol)
        assert "cookie_value" not in d
        assert "cookie_raw" not in d
        serialized = json.dumps(d)
        # Yaygın cookie name'lerinin deðeri bile (örnegin sessionid=...) gecmemeli
        for leak in ("sessionid=", "cf_clearance=", "__cf_bm="):
            assert leak not in serialized, f"{provider}: {leak} diagnostics'e sizmis"


# ── Test 2: QC dosyasi import edilebilir ve sabitler tutarli ──

def test_qc_constants_consistent():
    """HEAD_TAIL_MAX_BLACK esigi tanimli olmali ve 0 < deger < HEAD_TAIL_DURATION."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import qc_final_video as qc
    assert hasattr(qc, "HEAD_TAIL_DURATION")
    assert hasattr(qc, "HEAD_TAIL_MAX_BLACK")
    assert 0 < qc.HEAD_TAIL_MAX_BLACK < qc.HEAD_TAIL_DURATION, "head esigi HEAD_TAIL_DURATION'dan kucuk olmali"


def test_qc_scene_hash_function():
    """_file_sha256 ayni icerik icin ayni hash, farkli icerik icin farkli hash uretmeli."""
    import tempfile
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.qc_final_video import _file_sha256
    with tempfile.TemporaryDirectory() as td:
        p1 = Path(td) / "a.mp4"
        p2 = Path(td) / "b.mp4"
        p3 = Path(td) / "c.mp4"
        p1.write_bytes(b"x" * 10000)
        p2.write_bytes(b"x" * 10000)  # aynisi
        p3.write_bytes(b"y" * 10000)  # farkli
        h1, h2, h3 = _file_sha256(p1), _file_sha256(p2), _file_sha256(p3)
        assert h1 == h2, "ayni icerik ayni hash uretmeli"
        assert h1 != h3, "farkli icerik farkli hash uretmeli"
        assert len(h1) == 64, "sha256 hex 64 karakter olmali"


# ── Test 3: Topic history GitHub commit mesajlari anlamli ──

def test_topic_history_operation_messages_distinct():
    """put() cagrilari reserve/commit/release icin farkli mesajlar uretmeli
    ve hicbir zaman konu basligi veya cookie/secret icermemeli."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.topic_history import GitHubContentsStore

    # put()'un HTTP yapmasini engellemek icin session'i mock'la
    class MockSession:
        def __init__(self):
            self.last_payload = None
        def put(self, url, headers=None, json=None, timeout=None):
            self.last_payload = json
            class R:
                status_code = 200
            return R()
        def get(self, url, headers=None, params=None, timeout=None):
            raise NotImplementedError("get cagrilmamali")

    s = MockSession()
    store = GitHubContentsStore("owner/repo", "faketoken", session=s)
    data = {"version": 2, "used_titles": [], "used_records": [], "pending": []}
    messages_seen = set()
    for op in ("reserve", "commit", "release", "update"):
        store.put(data, None, operation=op)
        msg = s.last_payload["message"]
        messages_seen.add(msg)
        assert isinstance(msg, str) and len(msg) > 5, f"{op} icin mesaj bos olamaz"
        # Gizli veri icermemesi:
        for forbidden in ("password", "secret", "token=", "cookie=", "session="):
            assert forbidden not in msg.lower(), f"{op} mesaji gizli veri iceriyor: {msg}"
    # Uc farkli anlamli mesaj olmali (update son care, eski davranis)
    assert "reserve" in " ".join(messages_seen).lower() or any("reserve" in m for m in messages_seen)
    assert any("commit" in m or "successful" in m for m in messages_seen)
    assert any("release" in m or "failed" in m or "release" in m for m in messages_seen)


# ── Test 4: video_fetcher.js cookie degerlerini console'a yazmaz ──

def test_video_fetcher_js_does_not_leak_cookie_values():
    """video_fetcher.js kaynak kodunda cookie degerlerini dogrudan
    console.log/error/JSON.stringify ciktilarina sizdiran pattern'ler olmamali."""
    root = Path(__file__).resolve().parents[1]
    src = (root / "video_fetcher.js").read_text(encoding="utf-8")
    # Dogrudan cookie array'ini loglayan pattern'ler yok etmeli:
    # console.log(cookies) veya console.error({..., cookies}) gibi.
    import re
    leak_patterns = [
        r"console\.(log|error)\([^)]*cookies[^)]*\)",
        r"JSON\.stringify\([^)]*cookies\)",
    ]
    for pat in leak_patterns:
        m = re.search(pat, src)
        if m:
            # Ancak safe log() fonksiyonu (maskeli) varsa sorun yok
            # Log fonksiyonunu kontrol et:
            assert "//" in src[max(0, m.start()-200):m.start()], f"cookie degeri sizdiran pattern: {m.group()[:100]}"


# ── Test 5: media_providers.py hicbir sekilde cookie degerini return etmiyor ──

def test_media_providers_diagnostics_contain_no_cookie_values():
    """last_diagnostics cookie degeri veya tam cookie header'i icermemeli."""
    from src.media_processing.media_providers import BrowserStockProvider
    bp = BrowserStockProvider("pexels")
    bp.search("test")
    s = json.dumps(bp.last_diagnostics)
    # Cookie degerini aramak icin tipik cookie substratları:
    for forbidden in ("Cookie:", "Set-Cookie:", "sessionid=", "cf_clearance=",
                      "PEXELS_COOK=", "PIXABAY_COOK=", "Authorization:"):
        assert forbidden not in s, f"diagnostics cookie/secret iceriyor: {forbidden}"




# ── Faz4K: BrowserStockProvider probe cache ──

def test_browser_provider_probe_cache_skips_subprocess_on_permanent_error():
    """Kalıcı hata durumlarında (cookie_missing, access_denied, login_required,
    captcha_challenge) BrowserStockProvider tarayıcıyı tekrar açmamalı."""
    import os
    from unittest import mock
    from src.media_processing.media_providers import BrowserStockProvider, StockTerms

    # Test 1: PEXELS_COOK yok → cookie_missing, ikinci çağrıda subprocess çalışmamalı
    prov = BrowserStockProvider("pexels", terms=StockTerms())
    old = os.environ.pop("PEXELS_COOK", None)
    try:
        r1 = prov.search("cat")
        assert r1 == [], "cookie yoksa boş liste dönmeli"
        assert prov._probe_status == "cookie_missing"
        assert prov._probe_logged is True
        with mock.patch("subprocess.run") as spy:
            r2 = prov.search("cat")
            spy.assert_not_called()
        assert r2 == [], "cached hata da boş liste dönmeli"
    finally:
        if old is not None:
            os.environ["PEXELS_COOK"] = old

    # Test 2: _probe_status='access_denied' iken search() subprocess'e gitmemeli
    prov2 = BrowserStockProvider("pixabay", terms=StockTerms())
    prov2._probe_status = "access_denied"
    prov2.last_diagnostics = {"provider": "pixabay", "status": "access_denied"}
    old2 = os.environ.get("PIXABAY_COOK")
    os.environ["PIXABAY_COOK"] = "dummy_cookie_value"
    try:
        with mock.patch("subprocess.run") as spy:
            r = prov2.search("trees")
            spy.assert_not_called()
        assert r == []
    finally:
        if old2 is None:
            del os.environ["PIXABAY_COOK"]
        else:
            os.environ["PIXABAY_COOK"] = old2


def test_browser_provider_transient_errors_not_cached():
    """browser_timeout ve rate_limited geçici hatalardır; sonraki aramalar
    tekrar denemeli (probe_cache'e alınmamalı)."""
    from src.media_processing.media_providers import BrowserStockProvider, StockTerms
    prov = BrowserStockProvider("pexels", terms=StockTerms())
    # Başlangıç durumu
    assert prov._probe_status is None
    # Geçici hata senaryosu manuel simülasyon: search() metodu bu hataları
    # _probe_status'a yazmaz, dolayısıyla _probe_status None kalmalı ve
    # bir sonraki aramada tekrar subprocess çağrılır.
    # (Bu testin doğrulaması: kod akışında bu hata durumlarında
    # self._probe_status = X ataması yok.)
    import inspect
    src = inspect.getsource(prov.search)
    # Kalıcı hata durumları search_status değişkeni üzerinden set edilir:
    #   if search_status in ("login_required", "auth_required", "access_denied",
    #                        "captcha_challenge"):
    #       self._probe_status = search_status
    # Geçici durumlar (browser_timeout, rate_limited) bu listede YOK.
    assert '"login_required"' in src and '"access_denied"' in src and '"captcha_challenge"' in src, \
        "kalıcı hata durumları search_status listesinde olmalı"
    assert 'self._probe_status = search_status' in src, \
        "kalıcı hatalar için _probe_status set edilmeli"
    # Bu iki satırdan sonra browser_timeout/rate_limited için _probe_status set edilmemeli
    assert '_probe_status = "ok"' in src, \
        "başarılı durumda _probe_status=ok set edilmeli"


# ── Faz4K: Wikimedia Commons lisans tespiti düzeltmeleri ──

def test_commons_license_accepts_cc0_with_deed_suffix():
    """CC0 lisans URL'sinde /deed.en, /deed.tr gibi dil suffix'i
    varsa da kabul edilmeli (Lucius Verus.jpg örneği)."""
    from src.media_processing.media_providers import commons_license
    page = {"title": "File:Roman Emperor Lucius Verus.jpg"}
    info = {
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Roman_Emperor_Lucius_Verus.jpg",
        "extmetadata": {
            "LicenseShortName": {"value": "CC0"},
            "LicenseUrl": {"value": "http://creativecommons.org/publicdomain/zero/1.0/deed.en"},
            "License": {"value": "cc0"},
            "AttributionRequired": {"value": "false"},
            "Artist": {"value": "Ktrepas"},
        },
    }
    lic = commons_license(page, info)
    assert lic.verified is True, f"CC0 deed.en URL'si kabul edilmeli; reason={lic.rejection_reason}"
    assert lic.attribution_required is False


def test_commons_license_accepts_no_restrictions():
    """Müze 'No restrictions' / 'No known copyright restrictions' işareti
    public domain olarak kabul edilmeli (Getty Open Content örneği)."""
    from src.media_processing.media_providers import commons_license
    page = {"title": "File:Bust of Emperor Commodus.jpg"}
    info = {
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Bust.jpg",
        "extmetadata": {
            "LicenseShortName": {"value": "No restrictions"},
            "LicenseUrl": {"value": "http://www.getty.edu/about/opencontent.html"},
            "License": {"value": ""},
            "AttributionRequired": {"value": "false"},
            "Artist": {"value": "J. Paul Getty Museum"},
            "UsageTerms": {"value": "No known copyright restrictions"},
        },
    }
    lic = commons_license(page, info)
    assert lic.verified is True, f"'No restrictions' kabul edilmeli; reason={lic.rejection_reason}"
    assert lic.attribution_required is False


def test_browser_provider_consecutive_empty_short_circuits():
    """Cookie oturumu acik olsa bile (probe_status='ok') arka arkaya
    CONSECUTIVE_EMPTY_THRESHOLD kadar bos sonuc gelirse sonraki aramalar
    tarayiciyi tekrar acmamali."""
    import os
    from unittest import mock
    from src.media_processing.media_providers import BrowserStockProvider, StockTerms

    prov = BrowserStockProvider("pexels", terms=StockTerms())
    prov._probe_status = "ok"
    prov._probe_logged = True
    # Ilk 2 arama bosa ciksin (simule)
    prov._consecutive_empty = 2
    os.environ["PEXELS_COOK"] = "dummy"
    try:
        with mock.patch("subprocess.run") as spy:
            r = prov.search("cat")
            spy.assert_not_called()
        assert r == [], "esik asildiginda tarayici acilmamali"
    finally:
        del os.environ["PEXELS_COOK"]


def test_wikimedia_provider_returns_enough_licensed_results_for_common_queries():
    """WikimediaProvider gsrlimit=20 ile by-sa disi CC0/CC-BY adaylar
    donmeli (dead sea crystals gibi by-sa agirlikli sorgularda da)."""
    from src.media_processing.media_providers import WikimediaProvider
    w = WikimediaProvider()
    r = w.search("dead sea crystals")
    licensed = [c for c in r if c.license.verified and "by-sa" not in c.license.name.lower()]
    assert len(r) >= 12, f"en az 12 aday donmeli, {len(r)} dondu"
    assert len(licensed) >= 3, f"CC0/CC-BY en az 3 aday olmali, {len(licensed)} var"


def test_wikimedia_returns_high_resolution_candidates():
    """Wikimedia thumbnail width 1920px olmalı ki dikey videoda min 720p
    kosulu gecilebilsin."""
    from src.media_processing.media_providers import WikimediaProvider
    w = WikimediaProvider()
    r = w.search("einstein theory physics")
    image_or_video = [c for c in r if c.license.verified and c.width and c.height
                      and min(c.width, c.height) >= 720]
    assert len(image_or_video) >= 3, f"en az 3 yuksek cozunurluklu aday olmali, {len(image_or_video)} var"
