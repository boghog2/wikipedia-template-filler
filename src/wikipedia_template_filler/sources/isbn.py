"""ISBN lookup through the Open Library Books API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from wikipedia_template_filler.api import TemplateFillerError
from wikipedia_template_filler.renderer import render_template

OPEN_LIBRARY_BOOKS_API = "https://openlibrary.org/api/books"


class SourceLookupError(TemplateFillerError):
    """Raised when an upstream source lookup fails."""


JsonFetcher = Callable[[str], Mapping[str, Any]]


def fill_isbn(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return a ``{{cite book}}`` template for *identifier*."""
    isbn = normalize_isbn(identifier)
    if not isbn:
        raise SourceLookupError("no ISBN given")

    fetcher = json_fetcher or fetch_json
    book = fetch_openlibrary_book(isbn, fetcher=fetcher)
    fields = book_fields(isbn, book, add_accessdate=bool(options.get("add_accessdate", False)))
    return render_template(
        "cite book",
        fields,
        add_param_space=bool(options.get("add_param_space", False)),
        vertical=bool(options.get("vertical", False)),
        include_empty=bool(options.get("extended", False)),
    )


def normalize_isbn(identifier: str) -> str:
    """Return ISBN digits/X only, matching the Perl normalizer."""
    return re.sub(r"[^0-9X]", "", identifier, flags=re.IGNORECASE).upper()


def openlibrary_url(isbn: str) -> str:
    """Build the Open Library Books API URL for *isbn*."""
    return f"{OPEN_LIBRARY_BOOKS_API}?bibkeys=ISBN:{quote(isbn)}&format=json&jscmd=data"


def fetch_openlibrary_book(isbn: str, *, fetcher: JsonFetcher | None = None) -> Mapping[str, Any]:
    """Fetch one Open Library book record for *isbn*."""
    data = (fetcher or fetch_json)(openlibrary_url(isbn))
    book = data.get(f"ISBN:{isbn}")
    if not isinstance(book, Mapping):
        raise SourceLookupError(f"no book matches the given ISBN ({isbn})")
    return book


def fetch_json(url: str) -> Mapping[str, Any]:
    """Fetch JSON from *url* using the standard library."""
    request = Request(url, headers={"User-Agent": "wikipedia-template-filler/0.2.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SourceLookupError(f"Open Library ISBN lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SourceLookupError(f"Open Library ISBN lookup failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SourceLookupError("Open Library returned invalid JSON") from exc


def book_fields(isbn: str, book: Mapping[str, Any], *, add_accessdate: bool = False) -> list[tuple[str, object]]:
    """Return ordered ``{{cite book}}`` fields for an Open Library record."""
    identifiers = book.get("identifiers")
    if not isinstance(identifiers, Mapping):
        identifiers = {}
    url = book_url(book)

    return [
        ("vauthors", vancouver_authors(book.get("authors"))),
        ("title", book.get("title", "")),
        ("publisher", join_names(book.get("publishers"))),
        ("location", join_names(book.get("publish_places"))),
        ("year", publication_year(book.get("publish_date"))),
        ("pages", str(book.get("number_of_pages", "") or "")),
        ("isbn", isbn),
        ("oclc", first_identifier(identifiers.get("oclc"))),
        ("doi", first_identifier(identifiers.get("doi"))),
        ("url", url),
        ("accessdate", current_accessdate() if add_accessdate and url else ""),
    ]


def book_url(book: Mapping[str, Any]) -> str:
    """Return the Open Library record URL when available."""
    url = book.get("url")
    return str(url) if url else ""


def current_accessdate() -> str:
    """Return today's date in the citation access-date style."""
    return date.today().strftime("%-d %B %Y")


def join_names(items: object) -> str:
    """Join Open Library ``[{name: ...}]`` records into a comma-separated string."""
    if not isinstance(items, list):
        return ""
    names = []
    for item in items:
        if isinstance(item, Mapping):
            name = item.get("name")
        else:
            name = item
        if name is not None:
            names.append(str(name))
    return ", ".join(names)


def vancouver_authors(authors: object) -> str:
    """Return Open Library author records as Vancouver-style names."""
    if not isinstance(authors, list):
        return ""
    names = []
    for author in authors:
        name = author.get("name") if isinstance(author, Mapping) else author
        converted = vancouver_name(str(name or ""))
        if converted:
            names.append(converted)
    return ", ".join(names)


def vancouver_name(name: str) -> str:
    """Convert a personal name to ``Lastname Initials``."""
    name = name.strip()
    if not name:
        return ""

    if "," in name:
        last, given = name.split(",", 1)
    else:
        parts = name.split()
        if len(parts) == 1:
            return name
        last = parts[-1]
        given = " ".join(parts[:-1])

    last = last.strip()
    given = re.sub(r"\b(?:jr|sr|ii|iii|iv|md|phd)\.?\b", "", given, flags=re.IGNORECASE).strip()
    initials = "".join(part[0].upper() for part in re.split(r"[\s.-]+", given) if part)
    return f"{last} {initials}" if initials else last


def first_identifier(value: object) -> str:
    """Return the first identifier value from Open Library identifier data."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    if value is None or isinstance(value, Mapping):
        return ""
    return str(value)


def publication_year(publish_date: object) -> str:
    """Extract a four-digit publication year when present."""
    text = str(publish_date or "")
    match = re.search(r"(\d{4})", text)
    return match.group(1) if match else text
