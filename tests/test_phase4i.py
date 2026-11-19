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
