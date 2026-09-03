"""Small local web app for wikipedia-template-filler."""

from __future__ import annotations

import argparse
import html
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from . import __version__, fill
from .api import SUPPORTED_SOURCES, SourceSpec, TemplateFillerError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8780

SOURCE_VALUES = {
    "pubmed_id": "pubmed_id",
    "pubmedcentral_id": "pubmedcentral_id",
    "hgnc_id": "hgnc_id",
    "isbn": "isbn",
    "pubchem_cid": "pubchem",
    "pubchem_id": "pubchem_id",
    "url": "url",
    "drugbank_id": "drugbank_id",
}
SOURCE_LABELS = {
    "drugbank_id": "DrugBank ID",
    "hgnc_id": "HGNC ID",
    "isbn": "ISBN",
    "pubmed_id": "PubMed ID",
    "pubmedcentral_id": "PubMed Central ID",
    "pubchem_cid": "PubChem CID",
    "pubchem_id": "PubChem CID",
    "url": "URL",
}
SOURCE_EXAMPLES = {
    "drugbank_id": "DB00328",
    "hgnc_id": "12403",
    "isbn": "0-7216-5944-6",
    "pubmed_id": "123455",
    "pubmedcentral_id": "137841",
    "pubchem_cid": "2244",
    "pubchem_id": "2244",
    "url": "http://en.wikipedia.org",
}



def supported_sources() -> tuple[SourceSpec, ...]:
    """Return sources that can currently generate templates."""
    return tuple(spec for spec in SUPPORTED_SOURCES if spec.status == "supported")


def render_page(
    *,
    source_type: str = "pmid",
    identifier: str = "",
    add_param_space: bool = True,
    vertical: bool = False,
    output: str = "",
    error: str = "",
) -> str:
    """Render the single-page web interface."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wikipedia Template Filler</title>
<style>
:root {{
  color-scheme: light;
  --ink: #18212f;
  --muted: #5e6a78;
  --line: #d9dee7;
  --panel: #ffffff;
  --page: #f6f7f9;
  --accent: #1f6f78;
  --accent-strong: #15545b;
  --danger: #9f2f2f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--page);
  color: var(--ink);
}}
main {{
  width: min(980px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 32px 0;
}}
header {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  margin-bottom: 22px;
}}
h1 {{
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
}}
.version {{ color: var(--muted); font-size: 14px; }}
form {{
  display: grid;
  grid-template-columns: minmax(150px, 220px) minmax(220px, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 18px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}}
label {{ display: grid; gap: 6px; font-weight: 600; font-size: 14px; }}
select,
input[type="text"] {{
  width: 100%;
  min-height: 42px;
  border: 1px solid #b7c0cc;
  border-radius: 6px;
  padding: 8px 10px;
  font: inherit;
  background: #fff;
  color: var(--ink);
}}
button {{
  min-height: 42px;
  border: 0;
  border-radius: 6px;
  padding: 0 16px;
  font: inherit;
  font-weight: 700;
  color: #fff;
  background: var(--accent);
  cursor: pointer;
}}
button:hover {{ background: var(--accent-strong); }}
.options {{
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  color: var(--muted);
}}
.options label {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}}
.result {{ margin-top: 18px; }}
textarea {{
  width: 100%;
  min-height: 180px;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--panel);
  color: var(--ink);
}}
.error {{
  margin-top: 18px;
  border-left: 4px solid var(--danger);
  padding: 12px 14px;
  background: #fff4f4;
  color: #6f1f1f;
}}
.copy-row {{
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}}
.data-sources {{
  margin-top: 18px;
  overflow-x: auto;
}}
.data-sources h2 {{
  margin: 0 0 10px;
  font-size: 18px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}}
th, td {{
  border-bottom: 1px solid var(--line);
  padding: 9px 10px;
  text-align: left;
  white-space: nowrap;
}}
th {{
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}}
tr:last-child td {{ border-bottom: 0; }}
.status-pending, .status-unsupported {{ color: var(--muted); }}
.secondary {{ background: #435062; }}
.secondary:hover {{ background: #303b4b; }}
@media (max-width: 760px) {{
  header {{ display: block; }}
  form {{ grid-template-columns: 1fr; }}
  button {{ width: 100%; }}
}}
</style>
</head>
<body>
<main>
  <header>
    <h1>Wikipedia Template Filler</h1>
    <div class="version">v{html.escape(__version__)}</div>
  </header>
  <form method="get" action="/">
    <label>Source
      <select name="type">
        {source_options(source_type)}
      </select>
    </label>
    <label>Identifier
      <input name="id" type="text" value="{html.escape(identifier)}" autocomplete="off" autofocus>
    </label>
    <button type="submit">Fill</button>
    <div class="options">
      <label><input type="checkbox" name="add_param_space" value="1" {checked(add_param_space)}> Parameter spacing</label>
      <label><input type="checkbox" name="vertical" value="1" {checked(vertical)}> Vertical output</label>
    </div>
  </form>
  {data_sources_table()}
  {result_block(output)}
  {error_block(error)}
</main>
<script>
const copyButton = document.querySelector('[data-copy-output]');
if (copyButton) {{
  copyButton.addEventListener('click', async () => {{
    const output = document.querySelector('#output');
    await navigator.clipboard.writeText(output.value);
    copyButton.textContent = 'Copied';
    setTimeout(() => copyButton.textContent = 'Copy', 1200);
  }});
}}
</script>
</body>
</html>
"""


