import contextlib
import io
import unittest

import wikipedia_template_filler
from wikipedia_template_filler import fill
from wikipedia_template_filler.cli import main


class PackageTests(unittest.TestCase):
    def test_version_is_available(self):
        self.assertEqual(wikipedia_template_filler.__version__, "0.1.0")

    def test_fill_placeholder_is_explicit(self):
        with self.assertRaisesRegex(NotImplementedError, "isbn.*not implemented"):
            fill("isbn", "0721659446")

    def test_cli_without_arguments_shows_help(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main([])
        self.assertEqual(exit_code, 2)
        self.assertIn("Generate Wikipedia template markup", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
