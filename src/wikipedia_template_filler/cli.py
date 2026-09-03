"""Command-line entry point for wikipedia-template-filler."""

from __future__ import annotations

import argparse
import sys

from . import __version__, fill
from .api import TemplateFillerError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wikipedia-template-filler",
        description="Generate Wikipedia template markup from public identifiers.",
    )
    parser.add_argument("source_type", nargs="?", help="source type, such as isbn")
    parser.add_argument("identifier", nargs="?", help="identifier to look up")
    parser.add_argument("--add-param-space", action="store_true", help="pad template parameter names and values")
    parser.add_argument("--vertical", action="store_true", help="render one template parameter per line")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.source_type or not args.identifier:
        parser.print_help()
        return 2

    try:
        print(
            fill(
                args.source_type,
                args.identifier,
                add_param_space=args.add_param_space,
                vertical=args.vertical,
            )
        )
    except TemplateFillerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
