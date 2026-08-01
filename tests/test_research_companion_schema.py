import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from export_mfa_db_research_6tier import (  # noqa: E402
    EXCLUDED_FIELDS,
    PHONE_FIELDS,
    UTTERANCE_FIELDS,
    WORD_FIELDS,
)
from research_companion_schema import load_schema, validate_field_order  # noqa: E402


class ResearchCompanionSchemaTests(unittest.TestCase):
    def test_schema_covers_exporter_fields_exactly(self):
        _path, schema = load_schema()
        validate_field_order(
            schema,
            {
                "utterances": UTTERANCE_FIELDS,
                "words": WORD_FIELDS,
                "phones": PHONE_FIELDS,
                "excluded": EXCLUDED_FIELDS,
            },
        )
        self.assertEqual(schema["csv"]["boolean_true"], "true")
        self.assertEqual(schema["compression"]["mtime"], 0)


if __name__ == "__main__":
    unittest.main()
