import contextlib
import io
import unittest

import wikipedia_template_filler
from wikipedia_template_filler import (
    NotImplementedSourceError,
    TemplateFiller,
    UnknownSourceError,
    UnsupportedSourceError,
    fill,
)
from wikipedia_template_filler.cli import main


class PackageTests(unittest.TestCase):
    def test_version_is_available(self):
        self.assertEqual(wikipedia_template_filler.__version__, "0.1.0")

    def test_fill_placeholder_is_explicit_for_pending_sources(self):
        with self.assertRaisesRegex(NotImplementedSourceError, "pubmed_id.*cite journal.*not implemented"):
            fill("pubmed_id", "18535242")

    def test_template_filler_normalizes_source_aliases(self):
        filler = TemplateFiller()
        self.assertEqual(filler.source_spec("PMID").source_type, "pubmed_id")
        self.assertEqual(filler.source_spec("pmc").source_type, "pubmedcentral_id")
        self.assertEqual(filler.source_spec("HGNC").template, "infobox protein")

    def test_unknown_source_raises_specific_error(self):
        with self.assertRaisesRegex(UnknownSourceError, "unknown source type"):
            TemplateFiller().fill("not_a_source", "123")

    def test_drugbank_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(UnsupportedSourceError, "DrugBank/drugbox lookup is currently unsupported"):
            fill("drugbank_id", "DB00338")

    def test_cli_without_arguments_shows_help(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main([])
        self.assertEqual(exit_code, 2)
        self.assertIn("Generate Wikipedia template markup", stdout.getvalue())

    def test_cli_reports_api_errors(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["drugbank_id", "DB00338"])
        self.assertEqual(exit_code, 1)
        self.assertIn("DrugBank/drugbox lookup is currently unsupported", stderr.getvalue())

    def test_cli_accepts_renderer_options_for_api_calls(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["pubmed_id", "18535242", "--add-param-space", "--vertical"])
        self.assertEqual(exit_code, 1)
        self.assertIn("pubmed_id", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
