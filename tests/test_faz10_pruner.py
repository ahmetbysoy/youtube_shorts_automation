"""Faz 10 birim testleri: Otonom "ölü ağırlık" temizleyici (Auto-Pruner) ve emniyet kilitleri."""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRUNER_JS = PROJECT_ROOT / "prune_low_performers.js"
PRUNER_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "hourly_pruner.yml"
PRUNER_NODE_TEST = PROJECT_ROOT / "tests" / "pruner_logic.test.js"


class TestFaz10AutoPruner(unittest.TestCase):
    def test_pruner_script_exists_and_targets_real_studio_dom(self) -> None:
        self.assertTrue(PRUNER_JS.exists(), "prune_low_performers.js bulunmalı")
        source = PRUNER_JS.read_text(encoding="utf-8")
        # Gerçek YouTube Studio DOM yapısı (canlı kanalda doğrulandı)
        self.assertIn("ytcp-video-row", source)
        self.assertIn('tp-yt-paper-item[test-id="delete"]', source)
        self.assertIn("#confirm-checkbox #checkbox", source)
        self.assertIn("#confirm-button", source)
        self.assertIn("tablecell-views", source)
        self.assertIn("tablecell-date", source)

    def test_safety_rails_and_thresholds(self) -> None:
        source = PRUNER_JS.read_text(encoding="utf-8")
        self.assertIn("PRUNE_MIN_VIEWS || 100", source)
        self.assertIn("PRUNE_MIN_AGE_MINUTES || 60", source)
        self.assertIn("PRUNE_MAX_DELETIONS || 10", source)
        self.assertIn("PRUNE_MIN_REMAINING || 1", source)
        self.assertIn("PRUNE_DRY_RUN", source)
        # Yaş çözümleme katmanları: RSS (kesin) + durum dosyası + göreli/mutlak tarih
        self.assertIn("feeds/videos.xml", source)
        self.assertIn("prune_state.json", source)

    def test_pruner_writes_report_and_state_files(self) -> None:
        source = PRUNER_JS.read_text(encoding="utf-8")
        self.assertIn("prune_report.json", source)
        self.assertIn("HEDEF TEPİT EDİLDİ".replace("TEPİT", "TESPİT"), source)
        self.assertIn("BAŞARILI:", source)
        self.assertIn("KORUNDU:", source)
        self.assertIn("TEMİZLİK TAMAMLANDI", source)

    def test_hourly_workflow_schedule_and_matrix(self) -> None:
        self.assertTrue(PRUNER_WORKFLOW.exists(), "hourly_pruner.yml bulunmalı")
        yml = PRUNER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("cron: '0 * * * *'", yml)
        self.assertIn('fromJSON(\'["1","2","3","4","5","6","7","8","9","10"]\')', yml)
        self.assertIn("fail-fast: false", yml)
        self.assertIn("pruner-studio-lock", yml)
        self.assertIn("cancel-in-progress: false", yml)
        self.assertIn("COOKIES_JSON_{0}", yml)
        self.assertIn("STORAGE_STATE_JSON_{0}", yml)
        self.assertIn("xvfb-run -a", yml)
        self.assertIn("node prune_low_performers.js", yml)

    def test_pruner_javascript_is_syntactically_valid(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node bulunamadı")
        result = subprocess.run(
            [node, "--check", str(PRUNER_JS)], capture_output=True, text=True, timeout=120
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pruner_node_logic_tests_pass(self) -> None:
        node = shutil.which("node")
        if not node:
            self.skipTest("node bulunamadı")
        result = subprocess.run(
            [node, str(PRUNER_NODE_TEST)], capture_output=True, text=True, timeout=180
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("test başarıyla geçti", result.stdout)


if __name__ == "__main__":
    unittest.main()
