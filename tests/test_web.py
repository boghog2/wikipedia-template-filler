import contextlib
import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from wikipedia_template_filler import web


class WebAppTests(unittest.TestCase):
    def test_render_page_lists_supported_sources(self):
        page = web.render_page(source_type="hgnc", identifier="HGNC:1582")
        self.assertIn("Wikipedia Template Filler", page)
        self.assertIn('<div class="version">v0.2.0 <span class="runtime">python</span></div>', page)
        self.assertIn("Enter an PubMed ID, PubMed Central ID, ISBN, PubChem CID, or HGNC ID", page)
        self.assertIn("PubMed ID -&gt; cite journal", page)
        self.assertIn("PubMed Central ID -&gt; cite journal", page)
        self.assertIn("HGNC ID -&gt; infobox protein", page)
        self.assertIn("PubChem CID -&gt; infobox drug", page)
        self.assertIn("PubChem CID -&gt; chembox", page)
        self.assertIn('option value="pubmed_id"', page)
        self.assertIn('option value="pubmedcentral_id"', page)
        self.assertIn('option value="hgnc_id" selected', page)
        self.assertIn("option value=\"pubchem_id\"", page)
        self.assertIn("select name=\"type\"", page)
        self.assertIn("input name=\"id\"", page)
        self.assertIn('<label class="identifier-field">Identifier', page)
        self.assertIn(".identifier-field { max-width: 340px; }", page)
        self.assertIn('<button class="submit-button" type="submit">Submit</button>', page)
        self.assertIn(".submit-button {", page)
        self.assertIn("padding: 0 8px;", page)
        self.assertIn("name=\"add_param_space\"", page)
        self.assertIn("Pad parameter names and values (cite and protein templates only)", page)
        self.assertIn("name=\"vertical\"", page)
        self.assertIn("Fill vertically (cite templates only)", page)
        self.assertIn(".options {", page)
        self.assertIn("display: grid;", page)
        self.assertIn("gap: 6px;", page)
        self.assertIn("Show extended fields (cite and protein templates only)", page)
        self.assertIn("Add ref tag (cite templates only)", page)
        self.assertIn("Omit URL field if DOI field is populated (cite journal only)", page)
        self.assertIn("Don&#x27;t strip trailing period from article title (cite journal only)", page)
        self.assertIn("Use full journal title (cite journal only)", page)
        self.assertIn("Link journal title (cite journal only)", page)
        self.assertIn("Add URL (cite journal only)", page)
        self.assertIn("Add access date (cite journal URL only)", page)
        self.assertIn("Data sources", page)
        self.assertIn("Old URL compatibility", page)
        self.assertIn("Old Toolforge and Wikipedia talk-page links", page)
        self.assertIn("XML output", page)
        self.assertIn("&amp;format=xml", page)
        self.assertIn("{{cite journal}}", page)
        self.assertIn("{{chembox}}", page)
        self.assertIn("href=\"/?type=pubchem_id&amp;id=2244&amp;add_param_space=1&amp;add_iupac_name=1\"", page)
        self.assertIn("<a href=\"/?type=pubmed_id&amp;id=123455&amp;add_param_space=1\"><code>123455</code></a>", page)
        self.assertIn("<a href=\"/?type=isbn&amp;id=0-7216-5944-6&amp;add_param_space=1\"><code>0-7216-5944-6</code></a>", page)
        self.assertNotIn("<code>drugbank_id</code>", page)
        self.assertNotIn("<code>url</code>", page)
        self.assertNotIn("<option value=\"drugbank_id\"", page)

    def test_render_page_orders_data_source_rows(self):
        page = web.render_page()
        expected = [
            "<td>PubMed ID</td><td><code>{{cite journal}}</code></td>",
            "<td>PubMed Central ID</td><td><code>{{cite journal}}</code></td>",
            "<td>ISBN</td><td><code>{{cite book}}</code></td>",
            "<td>PubChem CID</td><td><code>{{chembox}}</code></td>",
            "<td>PubChem CID</td><td><code>{{infobox drug}}</code></td>",
            "<td>HGNC ID</td><td><code>{{infobox protein}}</code></td>",
        ]
        positions = [page.index(row) for row in expected]
        self.assertEqual(positions, sorted(positions))

    def test_render_page_orders_source_dropdown_like_data_table(self):
        page = web.render_page()
        expected = [
            "PubMed ID -&gt; cite journal",
            "PubMed Central ID -&gt; cite journal",
            "ISBN -&gt; cite book",
            "PubChem CID -&gt; chembox",
            "PubChem CID -&gt; infobox drug",
            "HGNC ID -&gt; infobox protein",
        ]
        positions = [page.index(label) for label in expected]
        self.assertEqual(positions, sorted(positions))


    def test_render_page_orders_options_like_perl_form(self):
        page = web.render_page(option_values={"add_ref_tag": True, "link_journal": True})
        expected = [label.replace("\x27", "&#x27;") for _name, label in web.WEB_OPTIONS]
        positions = [page.index(label) for label in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('name="add_ref_tag" value="1" checked', page)
        self.assertIn('name="link_journal" value="1" checked', page)

    def test_render_page_escapes_output_and_errors(self):
        page = web.render_page(output="{{cite journal|title=<bad>}}", error="x < y")
        self.assertIn("&lt;bad&gt;", page)
        self.assertIn("x &lt; y", page)

    def test_render_page_places_output_above_form_like_legacy_cgi(self):
        page = web.render_page(output="{{cite journal}}")
        self.assertIn("Paste this into your article:", page)
        self.assertLess(page.index("Paste this into your article:"), page.index('<form method="get" action="/">'))
        self.assertLess(page.index('<textarea id="output"'), page.index('<form method="get" action="/">'))

    def test_render_page_aligns_copy_button_with_output_box(self):
        page = web.render_page(output="{{cite journal}}")
        self.assertIn(".copy-row {", page)
        self.assertIn("width: min(65%, 100%);", page)
        self.assertLess(page.index(".copy-row {"), page.index(".data-sources {"))

    def test_render_page_uses_legacy_wrapper_background(self):
        page = web.render_page()
        self.assertIn("--page: #eeeeff;", page)
        self.assertIn("border: 1px solid var(--line);", page)

    def test_render_page_uses_thin_legacy_section_separators(self):
        page = web.render_page(output="{{cite journal}}")
        self.assertIn("border-top: 1px solid #ccc;", page)
        self.assertIn("border-bottom: 1px solid #ccc;", page)
        self.assertIn(".data-sources {", page)
        self.assertIn("padding-top: 12px;", page)

    def test_render_page_centers_table_headings(self):
        page = web.render_page()
        self.assertIn("th {", page)
        self.assertIn("text-align: center;", page)

    def test_render_page_uses_vertical_data_source_table_lines(self):
        page = web.render_page()
        self.assertIn("border-right: 2px solid var(--line);", page)
        self.assertIn(".data-sources td:last-child { border-right: 0; }", page)

    def test_render_page_uses_outer_data_source_table_border(self):
        page = web.render_page()
        self.assertIn("outline: 2px solid var(--line);", page)
        self.assertIn("outline-offset: -2px;", page)

    def test_render_page_standardizes_data_source_cell_text(self):
        page = web.render_page()
        self.assertIn(".data-sources td {", page)
        self.assertIn("font-size: 14px;", page)
        self.assertIn(".data-sources td code {", page)
        self.assertIn("font: inherit;", page)

    def test_render_page_sizes_data_sources_table_to_contents(self):
        page = web.render_page()
        self.assertIn(".data-sources table {", page)
        self.assertIn("width: max-content;", page)
        self.assertIn("white-space: nowrap;", page)

    def test_render_page_preserves_pending_selection(self):
        page = web.render_page(source_type="url", identifier="https://example.org")
        self.assertIn('<option value="url" selected disabled>URL -&gt; cite web (pending)</option>', page)
        self.assertNotIn('<option value="url">', page)

    def test_render_page_preserves_unsupported_selection(self):
        page = web.render_page(source_type="drugbank_id", identifier="DB00338")
        self.assertIn('<option value="drugbank_id" selected disabled>DrugBank ID -&gt; drugbox (unsupported)</option>', page)
        self.assertNotIn('<option value="drugbank_id">', page)

    def test_query_flag_defaults_and_false_values(self):
        self.assertTrue(web.query_flag({}, "add_param_space", default=True))
        self.assertFalse(web.query_flag({"vertical": ["0"]}, "vertical"))
        self.assertTrue(web.query_flag({"vertical": ["1"]}, "vertical"))

    def test_fill_route_renders_api_output(self):
        body = self.fetch(
            "/fill?source_type=pmid&identifier=18535242&add_param_space=1",
            fill_result="{{cite journal}}",
        )
        self.assertIn("{{cite journal}}", body)
        self.assertIn('value="18535242"', body)

    def test_fill_route_adds_ref_tag_when_requested(self):
        body = self.fetch(
            "/fill?source_type=pmid&identifier=18535242&add_ref_tag=1",
            fill_result="{{cite journal}}",
        )
        self.assertIn("&lt;ref&gt;{{cite journal}}&lt;/ref&gt;", body)

    def test_fill_route_does_not_add_ref_tag_to_infoboxes(self):
        body = self.fetch(
            "/fill?source_type=hgnc_id&identifier=12403&add_ref_tag=1",
            fill_result="{{infobox protein}}",
        )
        self.assertIn("{{infobox protein}}", body)
        self.assertNotIn("&lt;ref&gt;{{infobox protein}}&lt;/ref&gt;", body)

    def test_fill_route_renders_missing_identifier_error(self):
        body = self.fetch("/fill?source_type=pmid")
        self.assertIn("Enter an identifier.", body)

    def test_legacy_query_names_fill_from_root_path(self):
        body = self.fetch(
            "/?ddb=&type=pubmed_id&id=18535242&add_param_space=1&add_ref_tag=1&full_journal_title=1",
            fill_result="{{cite journal}}",
        )
        self.assertIn("{{cite journal}}", body)
        self.assertIn("value=\"18535242\"", body)

    def test_legacy_cgi_path_is_accepted(self):
        body = self.fetch("/cgi-bin/index.cgi?type=pubchem_id&id=2244", fill_result="{{chembox}}")
        self.assertIn("{{chembox}}", body)

    def test_xml_format_returns_legacy_xml_response(self):
        status, headers, body = self.fetch_response(
            "/cgi-bin/index.cgi?type=pubmed_id&id=123455&format=xml&add_param_space=1",
            fill_result="{{cite journal|title=A & B}}",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertIn("<?xml version=\"1.0\" encoding=\"utf-8\"?>", body)
        self.assertIn("<wikitool application=\"cite\">", body)
        self.assertIn("<id type=\"pubmed_id\">123455</id>", body)
        self.assertIn("<response status=\"ok\">", body)
        self.assertIn("<content template=\"Template:Cite journal\">{{cite journal|title=A &amp; B}}</content>", body)
        self.assertIn("<param name=\"format\">xml</param>", body)

    def test_xml_format_returns_error_response(self):
        status, headers, body = self.fetch_response("/cgi-bin/index.cgi?type=pubmed_id&format=xml")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertIn("<response status=\"error\">", body)
        self.assertIn("<error>Enter an identifier.</error>", body)


    def test_pending_legacy_url_renders_clear_error(self):
        body = self.fetch("/?type=url&id=https%3A%2F%2Fexample.org", fill_result=None)
        self.assertIn("URL -&gt; {{cite web}} lookup is recognized", body)
        self.assertIn('<option value="url" selected disabled>URL -&gt; cite web (pending)</option>', body)

    def test_unsupported_legacy_url_renders_clear_error(self):
        body = self.fetch("/?type=drugbank_id&id=DB00338", fill_result=None)
        self.assertIn("DrugBank/drugbox lookup is currently unsupported", body)
        self.assertIn('<option value="drugbank_id" selected disabled>DrugBank ID -&gt; drugbox (unsupported)</option>', body)

    def fetch_response(self, path: str, fill_result: str | None = "") -> tuple[int, dict[str, str], str]:
        server = ThreadingHTTPServer((web.DEFAULT_HOST, 0), web.make_handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        patch_context = (
            contextlib.nullcontext()
            if fill_result is None
            else mock.patch("wikipedia_template_filler.web.fill", return_value=fill_result)
        )
        try:
            with patch_context:
                connection = http.client.HTTPConnection(web.DEFAULT_HOST, server.server_port, timeout=5)
                connection.request("GET", path)
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        return response.status, dict(response.getheaders()), body

    def fetch(self, path: str, fill_result: str | None = "") -> str:
        status, _headers, body = self.fetch_response(path, fill_result=fill_result)
        self.assertEqual(status, 200)
        return body


if __name__ == "__main__":
    unittest.main()
