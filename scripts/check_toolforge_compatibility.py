#!/usr/bin/env python3
"""Check old Toolforge-compatible URLs against a running web app."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://127.0.0.1:8780"


@dataclass(frozen=True)
class CompatibilityCase:
    """One legacy web URL that should continue to render a filled template."""

    name: str
    path: str
    expected_text: str


COMPATIBILITY_CASES: tuple[CompatibilityCase, ...] = (
    CompatibilityCase(
        "legacy root PubMed URL",
        "/?ddb=&type=pubmed_id&id=18535242&add_param_space=1&add_ref_tag=1&full_journal_title=1",
        "{{cite journal",
    ),
    CompatibilityCase(
        "legacy CGI PubMed URL",
        "/cgi-bin/index.cgi?ddb=&type=pubmed_id&id=18535242&add_param_space=1&add_ref_tag=1&full_journal_title=1",
        "{{cite journal",
    ),
    CompatibilityCase(
        "legacy PubMed Central URL",
        "/?type=pubmedcentral_id&id=137841&add_param_space=1",
        "{{cite journal",
    ),
    CompatibilityCase(
        "legacy ISBN URL",
        "/?type=isbn&id=0-7216-5944-6&add_param_space=1",
        "{{cite book",
    ),
    CompatibilityCase(
        "legacy HGNC protein URL",
        "/?type=hgnc_id&id=HGNC%3A1582&add_param_space=1&vertical=1",
        "{{infobox protein",
    ),
    CompatibilityCase(
        "legacy PubChem drugbox URL",
        "/?type=pubchem_cid&id=2244&add_param_space=1",
        "{{Infobox drug",
    ),
    CompatibilityCase(
        "legacy PubChem chembox URL",
        "/?type=pubchem_id&id=2244&add_param_space=1&add_iupac_name=1",
        "{{chembox",
    ),
    CompatibilityCase(
        "new fill route PubMed URL",
        "/fill?source_type=pmid&identifier=18535242&add_param_space=1",
        "{{cite journal",
    ),
)


def build_url(base_url: str, path: str) -> str:
    """Join a host root with one of the absolute compatibility paths."""
    clean_base_url = base_url.rstrip("/")
    return f"{clean_base_url}{path}"


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "wikipedia-template-filler compatibility check"})
    with urlopen(request, timeout=30) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def run_checks(
    base_url: str = DEFAULT_BASE_URL,
    cases: Sequence[CompatibilityCase] = COMPATIBILITY_CASES,
    *,
    fetch_func: Callable[[str], str] = fetch_text,
) -> int:
    failures = 0
    for case in cases:
        url = build_url(base_url, case.path)
        try:
            body = fetch_func(url)
        except HTTPError as exc:
            failures += 1
            print(f"FAIL {case.name}: HTTP {exc.code} {url}", file=sys.stderr)
            continue
        except URLError as exc:
            failures += 1
            print(f"FAIL {case.name}: {exc.reason} {url}", file=sys.stderr)
            continue
        except Exception as exc:
            failures += 1
            print(f"FAIL {case.name}: unexpected {type(exc).__name__}: {exc} {url}", file=sys.stderr)
            continue
        if case.expected_text not in body:
            failures += 1
            print(f"FAIL {case.name}: expected {case.expected_text!r} in response {url}", file=sys.stderr)
            continue
        print(f"OK   {case.name} {url}")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check old Toolforge-style web URLs against a running app.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"web app base URL, default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument("--list", action="store_true", help="list compatibility URLs without fetching them")
    return parser


def print_cases(base_url: str) -> None:
    for case in COMPATIBILITY_CASES:
        print(f"{case.name}\t{build_url(base_url, case.path)}\t{case.expected_text}")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print_cases(args.base_url)
        return 0
    return run_checks(args.base_url)


if __name__ == "__main__":
    raise SystemExit(main())
