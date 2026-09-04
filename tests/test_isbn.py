import json
import unittest
from pathlib import Path

from wikipedia_template_filler import fill
from wikipedia_template_filler.sources.isbn import (
    SourceLookupError,
    book_fields,
    fetch_openlibrary_book,
    fill_isbn,
    first_identifier,
    normalize_isbn,
    openlibrary_url,
    publication_year,
    vancouver_name,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
NORMALIZED_DIR = FIXTURE_DIR / "normalized"


def load_fixture(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


class IsbnTests(unittest.TestCase):
    def test_normalize_isbn(self):
        self.assertEqual(normalize_isbn("978-0-13-110362-7"), "9780131103627")
        self.assertEqual(normalize_isbn("0 7216 5944 X"), "072165944X")

    def test_openlibrary_url(self):
        self.assertEqual(
            openlibrary_url("0721659446"),
            "https://openlibrary.org/api/books?bibkeys=ISBN:0721659446&format=json&jscmd=data",
        )

    def test_vancouver_name(self):
        self.assertEqual(vancouver_name("Arthur C. Guyton"), "Guyton AC")
        self.assertEqual(vancouver_name("Hall, John E."), "Hall JE")
        self.assertEqual(vancouver_name("Single"), "Single")

    def test_identifier_and_year_helpers(self):
        self.assertEqual(first_identifier(["31378424", "other"]), "31378424")
        self.assertEqual(first_identifier(None), "")
        self.assertEqual(publication_year("November 15, 1996"), "1996")

    def test_book_fields_match_normalized_fixture(self):
        normalized = load_fixture(NORMALIZED_DIR, "isbn_0721659446_cite_book.json")
        book = {
            "authors": [{"name": "Arthur C. Guyton"}, {"name": "John E. Hall"}],
            "title": "Textbook of medical physiology",
            "publishers": [{"name": "W.B. Saunders"}],
            "publish_places": [{"name": "Philadelphia"}],
            "publish_date": "1996",
            "number_of_pages": 1148,
            "identifiers": {"oclc": ["31378424"]},
        }
        self.assertEqual(book_fields("0721659446", book), [(field["name"], field["value"]) for field in normalized["fields"]])

    def test_fill_isbn_matches_golden_fixture_with_fake_fetcher(self):
        golden = load_fixture(GOLDEN_DIR, "isbn_0721659446_cite_book.json")

        def fake_fetcher(url: str):
            self.assertEqual(url, openlibrary_url(golden["id"]))
            return {
                "ISBN:0721659446": {
                    "authors": [{"name": "Arthur C. Guyton"}, {"name": "John E. Hall"}],
                    "title": "Textbook of medical physiology",
                    "publishers": [{"name": "W.B. Saunders"}],
                    "publish_places": [{"name": "Philadelphia"}],
                    "publish_date": "1996",
                    "number_of_pages": 1148,
                    "identifiers": {"oclc": ["31378424"]},
                }
            }

        self.assertEqual(fill_isbn(golden["id"], json_fetcher=fake_fetcher, extended=True, **golden["options"]), golden["output"])

    def test_fetch_openlibrary_book_raises_for_missing_record(self):
        with self.assertRaisesRegex(SourceLookupError, "no book matches"):
            fetch_openlibrary_book("0000000000", fetcher=lambda url: {})

    def test_public_fill_routes_to_isbn_source(self):
        with self.assertRaisesRegex(SourceLookupError, "no book matches"):
            fill("isbn", "0000000000", json_fetcher=lambda url: {})
