#!/usr/bin/env python3
"""Verify local Guide to Pharmacology credential and live lookup access."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if sys.version_info < (3, 10):
    version = ".".join(str(part) for part in sys.version_info[:3])
    print(f"FAIL: Python 3.10 or newer is required; this is Python {version}.", file=sys.stderr)
    print("Use: /usr/local/bin/python3 scripts/test-iuphar.py", file=sys.stderr)
    raise SystemExit(1)

from wikipedia_template_filler.api import TemplateFillerError  # noqa: E402
from wikipedia_template_filler.sources.guide_to_pharmacology import (  # noqa: E402
    guide_to_pharmacology_ligand_id,
    ligand_request,
)


def main() -> int:
    if not os.environ.get("GTP_API_KEY", "").strip():
        print("FAIL: GTP_API_KEY is not available in this shell.", file=sys.stderr)
        print("Run: source ~/.zshrc", file=sys.stderr)
        return 1

    request = ligand_request(pubchem_cid="2244")
    if not request.get_header("Gtp-api-key"):
        print("FAIL: the API-key header was not attached.", file=sys.stderr)
        return 1
    print("PASS: the API-key header is attached (value hidden).")

    try:
        ligand_id = guide_to_pharmacology_ligand_id(pubchem_cid="2244")
    except TemplateFillerError as exc:
        print(f"FAIL: live Guide to Pharmacology lookup failed: {exc}", file=sys.stderr)
        return 1

    if ligand_id != "4139":
        print(f"FAIL: expected aspirin ligand ID 4139; received {ligand_id or 'no match'}.", file=sys.stderr)
        return 1

    print("PASS: live aspirin lookup returned IUPHAR ligand ID 4139.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
