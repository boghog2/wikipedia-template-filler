"""Run live smoke checks for supported sources.

Use this before deployment to check upstream public APIs. The implementation
lives in wikipedia_template_filler.cli so the script and CLI command stay in
sync.
"""

from __future__ import annotations

from wikipedia_template_filler.cli import build_smoke_parser, print_smoke_cases, run_smoke_cases


def main() -> int:
    args = build_smoke_parser().parse_args()
    if args.list:
        print_smoke_cases()
        return 0
    return run_smoke_cases()


if __name__ == "__main__":
    raise SystemExit(main())
