"""Faz 4D — Cookie izolasyonu ve guvenlik testleri.

Bu testler hicbir gercek ag cagrisi yapmaz, cookie parse/filtreleme
mantigini dogrudan Node'dan (video_fetcher.js ic fonksiyonlari) test eder.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = "node"


def _run_node(js: str) -> str:
    """Node'a verilen JS string'ini eval edip stdout'unu dondurur."""
    # video_fetcher.js'i eval icin load et; icindeki main() otomatik calismasin diye
    # process.argv'yi bos bir script gibi ayarlayip, module'u "require" ederek
    # fonksiyonlari cagiriyoruz. Ama video_fetcher.js en ustte main() cagirmiyor
    # (sadece `main().catch(...)` module-sonunda); bunu require edersek calisir.
    # Ancak require otomatik olarak main() calistiracagi icin --eval kullanip
    # ic fonksiyonlari dogrudan cagiriyoruz.
    full = """
    const path = require('path');
    // process.argv'yi normal "node" gibi ayarla ki parseArgs patlamasin
    process.argv = ['node','eval'];
    const vf = require(%s);
    // vf modulu disariya fonksiyon acmiyor; onun yerine fonksiyonlari yeniden
    // tanimlamak yerine JS kodunu eval edip loadCookies/normalizeCookie
    // fonksiyonlarini tekrar icecegiz. Asagidaki kod dogrudan JS.
    """ % json.dumps(str(ROOT / 'video_fetcher.js'))
    # Daha basit yol: ayri bir JS test harness'i yaz.
    raise NotImplementedError


@pytest.fixture
def cookie_harness(tmp_path):
    """Node harness scripti yazip calistirmaya yardimci olur.

    video_fetcher.js'i gecici bir dosyaya kopyalayip sonuna module.exports
    ekleyerek Node'un require() ile ice aktarilabilir hale getirir; ana
    main() cagrisini kaldirir ve test edilmek istenen fonksiyonlari disari acar.
    """
    harness = tmp_path / "harness.js"
    import re
    src = (ROOT / "video_fetcher.js").read_text("utf8")
    # Playwright'i require eden satiri yoruma al (network testi yapmiyoruz);
    # bu sayede node_modules/playwright yuklu olmasa bile cookie/URL fonksiyonlari
    # test edilebilir.
    src = re.sub(r'^const\s*\{\s*chromium\s*\}\s*=\s*require\([^)]+\);',
                 '// { chromium } = require("playwright"); // TESTTE DEVRE DIŞI',
                 src, flags=re.MULTILINE)
    # child_process.execFileSync de ffprobe/ffmpeg cagiriyor; onu da yoruma al
    src = re.sub(r'^const\s*\{[^\n]*execFileSync[^\n]*\}\s*=\s*require\([^)]+\);',
                 '// child_process require devre dışı (test)', src, flags=re.MULTILINE)
    # main().catch(e => { ... }); blogunu regex ile cikart
    src = re.sub(r"\nmain\(\)\.catch\(e\s*=>\s*\{[^}]*\n\s*\}\);", "\n", src, flags=re.DOTALL)
    src += (
        "\nmodule.exports = { "
        "loadCookies, normalizeCookie, parseCookieString, parseCookiesFromJson, "
        "validHttpsUrl, ALLOWED_DOWNLOAD_HOSTS, ALLOWED_SOURCE_HOSTS, parseArgs"
        " };\n"
    )
    harness.write_text(src, "utf8")

    def call(fn, *args):
        code = (
            "const m = require(" + json.dumps(str(harness)) + ");\n"
            "const r = m['" + fn + "'](...arguments_raw);\n"
            "process.stdout.write(JSON.stringify(r));\n"
        )
        # Node -e tek bir string script alir; arguments_raw argumanini
        # process.argv gecerek iletmek yerine dogrudan JS literal olarak gom.
        args_js = json.dumps(list(args))
        code = (
            "const m = require(" + json.dumps(str(harness)) + ");\n"
            "const args = " + args_js + ";\n"
            "const r = m['" + fn + "'].apply(null, args);\n"
            "process.stdout.write(JSON.stringify(r));\n"
        )
        # NODE_PATH'i repo node_modules'una ayarla ki playwright'u bulabilsin
        env = os.environ.copy()
        env["NODE_PATH"] = str(ROOT / "node_modules")
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=15, env=env)
        assert r.returncode == 0, "node hatasi: " + r.stderr[:500]
        return json.loads(r.stdout) if r.stdout.strip() else None

    return call


class TestCookieNormalization:
    def test_normalize_basic(self, cookie_harness):
        c = cookie_harness("normalizeCookie",
            {"name": "session", "value": "abc123"}, ".pexels.com")
        assert c is not None
        assert c["name"] == "session"
        assert c["value"] == "abc123"
        assert c["domain"] == ".pexels.com"
        assert c["path"] == "/"
        assert c["sameSite"] in {"Strict", "Lax", "None"}

    def test_normalize_rejects_missing_name(self, cookie_harness):
        assert cookie_harness("normalizeCookie", {"value": "x"}, ".pexels.com") is None

    def test_normalize_rejects_missing_value(self, cookie_harness):
        assert cookie_harness("normalizeCookie", {"name": "x"}, ".pexels.com") is None

    def test_domain_prefix_added(self, cookie_harness):
        c = cookie_harness("normalizeCookie",
            {"name": "x", "value": "y", "domain": "pexels.com"}, ".pexels.com")
        assert c["domain"] == ".pexels.com"


