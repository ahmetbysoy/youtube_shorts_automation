"""Faz 11 birim testleri: Viral metadata (CTA / kapak promptu / trend hashtag) ve cron kilidi."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import content_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADER_JS = PROJECT_ROOT / "youtube_studio_uploader.js"
DAILY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "daily_shorts.yml"
PRUNER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "hourly_pruner.yml"
PROBE_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "cron_probe.yml"


class TestFaz11ViralMetadata(unittest.TestCase):
    def _raw(self, **overrides) -> dict:
        raw = {
            "topic": "Tarih",
            "title": "Piramitlerden 7 Bin Yıl Daha Eski Tapınak: Göbeklitepe! #Shorts",
            "description": "Göbeklitepe sırrı #tarih #shorts",
            "hook": "Piramitlerden eski tapınak Türkiye'de!",
            "script_text": " ".join(["kelime"] * 65),
            "visual_keywords": ["gobeklitepe stone temple", "ancient mesopotamia"],
        }
        raw.update(overrides)
        return raw

    def test_prompt_requests_cta_thumbnail_and_hashtags(self) -> None:
        system_prompt, user_prompt = content_engine.build_llm_prompts("İlginç Bilgiler", [])
        self.assertIn("cta_line", system_prompt)
        self.assertIn("thumbnail_prompt", system_prompt)
        self.assertIn("viral_hashtags", system_prompt)
        self.assertIn("cta_line", user_prompt)
        self.assertIn("thumbnail_prompt", user_prompt)
        self.assertIn("viral_hashtags", user_prompt)
        # Prompt JSON şeması hâlâ geçerli olmalı
        self.assertIn('"script_text"', user_prompt)
        self.assertIn('"visual_keywords"', user_prompt)

    def test_scenario_gets_cta_thumbnail_prompt_and_three_hashtags(self) -> None:
        norm = content_engine.validate_and_normalize_scenario(self._raw(), "unit-test")
        self.assertTrue(norm["cta_line"])
        self.assertIn("abone", norm["cta_line"].lower() + "yorum")
        self.assertIn("9:16", norm["thumbnail_prompt"])
        self.assertEqual(len(norm["viral_hashtags"]), 3)
        for tag in norm["viral_hashtags"]:
            self.assertTrue(tag.startswith("#"))
            self.assertNotIn(" ", tag)

    def test_description_order_affiliate_cta_then_viral_cta_then_hashtags(self) -> None:
        norm = content_engine.validate_and_normalize_scenario(self._raw(), "unit-test")
        desc = norm["description"]
        self.assertTrue(desc.startswith(norm["affiliate_cta"]), "affiliate CTA en üstte olmalı")
        self.assertIn(norm["cta_line"], desc)
        self.assertTrue(desc.rstrip().endswith(" ".join(norm["viral_hashtags"])))
        # YouTube 3'ten fazla hashtag'i yok sayar -> aciklamada tam 3 hashtag olmali
        self.assertEqual(len(re.findall(r"#[0-9A-Za-zÇĞİÖŞÜçğıöşü_]+", desc)), 3)

    def test_hashtag_sanitizer_and_curated_lookup(self) -> None:
        self.assertEqual(content_engine.sanitize_hashtag("Göbeklitepe"), "#göbeklitepe")
        self.assertEqual(content_engine.sanitize_hashtag("#MARIANA"), "#mariana")
        self.assertEqual(content_engine.sanitize_hashtag("123"), "")
        curated = content_engine.lookup_curated_hashtags("Napolyon'un Tavşan Ordusuna Karşı Tuhaf Yenilgisi! #Shorts")
        self.assertEqual(curated[0], "#napolyon")

    def test_uploader_contains_thumbnail_pipeline(self) -> None:
        source = UPLOADER_JS.read_text(encoding="utf-8")
        self.assertIn("AI ile dikkat çekici kapak (thumbnail) oluşturuluyor ve yükleniyor", source)
        self.assertIn("Kapak resmi başarıyla yüklendi", source)
        self.assertIn("Kapak resmi yüklenemedi, YouTube otomatik seçim yapacak", source)
        self.assertIn("image.pollinations.ai", source)
        self.assertIn("ytcp-thumbnail-uploader input[type=\"file\"]", source)
        self.assertIn("buildFinalDescription", source)
        # Gunluk kota korumasi
        self.assertIn("detectDailyUploadLimit", source)
        self.assertIn("process.exit(42)", source)

    def test_uploader_javascript_is_syntactically_valid(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node bulunamadı")
        result = subprocess.run(
            [node, "--check", str(UPLOADER_JS)], capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_workflows_use_exact_cron_and_have_chain_backup(self) -> None:
        daily = DAILY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '0,15,30,45 * * * *'", daily)
        self.assertIn("permissions:", daily)
        self.assertIn("contents: write", daily)
        self.assertIn("actions: write", daily)
        self.assertIn("workflow_dispatch:", daily)
        # Cron kilidi kirma: zincir tetikleyicisi
        self.assertIn("cron-kick:", daily)
        self.assertIn("actions/workflows/${WORKFLOW}/dispatches", daily)
        self.assertIn("slot_epoch", daily)

        pruner = PRUNER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '0 * * * *'", pruner)
        self.assertIn("cron-kick:", pruner)

    def test_no_skip_ci_in_auto_commit_messages(self) -> None:
        """[skip ci] HEAD commit mesajinda zamanlayiciyi sessizce atlatir -> kullanilMAZ."""
        for wf in [DAILY_WORKFLOW, PRUNER_WORKFLOW, PROBE_WORKFLOW]:
            text = wf.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "git commit -m" in line:
                    self.assertNotIn("skip ci", line.lower(), f"{wf.name} içinde [skip ci] var")

    def test_probe_workflow_exists_for_scheduler_health(self) -> None:
        self.assertTrue(PROBE_WORKFLOW.exists())
        probe = PROBE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '*/5 * * * *'", probe)
        self.assertIn("PROBE OK", probe)


if __name__ == "__main__":
    unittest.main()
