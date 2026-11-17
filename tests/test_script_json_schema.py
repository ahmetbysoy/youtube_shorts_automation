"""JSON sözleşmesi: legacy v1 uyumluluğu ve güncel v2 doğrulaması."""
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.validate_script_json import validate_payload

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "script.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


class TestScriptJsonSchema(unittest.TestCase):
    def test_runtime_validator_accepts_legacy_sample(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_payload(sample), [])

    def test_runtime_validator_rejects_invalid_payload(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        del sample["title"]
        self.assertTrue(validate_payload(sample))

    def test_media_processor_credit_metadata_keeps_payload_valid(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        sample["description"] = (sample.get("description") or "") + "\n\nWikimedia Commons: Author, CC BY-SA 4.0"
        sample["media_credits"] = ["Wikimedia Commons: Author, CC BY-SA 4.0"]
        self.assertEqual(validate_payload(sample), [])

    def test_schema_definition_is_valid(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_existing_sample_is_accepted_as_legacy_v1(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        self.assertNotIn("schema_version", sample)
        self.assertEqual(list(VALIDATOR.iter_errors(sample)), [])

    def test_current_v2_payload_is_accepted(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        sample.update({
            "schema_version": "2.0",
            "generation_id": "3d594650-7a9f-4ef5-b18e-9b4efaa67c31",
            "sources": [{"name": "Example source", "url": "https://example.com/source", "supports_claims": ["c1"]}],
            "fact_check": {"status": "passed", "claims": [{"claim": "Example claim", "status": "verified", "source_ids": ["s1"]}]},
            "storyboard": [{
                "scene_id": 1, "start_ms": 0, "end_ms": 2500,
                "narration": "Örnek anlatım", "visual_query": "historic palace exterior",
                "alternative_queries": ["old palace"], "source_ids": ["s1"], "media_type": "video"
            }]
        })
        self.assertEqual(list(VALIDATOR.iter_errors(sample)), [])

    def test_missing_required_field_is_rejected(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        del sample["script_text"]
        self.assertTrue(list(VALIDATOR.iter_errors(sample)))

    def test_invalid_timestamp_is_rejected(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        sample["word_timestamps"][0]["start_ms"] = -1
        self.assertTrue(list(VALIDATOR.iter_errors(sample)))

    def test_invalid_v2_version_and_uuid_are_rejected(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        sample.update({"schema_version": "9.9", "generation_id": "not-a-uuid"})
        self.assertTrue(list(VALIDATOR.iter_errors(sample)))

    def test_wrong_storyboard_type_is_rejected(self):
        sample = json.loads((ROOT / "samples" / "script.json").read_text(encoding="utf-8"))
        sample.update({"schema_version": "2.0", "generation_id": "3d594650-7a9f-4ef5-b18e-9b4efaa67c31", "storyboard": "not-an-array"})
        self.assertTrue(list(VALIDATOR.iter_errors(sample)))


if __name__ == "__main__":
    unittest.main()
