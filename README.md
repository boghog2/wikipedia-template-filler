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

Run live smoke checks against supported upstream sources before deployment:

```bash
wikipedia-template-filler smoke --list
wikipedia-template-filler smoke
python3 scripts/smoke_supported_sources.py
```

Check old Toolforge-style URLs against a running web app before deployment:

```bash
python3 scripts/check_toolforge_compatibility.py --base-url http://127.0.0.1:8780
python3 scripts/check_toolforge_compatibility.py --base-url https://citation-template-filling.toolforge.org
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

## Deployment / Toolforge

Toolforge Python webservices expect a WSGI callable named `app` under `$HOME/www/python/src/app.py` and load Python packages from `$HOME/www/python/venv`. The exact service command should match the active Toolforge Python runtime; the current Toolforge examples use `python3.13`.

A conservative deployment pass is:

```bash
ssh login.toolforge.org
become citation-template-filling
cd $HOME/www/python/src
git pull
source $HOME/www/python/venv/bin/activate
python -m pip install -e .
python -m pytest
wikipedia-template-filler smoke
toolforge webservice python3.13 restart
toolforge webservice status
```

After the service is running, check that old Wikipedia links still resolve through the compatibility URLs:

```bash
python3 scripts/check_toolforge_compatibility.py --base-url https://citation-template-filling.toolforge.org
```

If startup fails, inspect `$HOME/uwsgi.log`. See the Toolforge docs for [Python webservices](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Web/Python) and the general [`toolforge webservice`](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Web) command.

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

PubChem CID lookup is implemented through PubChem PUG REST and can generate either Infobox drug or the legacy Chembox:

```bash
wikipedia-template-filler pubchem 2244 --add-param-space
wikipedia-template-filler chembox 2244
```

HGNC lookup is implemented through the public genenames.org REST API:

```bash
wikipedia-template-filler hgnc HGNC:1582 --add-param-space
```

DrugBank/drugbox is explicitly unsupported.

The local web app accepts legacy CGI-style query parameters used by old links, such as `/?type=pubmed_id&id=18535242&add_param_space=1` and `/?type=pubchem_id&id=2244`. The newer `/fill?source_type=pmid&identifier=18535242` form remains supported too.

## Initial Porting Order

1. Template renderer and golden fixture tests
2. ISBN via Open Library
3. PubMed/PMC via NCBI E-utilities
4. HGNC via HGNC REST API
5. PubChem CID via PubChem PUG REST
6. Explicit unsupported behavior for DrugBank/drugbox
