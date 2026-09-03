import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest import mock

import wikipedia_template_filler
from wikipedia_template_filler import (
    TemplateFiller,
    UnknownSourceError,
    NotImplementedSourceError,
    UnsupportedSourceError,
    fill,
)
from wikipedia_template_filler.cli import SMOKE_CASES, main, run_smoke_cases


class PackageTests(unittest.TestCase):
    def test_version_is_available(self):
        self.assertEqual(wikipedia_template_filler.__version__, "0.1.0")

    def test_source_statuses_are_current(self):
        filler = TemplateFiller()
        self.assertEqual(filler.source_spec("pmid").status, "supported")
        self.assertEqual(filler.source_spec("pmc").status, "supported")
        self.assertEqual(filler.source_spec("hgnc").status, "supported")
        self.assertEqual(filler.source_spec("isbn").status, "supported")
        self.assertEqual(filler.source_spec("pubchem").status, "supported")
        self.assertEqual(filler.source_spec("chembox").status, "supported")
        self.assertEqual(filler.source_spec("web").status, "pending")
        self.assertEqual(filler.source_spec("drugbank").status, "unsupported")

    def test_template_filler_normalizes_source_aliases(self):
        filler = TemplateFiller()
        self.assertEqual(filler.source_spec("PMID").source_type, "pubmed_id")
        self.assertEqual(filler.source_spec("pmc").source_type, "pubmedcentral_id")
        self.assertEqual(filler.source_spec("HGNC").template, "infobox protein")
        self.assertEqual(filler.source_spec("drug").template, "infobox drug")
        self.assertEqual(filler.source_spec("pubchem_id").template, "chembox")

    def test_unknown_source_raises_specific_error(self):
        with self.assertRaisesRegex(UnknownSourceError, "unknown source type"):
            TemplateFiller().fill("not_a_source", "123")

    def test_drugbank_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(UnsupportedSourceError, "DrugBank/drugbox lookup is currently unsupported"):
            fill("drugbank_id", "DB00338")

    def test_url_source_is_explicitly_pending(self):
        with self.assertRaises(NotImplementedSourceError) as context:
            fill("url", "https://example.org")
        self.assertIn("URL -> {{cite web}} lookup is recognized", str(context.exception))

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

    def test_smoke_script_lists_cases_without_live_network(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "smoke_supported_sources.py"
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(script_path), "--list"]):
            namespace = runpy.run_path(str(script_path), run_name="smoke_supported_sources_test")
            with contextlib.redirect_stdout(stdout):
                exit_code = namespace["main"]()
        self.assertEqual(exit_code, 0)
        self.assertIn("pubmed_id\t18535242", stdout.getvalue())

    def test_cli_lists_smoke_cases_without_live_network(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["smoke", "--list"])
        self.assertEqual(exit_code, 0)
        self.assertIn("pubmed_id\t18535242", stdout.getvalue())
        self.assertIn("pubchem_id\t2244", stdout.getvalue())

    def test_toolforge_compatibility_script_lists_cases_without_network(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_toolforge_compatibility.py"
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(script_path), "--list"]):
            namespace = runpy.run_path(str(script_path), run_name="toolforge_compatibility_test")
            with contextlib.redirect_stdout(stdout):
                exit_code = namespace["main"]()
        self.assertEqual(exit_code, 0)
        self.assertIn("legacy CGI PubMed URL", stdout.getvalue())
        self.assertIn("/cgi-bin/index.cgi?ddb=&type=pubmed_id", stdout.getvalue())

    def test_toolforge_compatibility_runner_accepts_expected_output(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_toolforge_compatibility.py"
        namespace = runpy.run_path(str(script_path), run_name="toolforge_compatibility_test")
        case = namespace["CompatibilityCase"]("example old URL", "/?type=pubmed_id&id=1", "needle")
        calls = []

        def fake_fetch(url: str) -> str:
            calls.append(url)
            return "prefix needle suffix"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = namespace["run_checks"]("http://example.test", cases=(case,), fetch_func=fake_fetch)
        self.assertEqual(exit_code, 0)
        self.assertEqual(calls, ["http://example.test/?type=pubmed_id&id=1"])
        self.assertIn("OK   example old URL", stdout.getvalue())

    def test_toolforge_compatibility_runner_fails_on_unexpected_output(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "check_toolforge_compatibility.py"
        namespace = runpy.run_path(str(script_path), run_name="toolforge_compatibility_test")
        case = namespace["CompatibilityCase"]("example old URL", "/?type=pubmed_id&id=1", "needle")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = namespace["run_checks"]("http://example.test", cases=(case,), fetch_func=lambda url: "wrong")
        self.assertEqual(exit_code, 1)
        self.assertIn("expected", stderr.getvalue())

    def test_smoke_runner_accepts_expected_output(self):
        def fake_fill(source_type: str, identifier: str, **options: object) -> str:
            case = next(case for case in SMOKE_CASES if case.source_type == source_type)
            self.assertTrue(options["add_param_space"])
            self.assertFalse(options["vertical"])
            return f"{case.expected_text}}}"

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = run_smoke_cases(fill_func=fake_fill)
        self.assertEqual(exit_code, 0)
        self.assertIn("OK   PubMed ID -> cite journal", stdout.getvalue())

    def test_smoke_runner_fails_on_unexpected_output(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = run_smoke_cases(SMOKE_CASES[:1], fill_func=lambda *args, **kwargs: "wrong template")
        self.assertEqual(exit_code, 1)
        self.assertIn("expected", stderr.getvalue())

    def test_cli_reports_api_errors(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["drugbank_id", "DB00338"])
        self.assertEqual(exit_code, 1)
        self.assertIn("DrugBank/drugbox lookup is currently unsupported", stderr.getvalue())

    def test_cli_reports_pending_sources(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(["url", "https://example.org"])
        self.assertEqual(exit_code, 1)
        self.assertIn("URL -> {{cite web}} lookup is recognized", stderr.getvalue())

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
