"""Gemini Web text probe için ağ ve cookie kullanmayan sözleşme testleri."""

import json
import unittest

from scripts.gemini_web_text_probe import parse_cookie_payload, validate_model_text


class TestGeminiWebTextProbe(unittest.TestCase):
    def test_cookie_payload_accepts_required_web_session_fields(self):
        raw = json.dumps({
            "__Secure-1PSID": "session-cookie",
            "__Secure-1PSIDTS": "session-refresh-cookie",
            "other": "ignored",
        })
        parsed = parse_cookie_payload(raw)
        self.assertEqual(set(parsed), {"__Secure-1PSID", "__Secure-1PSIDTS"})
        self.assertEqual(parsed["__Secure-1PSID"], "session-cookie")

    def test_cookie_payload_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "geçerli JSON"):
            parse_cookie_payload("{not-json")

    def test_cookie_payload_rejects_missing_required_cookie(self):
        with self.assertRaisesRegex(ValueError, "__Secure-1PSIDTS"):
            parse_cookie_payload(json.dumps({"__Secure-1PSID": "only-one"}))

    def test_model_text_requires_four_specific_visual_queries(self):
        raw = {
            "topic": "Bilim",
            "title": "Venüs'te Bir Gün Neden Uzun? #Shorts",
            "description": "Venüs'ün sıra dışı dönüşü",
            "hook": "Bir gezegende günün bir yıldan uzun olduğunu biliyor muydunuz?",
            "script_text": " ".join(["Venüs"] * 60),
            "visual_keywords": ["venus planet", "venus rotation", "solar orbit"],
        }
        with self.assertRaisesRegex(ValueError, "en az dört"):
            validate_model_text(json.dumps(raw, ensure_ascii=False))

    def test_model_text_normalizes_valid_json(self):
        script = (
            "Venüs kendi ekseni etrafında çok yavaş döner ve bu nedenle bir dönüşü "
            "Dünya zamanıyla yaklaşık iki yüz kırk üç gün sürer. Güneş çevresindeki "
            "yörüngesini ise yaklaşık iki yüz yirmi beş günde tamamlar. Bu iki süre "
            "arasındaki fark, gezegenin sıra dışı hareketini ortaya koyar. "
            "Araştırmacılar bu ölçümleri uzay araçlarıyla incelemiştir. "
            "Sence böyle bir gezegende yaşamak nasıl olurdu?"
        )
        raw = {
            "topic": "Bilim",
            "title": "Venüs'te Bir Gün Neden Uzun? #Shorts",
            "description": "Venüs'ün sıra dışı dönüşü",
            "hook": "Venüs'te zaman algısı şaşırtıcıdır.",
            "script_text": script,
            "visual_keywords": [
                "venus planet surface",
                "venus rotation orbit",
                "solar system venus",
                "venus cloud atmosphere",
            ],
            "viral_hashtags": ["#venüs", "#uzay", "#gezegen"],
        }
        scenario = validate_model_text(json.dumps(raw, ensure_ascii=False))
        self.assertEqual(scenario["provider"], "gemini-web-session")
        self.assertGreaterEqual(scenario["word_count"], 55)
        self.assertLessEqual(scenario["word_count"], 95)
        self.assertEqual(len(scenario["visual_keywords"]), 4)
        self.assertEqual(len(scenario["viral_hashtags"]), 3)


if __name__ == "__main__":
    unittest.main()
