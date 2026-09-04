"""Small local web app for wikipedia-template-filler."""

from __future__ import annotations

import argparse
import html
import sys
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from xml.etree import ElementTree

from . import __version__, fill
from .api import SUPPORTED_SOURCES, SourceSpec, TemplateFiller, TemplateFillerError

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8780
XML_ERROR_MESSAGE = "Citation could not be generated, perhaps because the requested reference could not be found."

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



WEB_SOURCE_ORDER = (
    "pubmed_id",
    "pubmedcentral_id",
    "isbn",
    "pubchem_id",
    "pubchem_cid",
    "hgnc_id",
)
WEB_OPTIONS = (
    ("vertical", "Fill vertically"),
    ("extended", "Show extended fields"),
    ("add_param_space", "Pad parameter names and values"),
    ("add_ref_tag", "Add ref tag"),
    ("dont_use_etal", "Don't use et al. for author list"),
    ("omit_url_if_doi_filled", "Omit URL field if DOI field is populated (journals only)"),
    ("dont_strip_trailing_period", "Don't strip trailing period from article title"),
    ("full_journal_title", "Use full journal title"),
    ("link_journal", "Link journal title"),
    ("add_text_url", "Add URL (if available)"),
    ("add_accessdate", "Add access date (if relevant)"),
)


@dataclass(frozen=True)
class FillResult:
    """Result of applying web query parameters to the template filler."""

    source_type: str
    identifier: str
    options: dict[str, bool]
    output: str = ""
    error: str = ""


def supported_sources() -> tuple[SourceSpec, ...]:
    """Return sources that can currently generate templates."""
    return tuple(spec for spec in SUPPORTED_SOURCES if spec.status == "supported")


def ordered_web_sources() -> tuple[SourceSpec, ...]:
    """Return supported sources in the legacy web display order."""
    by_source_type = {spec.source_type: spec for spec in supported_sources()}
    return tuple(by_source_type[source_type] for source_type in WEB_SOURCE_ORDER if source_type in by_source_type)