class TestCookieParsing:
    def test_kv_string_parsing(self, cookie_harness):
        cookies = cookie_harness("parseCookieString", "a=b; c=d", ".pexels.com")
        assert isinstance(cookies, list)
        assert len(cookies) == 2
        names = {c["name"] for c in cookies}
        assert names == {"a", "c"}
        for c in cookies:
            assert c["domain"] == ".pexels.com"

    def test_json_array_parsing(self, cookie_harness):
        raw = json.dumps([{"name": "uid", "value": "xyz", "domain": ".pexels.com"}])
        cookies = cookie_harness("parseCookiesFromJson", raw, ".pexels.com")
        assert len(cookies) == 1
        assert cookies[0]["name"] == "uid"
        assert cookies[0]["domain"] == ".pexels.com"

    def test_storage_state_format(self, cookie_harness):
        raw = json.dumps({"cookies": [{"name": "s", "value": "v", "domain": ".pixabay.com"}]})
        cookies = cookie_harness("parseCookiesFromJson", raw, ".pixabay.com")
        assert len(cookies) == 1
        assert cookies[0]["domain"] == ".pixabay.com"


class TestDomainIsolation:
    def test_loadCookies_filters_wrong_domain(self, cookie_harness):
        # YouTube cookie'si pexels domain filtresinden gecmemeli
        raw = json.dumps([
            {"name": "yt", "value": "youtube-cookie", "domain": ".youtube.com"},
            {"name": "ps", "value": "pexels-cookie", "domain": ".pexels.com"},
            {"name": "google", "value": "google-cookie", "domain": ".google.com"},
        ])
        cookies = cookie_harness("loadCookies", raw, ".pexels.com")
        assert len(cookies) == 1
        assert cookies[0]["name"] == "ps"
        assert cookies[0]["domain"] == ".pexels.com"

    def test_loadCookies_filters_pixabay_from_pexels(self, cookie_harness):
        raw = json.dumps([
            {"name": "px", "value": "pixabay-cookie", "domain": ".pixabay.com"},
            {"name": "ps", "value": "pexels-cookie", "domain": ".pexels.com"},
        ])
        # Pexels istendiginde pixabay cookie'si elenmeli
        pex = cookie_harness("loadCookies", raw, ".pexels.com")
        assert all(c["domain"].endswith(".pexels.com") for c in pex)
        assert len(pex) == 1 and pex[0]["name"] == "ps"
        # Pixabay istendiginde de pexels elenmeli
        pix = cookie_harness("loadCookies", raw, ".pixabay.com")
        assert all(c["domain"].endswith(".pixabay.com") for c in pix)
        assert len(pix) == 1 and pix[0]["name"] == "px"

    def test_loadCookies_deduplicates(self, cookie_harness):
        raw = json.dumps([
            {"name": "x", "value": "v1", "domain": ".pexels.com", "path": "/"},
            {"name": "x", "value": "v2", "domain": ".pexels.com", "path": "/"},
        ])
        cookies = cookie_harness("loadCookies", raw, ".pexels.com")
        assert len(cookies) == 1
        assert cookies[0]["value"] == "v2"  # son gecerli olan kazansin

    def test_loadCookies_empty_when_no_cookie(self, cookie_harness):
        assert cookie_harness("loadCookies", "", ".pexels.com") == []
        assert cookie_harness("loadCookies", None, ".pexels.com") == []


class TestUrlValidation:
    def test_valid_pexels_hosts(self, cookie_harness):
        assert cookie_harness("validHttpsUrl", "https://videos.pexels.com/x.mp4",
                              ["videos.pexels.com"]) is True
        assert cookie_harness("validHttpsUrl", "https://cdn.pixabay.com/v.mp4",
                              ["cdn.pixabay.com"]) is True

    def test_reject_http(self, cookie_harness):
        assert cookie_harness("validHttpsUrl", "http://videos.pexels.com/x.mp4",
                              ["videos.pexels.com"]) is False

    def test_reject_untrusted_host(self, cookie_harness):
        assert cookie_harness("validHttpsUrl", "https://evil.com/x.mp4",
                              ["videos.pexels.com"]) is False

    def test_reject_auth_url(self, cookie_harness):
        assert cookie_harness("validHttpsUrl", "https://user:pass@videos.pexels.com/x.mp4",
                              ["videos.pexels.com"]) is False


class TestCliArgs:
    def test_metadata_flag(self, cookie_harness):
        # parseArgs dogrudan export edilmedi, ama CLI testi yapmak icin
        # Node sureci baslatip --metadata ile --provider'in taninip taninmadigina bak
        # (gercek ag cagrisi yapmadan, cookie yokken hizli hata vermesini bekleriz)
        r = subprocess.run(
            ["node", str(ROOT / "video_fetcher.js"), "kedi", "/tmp/out.mp4",
             "--metadata", "--provider", "pexels"],
            capture_output=True, text=True, timeout=15,
            env={k: v for k, v in os.environ.items() if k in {"PATH","HOME","TMPDIR","TMP","TEMP","LANG"}}
            # PEXELS_COOK yok => cookie_missing
        )
        # exit 1 donmeli (cookie yok)
        assert r.returncode == 1
        # Stdout JSON olmali (candidates + diagnostics)
        # Stderr cookie degeri icermemeli (eger PEXELS_COOK bos ise zaten bir sey cikmaz)
        assert "cookie_missing" in (r.stderr + r.stdout) or len(r.stdout) == 0
