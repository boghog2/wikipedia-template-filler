import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest import mock

from wikipedia_template_filler import web


class WebAppTests(unittest.TestCase):
    def test_render_page_lists_supported_sources(self):
        page = web.render_page(source_type="pmc", identifier="137841")
        self.assertIn("Wikipedia Template Filler", page)
        self.assertIn('option value="pmid"', page)
        self.assertIn('option value="pmc" selected', page)
        self.assertIn('option value="isbn"', page)
        self.assertNotIn("drugbank_id", page)

    def test_render_page_escapes_output_and_errors(self):
        page = web.render_page(output="{{cite journal|title=<bad>}}", error="x < y")
        self.assertIn("&lt;bad&gt;", page)
        self.assertIn("x &lt; y", page)

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

    def test_fill_route_renders_missing_identifier_error(self):
        body = self.fetch("/fill?source_type=pmid")
        self.assertIn("Enter an identifier.", body)

    def fetch(self, path: str, fill_result: str = "") -> str:
        server = ThreadingHTTPServer((web.DEFAULT_HOST, 0), web.make_handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch("wikipedia_template_filler.web.fill", return_value=fill_result):
                connection = http.client.HTTPConnection(web.DEFAULT_HOST, server.server_port, timeout=5)
                connection.request("GET", path)
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        self.assertEqual(response.status, 200)
        return body


if __name__ == "__main__":
    unittest.main()