def render_page(
    *,
    source_type: str = "pmid",
    identifier: str = "",
    add_param_space: bool = True,
    vertical: bool = False,
    output: str = "",
    error: str = "",
    option_values: dict[str, bool] | None = None,
) -> str:
    """Render the single-page web interface."""
    option_state = web_option_state(
        add_param_space=add_param_space,
        vertical=vertical,
        option_values=option_values,
    )
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
  --line: #ccccff;
  --panel: #eeeeff;
  --page: #eeeeff;
  --accent: #1f6f78;
  --accent-strong: #15545b;
  --danger: #9f2f2f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #fff;
  color: var(--ink);
}}
main {{
  margin: 5px;
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--page);
}}
header {{
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
  margin-bottom: 18px;
}}
h1 {{
  margin: 0;
  font-size: 16pt;
  line-height: 1.15;
  font-weight: 700;
}}
.version {{ color: var(--muted); font-size: 14px; }}
.runtime {{ margin-left: 8px; }}
.intro {{
  margin: -8px 0 18px;
  color: var(--muted);
  line-height: 1.45;
}}
form {{
  display: grid;
  grid-template-columns: minmax(150px, 220px) minmax(220px, 340px) auto;
  gap: 12px;
  align-items: end;
  padding: 18px;
  background: var(--panel);
  border: 0;
  border-radius: 0;
}}
label {{ display: grid; gap: 6px; font-weight: 600; font-size: 14px; }}
.identifier-field {{ max-width: 340px; }}
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
.submit-button {{
  justify-self: start;
  min-width: 0;
  padding: 0 8px;
}}
.options {{
  grid-column: 1 / -1;
  display: grid;
  gap: 6px;
  color: var(--muted);
}}
.options label {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
}}
.result {{
  margin: 0 0 18px;
  padding: 0 0 12px;
  border-top: 1px solid #ccc;
  border-bottom: 1px solid #ccc;
}}
.paste-label {{
  margin: 12px 0;
  font-weight: 700;
}}
textarea {{
  width: min(65%, 100%);
  min-height: 15em;
  resize: vertical;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #fff;
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
  width: min(65%, 100%);
  margin-top: 8px;
}}
.data-sources,
.compat-note,
.xml-output {{
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px solid #ccc;
}}
.data-sources {{
  overflow-x: auto;
}}
.data-sources h2,
.compat-note h2,
.xml-output h2 {{
  margin: 0 0 10px;
  font-size: 18px;
}}
.compat-note p,
.xml-output p {{
  margin: 0;
  color: var(--muted);
  line-height: 1.45;
}}
.data-sources table {{
  width: max-content;
  max-width: none;
  border-collapse: collapse;
  background: var(--panel);
  border: 2px solid var(--line);
  outline: 2px solid var(--line);
  outline-offset: -2px;
  border-radius: 8px;
  overflow: hidden;
}}
.data-sources th,
.data-sources td {{
  border-right: 2px solid var(--line);
  border-bottom: 2px solid var(--line);
  padding: 9px 10px;
  text-align: left;
  white-space: nowrap;
}}
.data-sources td {{
  font-size: 14px;
  line-height: 1.35;
}}
.data-sources td a,
.data-sources td code {{
  font: inherit;
}}
th {{
  color: var(--muted);
  text-align: center;
  font-size: 13px;
  font-weight: 700;
}}
.data-sources th:last-child,
.data-sources td:last-child {{ border-right: 0; }}
.data-sources tr:last-child td {{ border-bottom: 0; }}
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
    <div class="version">v{html.escape(__version__)} <span class="runtime">python</span></div>
  </header>
  {error_block(error)}
  {result_block(output)}
  <p class="intro">Enter an PubMed ID, PubMed Central ID, ISBN, PubChem CID, or HGNC ID and press Submit to fill out an appropriate template that can be pasted into a Wikipedia article:</p>
  <form method="get" action="/">
    <label>Source
      <select name="type">
        {source_options(source_type)}
      </select>
    </label>
    <label class="identifier-field">Identifier
      <input name="id" type="text" value="{html.escape(identifier)}" autocomplete="off" autofocus>
    </label>
    <button class="submit-button" type="submit">Submit</button>
    <div class="options">
      {option_controls(option_state)}
    </div>
  </form>
  {data_sources_table()}
  {old_url_compatibility_note()}
  {xml_output_note()}
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
    """Render option tags for supported sources, preserving unavailable selections."""
    options = []
    selected_unavailable = unavailable_selected_source(selected)
    if selected_unavailable is not None:
        value = SOURCE_VALUES.get(selected_unavailable.source_type, selected_unavailable.source_type)
        label = (
            f"{SOURCE_LABELS.get(selected_unavailable.source_type, selected_unavailable.source_type)} "
            f"-> {selected_unavailable.template} ({selected_unavailable.status})"
        )
        options.append(
            f'<option value="{html.escape(value)}" selected disabled>{html.escape(label)}</option>'
        )
    for spec in ordered_web_sources():
        value = SOURCE_VALUES.get(spec.source_type, spec.source_type)
        label = f"{SOURCE_LABELS.get(spec.source_type, spec.source_type)} -> {spec.template}"
        selected_attr = " selected" if selected_unavailable is None and selected in (value, spec.source_type, *spec.aliases) else ""
        options.append(f'<option value="{html.escape(value)}"{selected_attr}>{html.escape(label)}</option>')
    return "\n        ".join(options)


def unavailable_selected_source(selected: str) -> SourceSpec | None:
    """Return the selected source when it is known but cannot currently run."""
    try:
        spec = TemplateFiller().source_spec(selected)
    except TemplateFillerError:
        return None
    if spec.status == "supported":
        return None
    return spec


def data_sources_table() -> str:
    """Render a compact table of recognized legacy data sources."""
    rows = "\n".join(data_source_row(spec) for spec in ordered_web_sources())
    return f"""<section class="data-sources">
    <h2>Data sources</h2>
    <table>
      <thead><tr><th>Data source</th><th>Template</th><th>Example ID</th></tr></thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </section>"""


def old_url_compatibility_note() -> str:
    """Render legacy URL compatibility instructions."""
    return """<section class="compat-note">
    <h2>Old URL compatibility</h2>
    <p>Old Toolforge and Wikipedia talk-page links using <code>type</code> and <code>id</code> query parameters are still supported.</p>
  </section>"""


