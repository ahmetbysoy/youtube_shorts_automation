#!/usr/bin/env python3
"""gemini_story_pw.py offline testleri — ag/cookie/Chromium istemez."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "gemini_story_pw.py"


def _load_mod():
    spec = importlib.util.spec_from_file_location("gemini_story_pw", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IsResponseStableTest(unittest.TestCase):
    """Yanit kararlilik saf fonksiyonu — streaming takibinin kalbi."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_mod()

    def test_kararli_uzun_yanit_dogru(self):
        m = self.mod
        uzun = "Bu yanit otuz karakterden uzun ve kararli bir ornek metindir"
        self.assertGreaterEqual(len(uzun), m.MIN_RESPONSE_CHARS)
        self.assertTrue(m.is_response_stable([uzun] * m.STABLE_POLLS))

    def test_kisa_yanit_kararli_sayilmaz(self):
        m = self.mod
        samples = ["kisa yanit"] * m.STABLE_POLLS  # 30 karakter alti
        self.assertFalse(m.is_response_stable(samples))

    def test_streaming_degisiyor_kararli_degil(self):
        m = self.mod
        samples = ["metin v1", "metin v1", "metin v1 uzun", "metin v1 uzun"]
        self.assertFalse(m.is_response_stable(samples))

    def test_ornek_yetersiz(self):
        m = self.mod
        self.assertFalse(m.is_response_stable(["ayni metin"] * (m.STABLE_POLLS - 1)))

    def test_bos_ornek_kararli_degil(self):
        m = self.mod
        self.assertFalse(m.is_response_stable([""] * m.STABLE_POLLS))


class CliFailPathTest(unittest.TestCase):
    """Cookie/ag olmadan CLI hatayi temiz vermeli (exit non-zero + STORY_FAIL)."""

    def test_eksik_prompt_dosyasi(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--prompt-file", "/tmp/gemini_story_pw_olmayan_prompt.txt",
             "--out", "/tmp/gemini_story_pw_test_out.txt"],
            capture_output=True, text=True, timeout=60,
        )
        self.assertNotEqual(r.returncode, 0)
        combined = (r.stdout or "") + (r.stderr or "")
        self.assertIn("STORY_FAIL", combined)

    def test_probe_modul_aktarimi(self):
        """gemini_web_text_probe yeni transport yardimcilarini taniyor mu?"""
        sys.path.insert(0, str(REPO))
        try:
            from scripts.gemini_web_text_probe import (  # noqa: F401
                _pw_text_generate,
                _env_float,
            )
        finally:
            sys.path.pop(0)
        self.assertTrue(callable(_pw_text_generate))


if __name__ == "__main__":
    unittest.main()
