"""Command-line entry point for wikipedia-template-filler."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__, fill
from .api import SUPPORTED_SOURCES, TemplateFillerError

COMMANDS = {"fill", "sources"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wikipedia-template-filler",
        description="Generate Wikipedia template markup from public identifiers.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="command")
    fill_parser = subparsers.add_parser("fill", help="generate template markup for one identifier")
    add_fill_arguments(fill_parser)

    sources_parser = subparsers.add_parser("sources", help="list recognized identifier sources")
    add_sources_arguments(sources_parser)
    return parser


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wikipedia-template-filler",
        description="Generate Wikipedia template markup from public identifiers.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    add_fill_arguments(parser)
    return parser


def add_fill_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source_type", help="source type, such as isbn, pmid, or pmc")
    parser.add_argument("identifier", help="identifier to look up")
    add_renderer_options(parser)


def add_sources_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--status",
        choices=("supported", "pending", "unsupported"),
        help="only list sources with this support status",
    )


def add_renderer_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--add-param-space", action="store_true", help="pad template parameter names and values")
    parser.add_argument("--vertical", action="store_true", help="render one template parameter per line")


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    if not args_list:
        parser.print_help()
        return 2

    command = args_list[0]
    if command in {"-h", "--help", "--version"}:
        parser.parse_args(args_list)
        return 0
    if command == "sources":
        args = build_sources_parser().parse_args(args_list[1:])
        print_sources(status=args.status)
        return 0
    if command == "fill":
        args = build_fill_parser().parse_args(args_list[1:])
        return print_filled_template(args.source_type, args.identifier, args.add_param_space, args.vertical)

    args = build_legacy_parser().parse_args(args_list)
    return print_filled_template(args.source_type, args.identifier, args.add_param_space, args.vertical)


def build_fill_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wikipedia-template-filler fill")
    add_fill_arguments(parser)
    return parser


def build_sources_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wikipedia-template-filler sources")
    add_sources_arguments(parser)
    return parser


def print_filled_template(source_type: str, identifier: str, add_param_space: bool, vertical: bool) -> int:
    try:
        print(
            fill(
                source_type,
                identifier,
                add_param_space=add_param_space,
                vertical=vertical,
            )
        )
    except TemplateFillerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def print_sources(*, status: str | None = None) -> None:
    rows = [spec for spec in SUPPORTED_SOURCES if status is None or spec.status == status]
    widths = (
        max(len("source"), *(len(spec.source_type) for spec in rows)) if rows else len("source"),
        max(len("template"), *(len(spec.template) for spec in rows)) if rows else len("template"),
        max(len("status"), *(len(spec.status) for spec in rows)) if rows else len("status"),
    )
    print(f"{'source':<{widths[0]}}  {'template':<{widths[1]}}  {'status':<{widths[2]}}  aliases")
    print(f"{'-' * widths[0]}  {'-' * widths[1]}  {'-' * widths[2]}  -------")
    for spec in rows:
        print(
            f"{spec.source_type:<{widths[0]}}  "
            f"{spec.template:<{widths[1]}}  "
            f"{spec.status:<{widths[2]}}  "
            f"{', '.join(spec.aliases)}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
