# wikipedia-template-filler

Python port of `WWW::Wikipedia::TemplateFiller`, a tool for generating Wikipedia citation and infobox template markup from public identifiers.

This repository is intentionally starting small. The maintained Perl fork remains the behavioral reference while the Python implementation grows source by source.

## Development

Create a virtual environment and install the package in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```

## Current Status

ISBN lookup is implemented through the Open Library Books API:

```bash
PYTHONPATH=src python3 -m wikipedia_template_filler.cli isbn 0721659446 --add-param-space
```

HGNC, PubMed, and PMC are recognized by the public API but have not been ported yet. DrugBank/drugbox is explicitly unsupported.

## Initial Porting Order

1. Template renderer and golden fixture tests
2. ISBN via Open Library
3. HGNC via HGNC REST API
4. PubMed/PMC via NCBI E-utilities
5. Explicit unsupported behavior for DrugBank/drugbox
