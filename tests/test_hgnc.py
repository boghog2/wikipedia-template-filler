import json
import unittest
from pathlib import Path

from wikipedia_template_filler import fill
from wikipedia_template_filler.sources.hgnc import (
    SourceLookupError,
    fill_hgnc,
    first_value,
    gene_fields,
    hgnc_url,
    normalize_hgnc_id,
    parse_hgnc_response,
    split_location,
    strip_accession_version,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
NORMALIZED_DIR = FIXTURE_DIR / "normalized"


def load_fixture(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def hgnc_json() -> str:
    return json.dumps(
        {
            "responseHeader": {"status": 0, "QTime": 1},
            "response": {
                "numFound": 1,
                "docs": [
                    {
                        "hgnc_id": "HGNC:1582",
                        "symbol": "CCND1",
                        "name": "cyclin D1",
                        "prev_symbol": ["BCL1", "D11S287E", "PRAD1"],
                        "entrez_id": "595",
                        "omim_id": ["168461"],
                        "refseq_accession": ["NM_053056.3"],
                        "uniprot_ids": ["P24385"],
                        "location": "11q13.3",
                    }
                ],
            },
        }
    )


class HgncTests(unittest.TestCase):
    def test_normalize_hgnc_id(self):
        self.assertEqual(normalize_hgnc_id("HGNC:1582"), "1582")
        self.assertEqual(normalize_hgnc_id("1582"), "1582")

    def test_hgnc_url(self):
        self.assertEqual(hgnc_url("1582"), "https://rest.genenames.org/fetch/hgnc_id/HGNC%3A1582")

    def test_format_helpers(self):
        self.assertEqual(first_value(["P24385"]), "P24385")
        self.assertEqual(first_value([]), "")
        self.assertEqual(strip_accession_version("NM_053056.3"), "NM_053056")
        self.assertEqual(split_location("11q13.3"), ("11", "q", "13.3"))

    def test_parse_hgnc_response_matches_normalized_fixture(self):
        normalized = load_fixture(NORMALIZED_DIR, "hgnc_1582_infobox_protein.json")
        gene = parse_hgnc_response(hgnc_json(), expected_hgnc_id="1582")
        self.assertEqual(gene_fields(gene), [(field["name"], field["value"]) for field in normalized["fields"]])

    def test_fill_hgnc_matches_golden_fixture_with_fake_fetcher(self):
        golden = load_fixture(GOLDEN_DIR, "hgnc_1582_infobox_protein.json")

        def fake_fetcher(url: str) -> str:
            self.assertEqual(url, hgnc_url("1582"))
            return hgnc_json()

        self.assertEqual(fill_hgnc(golden["id"], json_fetcher=fake_fetcher, **golden["options"]), golden["output"])

    def test_fetch_raises_for_missing_gene(self):
        with self.assertRaisesRegex(SourceLookupError, "no gene matches"):
            parse_hgnc_response(json.dumps({"response": {"docs": []}}), expected_hgnc_id="1")

    def test_public_fill_routes_to_hgnc_source(self):
        self.assertEqual(
            fill("hgnc", "HGNC:1582", json_fetcher=lambda url: hgnc_json(), add_param_space=True),
            load_fixture(GOLDEN_DIR, "hgnc_1582_infobox_protein.json")["output"],
        )


if __name__ == "__main__":
    unittest.main()
