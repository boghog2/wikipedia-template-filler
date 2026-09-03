import contextlib
import io
import unittest
from unittest import mock

import wikipedia_template_filler
from wikipedia_template_filler import (
    TemplateFiller,
    UnknownSourceError,
    UnsupportedSourceError,
    fill,
)
from wikipedia_template_filler.cli import main


class PackageTests(unittest.TestCase):
    def test_version_is_available(self):
        self.assertEqual(wikipedia_template_filler.__version__, "0.1.0")

    def test_source_statuses_are_current(self):
        filler = TemplateFiller()
        self.assertEqual(filler.source_spec("pmid").status, "supported")
        self.assertEqual(filler.source_spec("pmc").status, "supported")
        self.assertEqual(filler.source_spec("hgnc").status, "supported")
        self.assertEqual(filler.source_spec("isbn").status, "supported")
        self.assertEqual(filler.source_spec("drugbank").status, "unsupported")

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

    def test_cli_lists_sources(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["sources"])
        self.assertEqual(exit_code, 0)
        self.assertIn("pubmed_id", stdout.getvalue())
        self.assertIn("pubmedcentral_id", stdout.getvalue())
        self.assertIn("unsupported", stdout.getvalue())

    def test_cli_filters_sources_by_status(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["sources", "--status", "supported"])
        self.assertEqual(exit_code, 0)
        self.assertIn("pubmed_id", stdout.getvalue())
        self.assertNotIn("drugbank_id", stdout.getvalue())

    def test_cli_fill_subcommand_prints_template(self):
        stdout = io.StringIO()
        with mock.patch("wikipedia_template_filler.cli.fill", return_value="{{cite journal}}") as fake_fill:
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["fill", "pmid", "18535242", "--add-param-space"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "{{cite journal}}\n")
        fake_fill.assert_called_once_with("pmid", "18535242", add_param_space=True, vertical=False)

    def test_cli_legacy_positional_form_still_prints_template(self):
        stdout = io.StringIO()
        with mock.patch("wikipedia_template_filler.cli.fill", return_value="{{cite book}}") as fake_fill:
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["isbn", "0721659446", "--vertical"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "{{cite book}}\n")
        fake_fill.assert_called_once_with("isbn", "0721659446", add_param_space=False, vertical=True)

    def test_cli_reports_api_errors(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["drugbank_id", "DB00338"])
        self.assertEqual(exit_code, 1)
        self.assertIn("DrugBank/drugbox lookup is currently unsupported", stderr.getvalue())

    def test_cli_accepts_renderer_options_for_api_calls(self):
        stdout = io.StringIO()
        with mock.patch("wikipedia_template_filler.cli.fill", return_value="{{infobox protein}}") as fake_fill:
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["hgnc_id", "HGNC:1582", "--add-param-space", "--vertical"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "{{infobox protein}}\n")
        fake_fill.assert_called_once_with("hgnc_id", "HGNC:1582", add_param_space=True, vertical=True)


if __name__ == "__main__":
    unittest.main()