def source_options(selected: str) -> str:
    """Render option tags for supported sources."""
    options = []
    for spec in supported_sources():
        value = SOURCE_VALUES.get(spec.source_type, spec.source_type)
        label = f"{SOURCE_LABELS.get(spec.source_type, spec.source_type)} -> {spec.template}"
        selected_attr = " selected" if selected in (value, spec.source_type, *spec.aliases) else ""
        options.append(f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>')
    return "\n        ".join(options)


def data_sources_table() -> str:
    """Render a compact table of recognized legacy data sources."""
    rows = "\n".join(data_source_row(spec) for spec in supported_sources())
    return f"""<section class="data-sources">
    <h2>Data sources</h2>
    <table>
      <thead><tr><th>Data source</th><th>Template</th><th>Example ID</th></tr></thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </section>"""


def data_source_row(spec: SourceSpec) -> str:
    """Render one data-source table row."""
    label = SOURCE_LABELS.get(spec.source_type, spec.source_type)
    value = SOURCE_VALUES.get(spec.source_type, spec.source_type)
    example = SOURCE_EXAMPLES.get(spec.source_type, "")
    href = example_href(spec)
    return (
        f"<tr class=\"status-{html.escape(spec.status)}\">"
        f"<td>{html.escape(label)}</td>"
        f"<td><code>{{{{{html.escape(spec.template)}}}}}</code></td>"
        f"<td><a href=\"{html.escape(href, quote=True)}\"><code>{html.escape(example)}</code></a></td>"
        "</tr>"
    )


def example_href(spec: SourceSpec) -> str:
    """Return a fill URL for a table example using legacy query names."""
    query = {
        "type": SOURCE_VALUES.get(spec.source_type, spec.source_type),
        "id": SOURCE_EXAMPLES.get(spec.source_type, ""),
        "add_param_space": "1",
    }
    if spec.source_type == "pubchem_id":
        query["add_iupac_name"] = "1"
    return f"/?{urlencode(query)}"


def checked(value: bool) -> str:
    """Return a checked attribute when value is truthy."""
    return "checked" if value else ""


def result_block(output: str) -> str:
    """Render citation output controls."""
    if not output:
        return ""
    escaped = html.escape(output)
    return f"""<section class="result">
    <textarea id="output" readonly>{escaped}</textarea>
    <div class="copy-row"><button class="secondary" type="button" data-copy-output>Copy</button></div>
  </section>"""


def error_block(error: str) -> str:
    """Render an error message."""
    if not error:
        return ""
    return f'<div class="error">{html.escape(error)}</div>'


def query_flag(params: dict[str, list[str]], name: str, default: bool = False) -> bool:
    """Return a checkbox-style boolean query parameter."""
    if name not in params:
        return default
    return params[name][-1].lower() not in {"", "0", "false", "off"}


def query_value(params: dict[str, list[str]], *names: str, default: str = "") -> str:
    """Return the last non-empty value for the first matching query name."""
    for name in names:
        values = params.get(name)
        if values:
            value = values[-1].strip()
            if value:
                return value
    return default


def renderer_options(params: dict[str, list[str]]) -> dict[str, bool]:
    """Return renderer flags accepted by the legacy CGI query string."""
    flag_names = (
        "vertical",
        "extended",
        "add_param_space",
        "add_ref_tag",
        "dont_use_etal",
        "omit_url_if_doi_filled",
        "dont_strip_trailing_period",
        "full_journal_title",
        "link_journal",
        "add_text_url",
        "add_accessdate",
        "add_iupac_name",
    )
    options = {name: query_flag(params, name) for name in flag_names}
    options["add_param_space"] = query_flag(params, "add_param_space", default=True)
    return options


def make_handler() -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the template-filler API."""

    class TemplateFillerHandler(BaseHTTPRequestHandler):
        server_version = f"WikipediaTemplateFiller/{__version__}"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/fill", "/cgi-bin/index.cgi"}:
                params = parse_qs(parsed.query)
                if parsed.path == "/" and not params:
                    self.respond_html(render_page())
                else:
                    self.handle_fill(params)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def handle_fill(self, params: dict[str, list[str]]) -> None:
            source_type = query_value(params, "source_type", "type", default="pmid")
            identifier = query_value(params, "identifier", "id")
            options = renderer_options(params)
            add_param_space = options["add_param_space"]
            vertical = options["vertical"]
            output = ""
            error = ""

            if not identifier:
                error = "Enter an identifier."
            else:
                try:
                    output = fill(
                        source_type,
                        identifier,
                        **options,
                    )
                except TemplateFillerError as exc:
                    error = str(exc)

            self.respond_html(
                render_page(
                    source_type=source_type,
                    identifier=identifier,
                    add_param_space=add_param_space,
                    vertical=vertical,
                    output=output,
                    error=error,
                )
            )

        def respond_html(self, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}", file=sys.stderr)

    return TemplateFillerHandler


def run(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the local web server until interrupted."""
    server = ThreadingHTTPServer((host, port), make_handler())
    url = f"http://{host}:{server.server_port}/"
    print(f"Serving wikipedia-template-filler at {url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping web server.", file=sys.stderr)
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the wikipedia-template-filler local web app.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="host interface to bind")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="port to bind")
    args = parser.parse_args(argv)
    run(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
