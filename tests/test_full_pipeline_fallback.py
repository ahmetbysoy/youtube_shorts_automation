"""Tam uçtan uca test: content_engine fallback modu (Force Fallback).

run_content_pipeline(force_fallback=True) çağrılır ve şu çıktılar doğrulanır:
  - script.txt (saf senaryo metni)
  - voiceover.mp3 (ses dosyası, edge-tts)
  - voiceover.srt (altyazı)
  - script.json (zengin meta paketi)
  - .used_topics.json güncellemesi (başlık eklendi, 25 kayıt sınırı)
"""

import json
import sys
import unittest
from pathlib import Path

# Fallback hattı gerçek kurulu bağımlılıklarla sınanır. Modül seviyesinde
# sys.modules mock'u kullanmak diğer testlerin requests import'unu bozabilir.
sys.path.insert(0, "/home/user/yts")

from content_engine import (  # noqa: E402
    HISTORY_FILE,
    load_recent_titles,
    run_content_pipeline,
)


class TestFullPipelineFallback(unittest.TestCase):
    """Fallback modu uçtan uca içerik üretim hattı testleri."""

    def setUp(self):
        self.original_history = (
            HISTORY_FILE.read_text(encoding="utf-8") if HISTORY_FILE.exists() else "[]"
        )
        # Çıktı dosyalarını temizle
        for p in [Path("voiceover.mp3"), Path("script.txt"), Path("voiceover.srt"), Path("script.json")]:
            p.unlink(missing_ok=True)

    def tearDown(self):
        HISTORY_FILE.write_text(self.original_history, encoding="utf-8")
        for p in [Path("voiceover.mp3"), Path("script.txt"), Path("voiceover.srt"), Path("script.json")]:
            p.unlink(missing_ok=True)

    def test_full_pipeline_creates_all_outputs(self):
        """run_content_pipeline(force_fallback=True) tüm çıkış dosyalarını oluşturmalı."""
        before = load_recent_titles()
        payload = run_content_pipeline(
            concept="İlginç Bilgiler",
            force_fallback=True,
            channel_id="1",
        )

        # 1. Dönüş değeri (payload) doğruluğu
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["llm_provider"], "local-fallback-matrix-1")
        self.assertTrue(payload["title"].endswith("#Shorts"))
        self.assertGreaterEqual(payload["word_count"], 45)
        self.assertLessEqual(payload["word_count"], 110)
        self.assertGreater(payload["audio_duration_sec"], 0)

        # 2. Dosya varlığı
        self.assertTrue(Path("script.txt").exists(), "script.txt oluşturulmadı")
        self.assertTrue(Path("voiceover.mp3").exists(), "voiceover.mp3 oluşturulmadı")
        self.assertTrue(Path("voiceover.srt").exists(), "voiceover.srt oluşturulmadı")
        self.assertTrue(Path("script.json").exists(), "script.json oluşturulmadı")

        # 3. script.txt içeriği = script_text
        script_txt = Path("script.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(script_txt, payload["script_text"])

        # 4. voiceover.mp3 boş değil (>1 KB)
        self.assertGreater(Path("voiceover.mp3").stat().st_size, 1024)

        # 5. voiceover.srt içeriği (SRT formatı: numara\\nzaman --> zaman\\nmetin)
        srt = Path("voiceover.srt").read_text(encoding="utf-8")
        self.assertIn("-->", srt, "SRT zaman damgası eksik")

        # 6. script.json içeriği (geçerli JSON, gerekli anahtarlar)
        script_json = json.loads(Path("script.json").read_text(encoding="utf-8"))
        for key in [
            "title", "script_text", "topic", "description",
            "visual_keywords", "viral_hashtags", "thumbnail_prompt",
            "audio_file", "srt_file", "word_timestamps",
        ]:
            self.assertIn(key, script_json, f"script.json'da eksik anahtar: {key}")
        self.assertEqual(script_json["title"], payload["title"])
        self.assertEqual(len(script_json["viral_hashtags"]), 3)

        # 7. .used_topics.json güncellendi (yeni başlık eklendi)
        after = load_recent_titles()
        self.assertIn(payload["title"], after, "Üretilen başlık .used_topics.json'a eklenmedi")
        self.assertLessEqual(len(after), 25, ".used_topics.json 25 kayıtı aştı")


if __name__ == "__main__":
    unittest.main()
