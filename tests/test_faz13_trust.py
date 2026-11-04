"""FAZ 13 testleri: aciklama guvenligi (CTA), kaynak satiri, iddia/rakam
dogrulama ve kaynak haritasi.

NEDEN:
  Kanal denetimi (2026-11-04) iki kritik guven sorunu gosterdi:
   1) "Bu teleskobu incele / Bu kitabı oku" metinleri ABONE LINKINE bagliydi.
   2) Aciklamalarda kaynak yoktu; bazi rakamlar inflatedti (nötron yıldizi
      "6 milyar ton" -> NASA "yaklasik 1 milyar ton").
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHANNEL_URL = "https://www.youtube.com/@mentansiytas?sub_confirmation=1"


def load_content_engine():
    spec = importlib.util.spec_from_file_location("ce_faz13", PROJECT_ROOT / "content_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFaz13CtaGuvenligi(unittest.TestCase):
    """Denetim bulgusu 1: abone linki urun gibi sunulmaz."""

    def setUp(self) -> None:
        self.ce = load_content_engine()

    def test_channel_link_produces_honest_cta(self) -> None:
        url, cta = self.ce.resolve_affiliate_offer("Bilim", "Venüs testi", "")
        self.assertEqual(url, CHANNEL_URL)
        self.assertIn("Benzer videolar için abone ol", cta)
        self.assertNotIn("teleskop", cta.lower())
        self.assertNotIn("kitap", cta.lower())
        self.assertNotIn("bilim seti", cta.lower())

    def test_real_product_link_keeps_product_cta_and_disclosure(self) -> None:
        import os

        os.environ["AFFILIATE_URL_SPACE"] = "https://ornek-magaza.com/teleskop"
        try:
            url, cta = self.ce.resolve_affiliate_offer("Uzay", "Teleskop testi", "uzay")
            self.assertIn("teleskop", cta.lower())
            self.assertIn("affiliate", cta.lower())
            self.assertIn("https://ornek-magaza.com/teleskop", cta)
        finally:
            os.environ.pop("AFFILIATE_URL_SPACE", None)

    def test_product_claim_with_channel_link_is_sanitized(self) -> None:
        for claim in (
            "Bu teleskobu incele: " + CHANNEL_URL,
            "Bu kitabı oku: " + CHANNEL_URL,
            "Bu bilim setini incele: " + CHANNEL_URL,
            "Satın al: " + CHANNEL_URL,
        ):
            hook, notes = self.ce.sanitize_affiliate_hook(claim, CHANNEL_URL)
            self.assertIn("urun_iddiasi", notes, claim)
            self.assertIn("Benzer videolar için abone ol", hook)
            self.assertNotIn("teleskop", hook.lower())
            self.assertNotIn("kitabı", hook.lower())

    def test_hallucinated_link_is_replaced(self) -> None:
        hook, notes = self.ce.sanitize_affiliate_hook(
            "Şu harika teleskoba bak: https://www.amazon.com.tr/xyz", CHANNEL_URL
        )
        self.assertIn("uydurma_link", notes)
        self.assertNotIn("amazon", hook.lower())
        self.assertIn(CHANNEL_URL, hook)

    def test_honest_hook_is_untouched(self) -> None:
        hook, notes = self.ce.sanitize_affiliate_hook(
            "Benzer videolar için abone ol: " + CHANNEL_URL, CHANNEL_URL
        )
        self.assertEqual(notes, "")
        self.assertIn("Benzer videolar için abone ol", hook)


class TestFaz13KaynakSatiri(unittest.TestCase):
    """Denetim bulgusu 9: her aciklamada dogrulanabilir kaynak."""

    def setUp(self) -> None:
        self.ce = load_content_engine()

    def test_every_fallback_scenario_has_a_verified_source(self) -> None:
        for scenario in self.ce.FALLBACK_SCENARIOS:
            self.assertTrue(scenario.get("source"), scenario["title"])
            self.assertIn("http", scenario["source"], scenario["title"])

    def test_knowledge_sources_are_unique_and_url_shaped(self) -> None:
        seen = set()
        for key, value in self.ce.KNOWLEDGE_SOURCES.items():
            self.assertNotIn(key, seen)
            seen.add(key)
            self.assertIn("http", value, key)
            self.assertIn("—", value, key)  # kurum + link ayrimi

    def test_source_line_format(self) -> None:
        line = self.ce.build_source_line("NASA — https://svs.gsfc.nasa.gov/11260/", "Bilim", "x")
        self.assertEqual(line, "Kaynak: NASA — https://svs.gsfc.nasa.gov/11260/")

    def test_source_matched_by_topic_keywords(self) -> None:
        line = self.ce.build_source_line(
            "", "Bilim", "Bir Çay Kaşığı Nötron Yıldızı 1 Milyar Ton Çeker! #Shorts"
        )
        self.assertIn("NASA", line)
        self.assertIn("svs.gsfc.nasa.gov", line)

    def test_description_contains_source_line(self) -> None:
        item = next(
            s for s in self.ce.FALLBACK_SCENARIOS if "Nötron Yıldızı" in s["title"]
        )
        scenario = self.ce.validate_and_normalize_scenario(dict(item), "test")
        self.assertIn("Kaynak: NASA", scenario["description"])
        # Kaynak satiri hashtag'ten ONCE gelir
        self.assertLess(
            scenario["description"].index("Kaynak:"),
            scenario["description"].rindex("#"),
        )
        # Urun iddiasi icermeyen durust CTA
        self.assertIn("Benzer videolar için abone ol", scenario["description"])
        self.assertNotIn("Bu teleskobu incele", scenario["description"])


class TestFaz13IddiaDogrulama(unittest.TestCase):
    """Denetim bulgusu 3: rakam/iddia dogrulama."""

    def setUp(self) -> None:
        self.ce = load_content_engine()
        self.by_title = {s["title"]: s for s in self.ce.FALLBACK_SCENARIOS}

    def test_neutron_star_ton_amount_matches_nasa(self) -> None:
        item = next(
            s for s in self.ce.FALLBACK_SCENARIOS if "Nötron Yıldızı" in s["title"]
        )
        self.assertIn("1 Milyar Ton", item["title"])
        self.assertNotIn("6 Milyar Ton", item["title"])
        self.assertNotIn("altı milyar ton", item["script_text"])
        self.assertIn("bir milyar ton", item["script_text"])
        self.assertIn("NASA", item["source"])
        # Olcu tutarliligi: metinde tek bir "cay kasigi" olcumu
        self.assertNotIn("küp şeker", item["script_text"])

    def test_jellyfish_is_not_claimed_physically_immortal(self) -> None:
        item = next(s for s in self.ce.FALLBACK_SCENARIOS if "Denizanası" in s["title"])
        self.assertIn("Fiziksel olarak ölümsüz değildir", item["script_text"])
        self.assertNotIn("sonsuza kadar", item["script_text"])
        self.assertIn("doğrulanmış bir tedavi yok", item["script_text"])

    def test_emu_war_is_not_called_an_official_war(self) -> None:
        item = next(s for s in self.ce.FALLBACK_SCENARIOS if "Emu" in s["title"])
        self.assertIn("resmî bir savaş değildi", item["script_text"])
        self.assertNotIn("devekuşu", item["title"].lower())

    def test_gobeklitepe_date_matches_unesco(self) -> None:
        item = next(s for s in self.ce.FALLBACK_SCENARIOS if "Göbeklitepe" in s["title"])
        self.assertIn("MÖ 9600–8200", item["script_text"])
        self.assertNotIn("on iki bin yıl", item["script_text"])
        self.assertIn("UNESCO", item["source"])

    def test_antikythera_claim_is_sourced(self) -> None:
        item = next(s for s in self.ce.FALLBACK_SCENARIOS if "Antikythera" in s["title"])
        self.assertIn("Smithsonian", item["script_text"])
        self.assertNotIn("bin dört yüz yıl sonra", item["script_text"])

    def test_napoleon_rabbit_count_is_not_overprecise(self) -> None:
        item = next(s for s in self.ce.FALLBACK_SCENARIOS if "Napolyon" in s["title"])
        self.assertIn("binlerce evcil tavşan", item["script_text"])
        self.assertNotIn("üç bin evcil tavşan", item["script_text"])


class TestFaz13ThumbnailSubject(unittest.TestCase):
    """Denetim bulgusu 2: kapakta konu nesnesi gorunur (bitis karti degil)."""

    FALLBACK_PY = PROJECT_ROOT / "scripts" / "generate_fallback_thumbnail.py"

    def _make_test_video(self, tmp: Path) -> Path:
        import shutil
        import subprocess

        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg yok")
        video = tmp / "clip.mp4"
        proc = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=360x640:d=4",
             "-pix_fmt", "yuv420p", str(video)],
            capture_output=True, timeout=180,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode()[-400:])
        return video

    def _run_generator(self, out: Path, video: Path | None = None) -> str:
        import subprocess

        cmd = ["python3", str(self.FALLBACK_PY), "--title", "Konu Testi",
               "--out", str(out), "--topic", "Bilim"]
        if video is not None:
            cmd += ["--video", str(video)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        return proc.stdout

    def test_fallback_uses_video_frame_as_subject(self) -> None:
        import tempfile

        from PIL import Image, ImageStat

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            video = self._make_test_video(tmp)
            with_video = tmp / "with_video.jpg"
            log = self._run_generator(with_video, video)
            self.assertIn("konu kareli", log)

            text_only = tmp / "text_only.jpg"
            self._run_generator(text_only, None)

            with Image.open(with_video) as img:
                self.assertEqual(img.size, (1080, 1920))
                mean_video = ImageStat.Stat(img.convert("RGB")).mean
            with Image.open(text_only) as img:
                mean_card = ImageStat.Stat(img.convert("RGB")).mean
            # Yesil video karesi -> kapakta yesil bilesen belirgin sekilde yuksek olmali
            self.assertGreater(mean_video[1], mean_card[1] + 20)

    def test_generator_without_video_falls_back_to_text_card(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "card.jpg"
            log = self._run_generator(out, None)
            self.assertIn("metin karti", log)
            self.assertTrue(out.exists())

    def test_uploader_passes_video_and_topic_to_generator(self) -> None:
        source = (PROJECT_ROOT / "youtube_studio_uploader.js").read_text(encoding="utf-8")
        self.assertIn("'--video'", source)
        self.assertIn("'--topic'", source)
        self.assertIn("generateLocalFallbackThumbnail(title, readScenarioField(scriptData, 'topic'", source)

    def test_ai_thumbnail_prompt_requires_subject_in_frame(self) -> None:
        source = (PROJECT_ROOT / "youtube_studio_uploader.js").read_text(encoding="utf-8")
        self.assertIn("single clear subject filling the frame", source)
        self.assertIn("no text, no letters, no logo, no end card", source)

        ce = load_content_engine()
        prompt = ce.build_thumbnail_prompt("Bilim", "Test", ["neutron star"])
        self.assertIn("fills the frame", prompt)
        self.assertIn("no end card", prompt)


if __name__ == "__main__":
    unittest.main()
