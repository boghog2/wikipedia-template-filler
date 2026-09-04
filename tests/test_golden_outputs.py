import json
import unittest
from pathlib import Path

from wikipedia_template_filler import TemplateFiller, UnsupportedSourceError
from wikipedia_template_filler.renderer import render_template


FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
NORMALIZED_DIR = FIXTURE_DIR / "normalized"


class GoldenOutputTests(unittest.TestCase):
    def fixture(self, directory: Path, name: str) -> dict:
        return json.loads((directory / name).read_text(encoding="utf-8"))

    def test_normalized_source_fields_render_to_golden_outputs(self):
        for path in sorted(NORMALIZED_DIR.glob("*.json")):
            with self.subTest(fixture=path.name):
                normalized = self.fixture(NORMALIZED_DIR, path.name)
                golden = self.fixture(GOLDEN_DIR, normalized["golden"])

                self.assertEqual(normalized["source_type"], golden["source_type"])
                self.assertEqual(normalized["id"], golden["id"])
                self.assertEqual(normalized["template"], golden["template"])

                output = render_template(
                    normalized["template"],
                    normalized["fields"],
                    **normalized["options"],
                    include_empty=True,
                )
                self.assertEqual(output, golden["output"])

    def test_golden_source_types_are_known_to_api(self):
        filler = TemplateFiller()
        for path in sorted(GOLDEN_DIR.glob("*.json")):
            with self.subTest(fixture=path.name):
                fixture = self.fixture(GOLDEN_DIR, path.name)
                spec = filler.source_spec(fixture["source_type"])
                self.assertEqual(spec.template, fixture["template"])

    def test_drugbank_unsupported_message_matches_golden_fixture(self):
        fixture = self.fixture(GOLDEN_DIR, "drugbank_unsupported.json")
        with self.assertRaisesRegex(UnsupportedSourceError, fixture["error"]):
            TemplateFiller().fill(fixture["source_type"], fixture["id"])


if __name__ == "__main__":
    unittest.main()