def xml_output_note() -> str:
    """Render legacy XML-output instructions."""
    return """<section class="xml-output">
    <h2>XML output</h2>
    <p>This tool can output XML in case you're interested in developing, for example, an Ajax interface to this page. Just add <code>&amp;format=xml</code> at the end of the URL.</p>
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


def web_option_state(
    *,
    add_param_space: bool,
    vertical: bool,
    option_values: dict[str, bool] | None = None,
) -> dict[str, bool]:
    """Return checkbox state for the legacy web options."""
    state = {name: False for name, _label in WEB_OPTIONS}
    state["add_param_space"] = add_param_space
    state["vertical"] = vertical
    if option_values:
        state.update({name: bool(value) for name, value in option_values.items() if name in state})
    return state


def option_controls(option_state: dict[str, bool]) -> str:
    """Render legacy option checkboxes in Perl web-interface order."""
    rows = []
    for name, label in WEB_OPTIONS:
        rows.append(
            f"<label><input type=\"checkbox\" name=\"{html.escape(name)}\" value=\"1\" {checked(option_state.get(name, False))}> {html.escape(label)}</label>"
        )
    return "\n      ".join(rows)


def checked(value: bool) -> str:
    """Return a checked attribute when value is truthy."""
    return "checked" if value else ""


def result_block(output: str) -> str:
    """Render citation output controls."""
    if not output:
        return ""
    escaped = html.escape(output)
    return f"""<section class="result">
    <p class="paste-label">Paste this into your article:</p>
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


def fill_request(
    params: dict[str, list[str]],
    *,
    fill_func: Callable[..., str] | None = None,
) -> FillResult:
    """Apply query parameters and return a fill result for HTML or XML."""
    source_type = query_value(params, "source_type", "type", default="pmid")
    identifier = query_value(params, "identifier", "id")
    options = renderer_options(params)
    output = ""
    error = ""

    if not identifier:
        error = "Enter an identifier."
    else:
        try:
            live_fill = fill if fill_func is None else fill_func
            output = live_fill(
                source_type,
                identifier,
                **options,
            )
            if options["add_ref_tag"]:
                output = f"<ref>{output}</ref>"
        except TemplateFillerError as exc:
            error = str(exc)

    return FillResult(
        source_type=source_type,
        identifier=identifier,
        options=options,
        output=output,
        error=error,
    )


def render_fill_page(
    params: dict[str, list[str]],
    *,
    fill_func: Callable[..., str] | None = None,
) -> str:
    """Render the filled-template page for web and WSGI entry points."""
    result = fill_request(params, fill_func=fill_func)
    return render_page(
        source_type=result.source_type,
        identifier=result.identifier,
        add_param_space=result.options["add_param_space"],
        vertical=result.options["vertical"],
        output=result.output,
        error=result.error,
        option_values=result.options,
    )


def is_xml_request(params: dict[str, list[str]]) -> bool:
    """Return true when the query asks for legacy XML output."""
    return query_value(params, "format").lower() == "xml"


def render_xml_response(
    params: dict[str, list[str]],
    *,
    fill_func: Callable[..., str] | None = None,
) -> str:
    """Render a Perl-compatible XML response for ``format=xml`` requests."""
    result = fill_request(params, fill_func=fill_func)
    root = ElementTree.Element("wikitool", {"application": "cite"})
    query = ElementTree.SubElement(root, "query")
    identifier = ElementTree.SubElement(query, "id", {"type": result.source_type})
    identifier.text = result.identifier

    response = ElementTree.SubElement(root, "response", {"status": "ok" if result.output else "error"})
    if result.output:
        ElementTree.SubElement(response, "source")
        content = ElementTree.SubElement(response, "content", {"template": xml_template_name(result.source_type)})
        content.text = result.output
        paramlist = ElementTree.SubElement(response, "paramlist")
        for name, values in params.items():
            for value in values:
                param = ElementTree.SubElement(paramlist, "param", {"name": name})
                param.text = value
    else:
        error = ElementTree.SubElement(response, "error")
        error.text = result.error or XML_ERROR_MESSAGE

    ElementTree.indent(root, space="  ")
    return "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n" + ElementTree.tostring(root, encoding="unicode") + "\n"


def xml_template_name(source_type: str) -> str:
    """Return the legacy Template:Name label for a source type."""
    try:
        template = TemplateFiller().source_spec(source_type).template
    except TemplateFillerError:
        return ""
    return f"Template:{template[:1].upper()}{template[1:]}"


def make_handler() -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to the template-filler API."""

    class TemplateFillerHandler(BaseHTTPRequestHandler):
        server_version = f"WikipediaTemplateFiller/{__version__}"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/fill", "/cgi-bin/index.cgi"}:
                params = parse_qs(parsed.query)
                if is_xml_request(params):
                    self.respond_xml(render_xml_response(params))
                elif parsed.path == "/" and not params:
                    self.respond_html(render_page())
                else:
                    self.handle_fill(params)
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def handle_fill(self, params: dict[str, list[str]]) -> None:
            self.respond_html(render_fill_page(params))

        def respond_html(self, body: str) -> None:
            self.respond(body, "text/html; charset=utf-8")

        def respond_xml(self, body: str) -> None:
            self.respond(body, "application/xml; charset=utf-8")

        def respond(self, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
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
