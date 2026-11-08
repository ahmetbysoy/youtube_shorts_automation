"""FAZ 12 (TOTAL DOMINATION) birim testleri: silahlandırılmış prompt, agresif kapak,
kron throttle ayarları, affiliate_hook sırası ve kanal hijyeni araçları."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADER_JS = PROJECT_ROOT / "youtube_studio_uploader.js"
HYGIENE_JS = PROJECT_ROOT / "scripts" / "channel_hygiene.js"
BANNER_PY = PROJECT_ROOT / "scripts" / "generate_banner.py"
FALLBACK_PY = PROJECT_ROOT / "scripts" / "generate_fallback_thumbnail.py"
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

    def test_uploader_logs_preview_with_verification_caveat(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("Studio önizlemesi değişti; yayın sonrası kalıcı kayıt ayrıca doğrulanmalı", source)
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
        self.assertIn("cron: '13 */2 * * *'", yml)

    def test_cancel_in_progress_true(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cancel-in-progress: true", yml)
        self.assertIn("contents: write", yml)
        self.assertIn("actions: write", yml)

    def test_chain_still_exists(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron-kick:", yml)
        self.assertIn("actions/workflows/${WORKFLOW}/dispatches", yml)

    def test_local_fallback_thumbnail_exists_and_is_1080x1920(self) -> None:
        """AI kapak servisi rate limit verirse yerel yedek kapak uretilmeli (run #52 kaniti)."""
        script = PROJECT_ROOT / "scripts" / "generate_fallback_thumbnail.py"
        self.assertTrue(script.exists(), "yerel yedek kapak scripti yok")
        src = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("generateLocalFallbackThumbnail", src)
        self.assertIn("generate_fallback_thumbnail.py", src)

        # Gercekten 1080x1920 uretebiliyor mu?
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "thumb.jpg"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--title",
                    "Test Basligi! #Shorts",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(out.exists())
            from PIL import Image

            with Image.open(out) as img:
                self.assertEqual(img.size, (1080, 1920))

    def test_slot_step_is_coprime_so_topics_rotate(self) -> None:
        """(slot * CARPAN) % len(pool) sabit kalinca ayni konu arka arkaya secilir."""
        sys.path.insert(0, str(PROJECT_ROOT))
        from content_engine import _coprime_step  # noqa: E402
        import math  # noqa: E402

        for size in (3, 5, 7, 10, 12, 20):
            step = _coprime_step(size)
            self.assertEqual(math.gcd(step, size), 1, f"step {step} ve {size} asal degil")
            slots = {(s * step) % size for s in range(size)}
            self.assertEqual(len(slots), size, f"boyut {size} icin tum konular kullanilmiyor")

        # Canli hata: len=3, carpim=3 -> hep 0 (ayni konu)
        old_slots = {(s * 3) % 3 for s in range(6)}
        self.assertEqual(len(old_slots), 1, "eski formul bu boyutta sabit kalir")
        new_slots = {(s * _coprime_step(3)) % 3 for s in range(6)}
        self.assertEqual(len(new_slots), 3, "yeni formul konulari dagitmali")

    def test_visibility_tab_transition_is_resilient(self) -> None:
        """Kapuk yuklemesinden sonra "İleri" pasif kalirsa gorusurluk sekmesine gecmeli."""
        src = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("PUBLIC_RADIO_SEL", src)
        self.assertIn("isEnabled()", src)
        # eski tek-seferlik 3 deneme yerine dongu + bekleme
        self.assertIn("for (let attempt = 0; attempt < 18; attempt++)", src)
        self.assertIn("kontroller sürüyor", src)

    def test_uploader_prevents_title_overwrite_and_dialog_self_close(self) -> None:
        """Hashtag dropdown odagi bozmamali (Run #550) ve ana yukleme diyalogu kapatilmamali (Run #549)."""
        src = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("hideSuggestionDropdowns", src)
        self.assertIn("document.execCommand('insertText', false, val)", src)
        self.assertIn("cleanCurrentTitle.length > 100", src)
        self.assertNotIn('#close-button, ytcp-button[id="cancel-button"]', src)

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


class TestForceLocalThumbnailLiveProof(unittest.TestCase):
    """Islah 11: rate-limit yolunun CANLI kaniti icin zorlanabilir yedek kapak dali."""

    def test_uploader_supports_force_local_thumbnail_flag(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("FORCE_LOCAL_THUMBNAIL", source)
        self.assertIn("forceLocalThumbnail", source)
        # Zorlanan modda AI kapak ATLANIR, dogrudan yerel yedek uretece gecilir
        self.assertIn("AI kapak atlandi, yerel yedek kapak kullanilacak", source)

    def test_workflow_exposes_force_local_thumbnail_input(self) -> None:
        yml = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("force_local_thumbnail:", yml)
        self.assertIn("FORCE_LOCAL_THUMBNAIL: ${{ inputs.force_local_thumbnail || '0' }}", yml)

    def test_fallback_generator_is_standalone_and_deterministic(self) -> None:
        if not shutil.which("python3"):
            self.skipTest("python3 yok")
        try:
            from PIL import Image  # noqa: F401
        except Exception:
            self.skipTest("Pillow yok")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fallback.png"
            result = subprocess.run(
                ["python3", str(FALLBACK_PY), "--title", "Test Basligi", "--out", str(out)],
                capture_output=True, text=True, timeout=180,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(out.exists())
            from PIL import Image
            with Image.open(out) as img:
                self.assertEqual(img.size, (1080, 1920))


if __name__ == "__main__":
    unittest.main()
