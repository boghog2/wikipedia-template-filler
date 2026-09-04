import json
import unittest
from pathlib import Path

from wikipedia_template_filler.renderer import TemplateField, fields_from_mapping, render_template


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden"


class RendererTests(unittest.TestCase):
    def test_inline_output_without_param_spacing(self):
        fields = [TemplateField("title", "Example"), TemplateField("doi", "")]
        self.assertEqual(render_template("cite journal", fields), "{{cite journal |title=Example}}")
        self.assertEqual(render_template("cite journal", fields, include_empty=True), "{{cite journal |title=Example |doi=}}")

    def test_inline_output_with_param_spacing_matches_cite_book_fixture(self):
        fixture = json.loads((FIXTURE_DIR / "isbn_0721659446_cite_book.json").read_text())
        fields = [
            ("vauthors", "Guyton AC, Hall JE"),
            ("title", "Textbook of medical physiology"),
            ("publisher", "W.B. Saunders"),
            ("location", "Philadelphia"),
            ("year", "1996"),
            ("pages", "1148"),
            ("isbn", "0721659446"),
            ("oclc", "31378424"),
            ("doi", ""),
            ("url", ""),
            ("accessdate", ""),
        ]
        self.assertEqual(render_template("cite book", fields, add_param_space=True, include_empty=True), fixture["output"])

    def test_vertical_output_with_param_spacing_matches_protein_fixture(self):
        fixture = json.loads((FIXTURE_DIR / "hgnc_1582_infobox_protein.json").read_text())
        fields = [
            ("name", "cyclin D1"),
            ("caption", ""),
            ("image", ""),
            ("width", ""),
            ("HGNCid", "1582"),
            ("Symbol", "CCND1"),
            ("AltSymbols", "BCL1, D11S287E, PRAD1"),
            ("EntrezGene", "595"),
            ("OMIM", "168461"),
            ("RefSeq", "NM_053056"),
            ("UniProt", "P24385"),
            ("PDB", ""),
            ("ECnumber", ""),
            ("Chromosome", "11"),
            ("Arm", "q"),
            ("Band", "13.3"),
            ("LocusSupplementaryData", ""),
        ]
        self.assertEqual(render_template("infobox protein", fields, add_param_space=True, vertical=True, include_empty=True), fixture["output"])

    def test_fields_from_mapping_preserves_insertion_order(self):
        fields = fields_from_mapping({"first": 1, "second": None})
        self.assertEqual(fields, [TemplateField("first", 1), TemplateField("second", None)])
        self.assertEqual(render_template("demo", fields), "{{demo |first=1}}")
        self.assertEqual(render_template("demo", fields, include_empty=True), "{{demo |first=1 |second=}}")

    def test_mapping_field_input(self):
        fields = [{"name": "title", "value": "Mapped"}]
        self.assertEqual(render_template("cite book", fields), "{{cite book |title=Mapped}}")


if __name__ == "__main__":
    unittest.main()
