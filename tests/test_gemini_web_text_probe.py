"""Gemini Web text probe için ağ ve cookie kullanmayan sözleşme testleri."""

import json
import os
import unittest

from scripts.gemini_web_text_probe import (
    _env_float,
    _parse_backoff_schedule,
    parse_cookie_payload,
    validate_model_text,
)


class TestTimeoutHelpers(unittest.TestCase):
    def test_env_float_returns_default_when_missing(self):
        self.assertEqual(_env_float("TEST_ENV_FLOAT_YOK_1234", 80), 80)

    def test_env_float_parses_positive_value(self):
        os.environ["TEST_ENV_FLOAT_OK"] = "123.5"
        try:
            self.assertEqual(_env_float("TEST_ENV_FLOAT_OK", 80), 123.5)
        finally:
            os.environ.pop("TEST_ENV_FLOAT_OK", None)

    def test_env_float_rejects_non_positive_and_garbage(self):
        os.environ["TEST_ENV_FLOAT_BAD1"] = "-3"
        os.environ["TEST_ENV_FLOAT_BAD2"] = "abc"
        try:
            self.assertEqual(_env_float("TEST_ENV_FLOAT_BAD1", 35), 35)
            self.assertEqual(_env_float("TEST_ENV_FLOAT_BAD2", 55), 55)
        finally:
            os.environ.pop("TEST_ENV_FLOAT_BAD1", None)
            os.environ.pop("TEST_ENV_FLOAT_BAD2", None)

    def test_backoff_schedule_parses_list(self):
        self.assertEqual(_parse_backoff_schedule("10,20", 3), [10.0, 20.0])

    def test_backoff_schedule_fills_missing_gaps_with_last_value(self):
        self.assertEqual(_parse_backoff_schedule("15", 3), [15.0, 15.0])

    def test_backoff_schedule_skips_invalid_parts(self):
        self.assertEqual(_parse_backoff_schedule("10,x,30", 4), [10.0, 30.0, 30.0])

    def test_backoff_schedule_empty_means_zero(self):
        self.assertEqual(_parse_backoff_schedule("", 3), [0.0, 0.0])


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

    def test_cookie_payload_allows_optional_refresh_cookie(self):
        parsed = parse_cookie_payload(json.dumps({"__Secure-1PSID": "session-cookie"}))
        self.assertEqual(parsed["__Secure-1PSID"], "session-cookie")
        self.assertEqual(parsed["__Secure-1PSIDTS"], "")

    def test_cookie_payload_rejects_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "geçerli JSON"):
            parse_cookie_payload("{not-json")

    def test_cookie_payload_rejects_missing_session_cookie(self):
        with self.assertRaisesRegex(ValueError, "__Secure-1PSID"):
            parse_cookie_payload(json.dumps({"__Secure-1PSIDTS": "refresh-only"}))

    def test_cookie_payload_rejects_non_string_refresh_cookie(self):
        with self.assertRaisesRegex(ValueError, "__Secure-1PSIDTS"):
            parse_cookie_payload(json.dumps({
                "__Secure-1PSID": "session-cookie",
                "__Secure-1PSIDTS": 123,
            }))

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
