"""FAZ 12 (TOTAL DOMINATION) birim testleri: silahlandırılmış prompt, agresif kapak,
kron throttle ayarları, affiliate_hook sırası ve kanal hijyeni araçları."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADER_JS = PROJECT_ROOT / "youtube_studio_uploader.js"
HYGIENE_JS = PROJECT_ROOT / "scripts" / "channel_hygiene.js"
BANNER_PY = PROJECT_ROOT / "scripts" / "generate_banner.py"
DAILY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "daily_shorts.yml"


def load_content_engine():
    spec = importlib.util.spec_from_file_location("ce_faz12", PROJECT_ROOT / "content_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFaz12WeaponizedPrompt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ce = load_content_engine()

    def test_system_prompt_is_weaponized(self) -> None:
        system_prompt, _ = self.ce.build_llm_prompts("İlginç Bilgiler", [])
        self.assertIn("algoritmasını hackleyen", system_prompt)
        self.assertIn("acımasız baş stratejistsin", system_prompt)
        self.assertIn("scroll stop", system_prompt)
        self.assertIn("retention", system_prompt)
        self.assertIn("ZORLAMAK", system_prompt)
        # Kapak promptu icin zorunlu gorsel dili
        self.assertIn("YouTube Shorts thumbnail, vertical 9:16, hyper-dramatic lighting", system_prompt)
        self.assertIn("glowing elements", system_prompt)
        self.assertIn("8k resolution", system_prompt)
        # 60-80 kelime kurali
        self.assertIn("60-80 kelime", system_prompt)

    def test_user_prompt_schema_has_all_required_fields(self) -> None:
        _, user_prompt = self.ce.build_llm_prompts("Tarih", [])
        for field in (
            "title", "hook", "script_text", "cta_line", "thumbnail_prompt",
            "viral_hashtags", "affiliate_hook", "visual_keywords", "description",
        ):
            self.assertIn(f'"{field}"', user_prompt, f"{field} şemada yok")

    def test_normalized_scenario_keeps_affiliate_hook_first(self) -> None:
        raw = {
            "topic": "Bilim",
            "title": "Test Başlık #Shorts",
            "description": "Gövde metni",
            "hook": "Kanca?",
            "script_text": " ".join(["kelime"] * 65),
            "visual_keywords": ["a", "b"],
            "cta_line": "Yorumlara yaz!",
            "affiliate_hook": "🔗 Şunu incele: [LINK]",
            "viral_hashtags": ["#x", "#y", "#z"],
        }
        norm = self.ce.validate_and_normalize_scenario(raw, "unit-test")
        self.assertTrue(norm["affiliate_hook"].startswith("🔗"))
        self.assertNotIn("[LINK]", norm["affiliate_hook"])
        self.assertTrue(norm["description"].startswith(norm["affiliate_hook"]))
        # Sira: affiliate -> CTA -> govde -> hashtag
        desc = norm["description"]
        self.assertLess(desc.index(norm["affiliate_hook"]), desc.index(norm["cta_line"]))
        self.assertLess(desc.index(norm["cta_line"]), desc.index("Gövde metni"))
        self.assertTrue(desc.rstrip().endswith("#x #y #z"))

    def test_description_has_exactly_three_hashtags(self) -> None:
        raw = {
            "topic": "Tarih",
            "title": "Test #Shorts",
            "description": "Gövde #tarih #shorts",
            "script_text": " ".join(["kelime"] * 65),
            "visual_keywords": ["a"],
            "cta_line": "Yorumlara yaz!",
            "viral_hashtags": ["#x", "#y", "#z"],
        }
        norm = self.ce.validate_and_normalize_scenario(raw, "unit-test")
        tags = re.findall(r"#[0-9A-Za-zÇĞİÖŞÜçğıöşü_]+", norm["description"])
        self.assertEqual(len(tags), 3, tags)


class TestFaz12AggressiveThumbnail(unittest.TestCase):
    def test_uploader_has_weaponized_style_suffix(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("STYLE_SUFFIX", source)
        for phrase in (
            "YouTube Shorts thumbnail",
            "vertical 9:16",
            "hyper-dramatic lighting",
            "glowing arrows",
            "shocked expression",
            "unreal engine 5 render",
            "dramatic shadows",
        ):
            self.assertIn(phrase, source, phrase)

    def test_uploader_logs_required_success_line(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("[+] KAPAK RESMİ BAŞARIYLA YÜKLENDİ VE KAYDEDİLDİ!", source)
        self.assertIn("SİLAHLANDIRILMIŞ AI KAPAK (THUMBNAIL) ÜRETİLİYOR VE YÜKLENİYOR", source)

    def test_uploader_keeps_proven_selectors_and_ffmpeg(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("ytcp-thumbnail-uploader input[type=\"file\"]", source)
        self.assertIn("setInputFiles", source)
        self.assertIn("filechooser", source)  # yedek yol
        self.assertIn("scale=1080:1920", source)

    def test_uploader_javascript_is_valid(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node yok")
        for script in (UPLOADER_JS, HYGIENE_JS):
            result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)


class TestFaz12CronThrottle(unittest.TestCase):
    def test_cron_uses_non_peak_minutes(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '0,13,27,41,55 * * * *'", yml)

    def test_cancel_in_progress_true(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cancel-in-progress: true", yml)
        self.assertIn("contents: write", yml)
        self.assertIn("actions: write", yml)

    def test_chain_still_exists(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron-kick:", yml)
        self.assertIn("actions/workflows/${WORKFLOW}/dispatches", yml)

    def test_chain_runs_do_not_cancel_active_publish(self) -> None:
        """Zincir koşusu AYRI concurrency grubunda olmali; aksi halde yayin yarida kesiliyor."""
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("inputs.chain", yml)
        self.assertIn('chain\\\":\\\"1', yml)
        # Studio oturum kilidi
        self.assertIn("studio-upload-lock", yml)


class TestFaz12ChannelHygiene(unittest.TestCase):
    def test_hygiene_script_exists_and_is_safe(self) -> None:
        source = HYGIENE_JS.read_text(encoding="utf-8")
        self.assertIn("uploadBanner", source)
        self.assertIn("updateAbout", source)
        self.assertIn("pinComment", source)
        self.assertIn("Sabitle", source)
        # Canli DOM ile dogrulanmis seciciler
        self.assertIn("ytcp-banner-upload input#file-selector", source)
        self.assertIn("#description-textbox", source)
        self.assertIn("ytd-comment-simplebox-renderer #placeholder-area", source)
        self.assertIn("ytd-comment-view-model ytd-menu-renderer button#button", source)
        self.assertIn("/editing/profile", source)
        # Hicbir hata pipeline'i bozmamali
        self.assertIn("process.exit(0)", source)

    def test_banner_generator_creates_valid_png(self) -> None:
        if not shutil.which("python3"):
            self.skipTest("python3 yok")
        try:
            from PIL import Image  # noqa: F401
        except Exception:
            self.skipTest("Pillow yok")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "banner.png"
            result = subprocess.run(
                ["python3", str(BANNER_PY), "--out", str(out)],
                capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())
            from PIL import Image
            with Image.open(out) as img:
                self.assertEqual(img.size, (2560, 1440))

    def test_workflow_runs_hygiene_step(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Kanal Hijyeni (Faz 12.5)", yml)
        self.assertIn("scripts/channel_hygiene.js", yml)
        self.assertIn("scripts/generate_banner.py", yml)


if __name__ == "__main__":
    unittest.main()
