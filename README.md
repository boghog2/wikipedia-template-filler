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

List recognized sources:

```bash
wikipedia-template-filler sources
wikipedia-template-filler sources --status supported
```

Generate a template:

```bash
wikipedia-template-filler fill pmid 18535242 --add-param-space
```

The legacy positional form also works:

```bash
wikipedia-template-filler pmid 18535242 --add-param-space
```

Run the local web app:

```bash
wikipedia-template-filler-web --port 8780
```

Then open `http://127.0.0.1:8780/`.

## Current Status

ISBN lookup is implemented through the Open Library Books API:

```bash
wikipedia-template-filler isbn 0721659446 --add-param-space
```

PubMed and PubMed Central lookup are implemented through NCBI E-utilities:

```bash
wikipedia-template-filler pmid 18535242 --add-param-space
wikipedia-template-filler pmc 137841 --add-param-space
```

HGNC is recognized by the public API but has not been ported yet. DrugBank/drugbox is explicitly unsupported.

## Initial Porting Order

1. Template renderer and golden fixture tests
2. ISBN via Open Library
3. HGNC via HGNC REST API
4. PubMed/PMC via NCBI E-utilities
5. Explicit unsupported behavior for DrugBank/drugbox
