#!/usr/bin/env python3
"""gemini_story_pw.py offline testleri — ag/cookie/Chromium istemez."""

import importlib.util
import json
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


class FindStoryTextTest(unittest.TestCase):
    """Ag yakalama kurtaricisi — sentetik batchexecute govdesiyle."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _load_mod()

    def _line(cls, payload) -> str:
        s = json.dumps(payload, ensure_ascii=False)
        return str(len(s)) + s + "\n"

    def test_yanit_metni_bulunur(self):
        m = self.mod
        story = 'İşte senaryo:\n```json\n{"topic":"x","script_text":"Merhaba dunya"}\n```'
        body = ")]}'\n\n" + self._line(["wrb.fr", None, None]) + \
               self._line(["wrb.fr", "x", story, None])
        found = m.find_story_text([body])
        self.assertIn("script_text", found)
        self.assertIn("Merhaba dunya", found)

    def test_isaretsiz_govde_bos(self):
        m = self.mod
        self.assertEqual(m.find_story_text([")]}'\n\n5[[1,2,3]]\n"]), "")

    def test_walk_strings_ic_ice(self):
        m = self.mod
        data = {"a": ["x", {"b": "y"}], "c": "z"}
        self.assertEqual(sorted(m._walk_strings(data)), ["x", "y", "z"])

    def test_en_uzun_aday_kazanir(self):
        m = self.mod
        kisa = 'x "script_text" y'
        uzun = 'uzun icerik {"script_text": "tam senaryo burada"} devam'
        body = self._line(["a", kisa]) + self._line(["a", uzun])
        found = m.find_story_text([body])
        self.assertEqual(found, uzun)


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
