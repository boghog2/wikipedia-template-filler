import runpy
import unittest
from pathlib import Path
from unittest import mock

from wikipedia_template_filler import wsgi


class WsgiAppTests(unittest.TestCase):
    def test_root_page_renders(self):
        status, headers, body = self.call_app("/")
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("Wikipedia Template Filler", body)
        self.assertIn("Data sources", body)

    def test_legacy_cgi_url_renders_filled_template(self):
        with mock.patch("wikipedia_template_filler.web.fill", return_value="{{cite journal}}") as fake_fill:
            status, headers, body = self.call_app(
                "/cgi-bin/index.cgi",
                "type=pubmed_id&id=123455&add_param_space=1",
            )
        self.assertEqual(status, "200 OK")
        self.assertIn("{{cite journal}}", body)
        fake_fill.assert_called_once()
        self.assertEqual(fake_fill.call_args.args[:2], ("pubmed_id", "123455"))

    def test_fill_route_renders_filled_template(self):
        with mock.patch("wikipedia_template_filler.web.fill", return_value="{{cite journal}}") as fake_fill:
            status, headers, body = self.call_app(
                "/fill",
                "source_type=pmid&identifier=18535242&add_param_space=1",
            )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("Paste this into your article:", body)
        self.assertIn("{{cite journal}}", body)
        fake_fill.assert_called_once()
        self.assertEqual(fake_fill.call_args.args[:2], ("pmid", "18535242"))
        self.assertTrue(fake_fill.call_args.kwargs["add_param_space"])

    def test_fill_route_renders_missing_identifier_error(self):
        status, headers, body = self.call_app("/fill", "source_type=pmid")
        self.assertEqual(status, "200 OK")
        self.assertIn("Enter an identifier.", body)

    def test_legacy_cgi_url_renders_xml(self):
        with mock.patch("wikipedia_template_filler.web.fill", return_value="{{cite journal}}") as fake_fill:
            status, headers, body = self.call_app(
                "/cgi-bin/index.cgi",
                "type=pubmed_id&id=123455&format=xml&add_param_space=1",
            )
        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertIn("<wikitool application=\"cite\">", body)
        self.assertIn("<content template=\"Template:Cite journal\">{{cite journal}}</content>", body)
        fake_fill.assert_called_once()

    def test_head_has_headers_without_body(self):
        status, headers, body = self.call_app("/", method="HEAD")
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, "")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_unknown_path_returns_not_found(self):
        status, headers, body = self.call_app("/missing")
        self.assertEqual(status, "404 Not Found")
        self.assertIn("Not found", body)

    def test_unsupported_method_returns_method_not_allowed(self):
        status, headers, body = self.call_app("/", method="POST")
        self.assertEqual(status, "405 Method Not Allowed")
        self.assertEqual(headers["Allow"], "GET, HEAD")
        self.assertIn("Method not allowed", body)

    def test_toolforge_app_py_exports_wsgi_app(self):
        app_path = Path(__file__).resolve().parent.parent / "app.py"
        namespace = runpy.run_path(str(app_path), run_name="toolforge_app_test")
        self.assertIs(namespace["app"], wsgi.app)

    def call_app(
        self,
        path: str,
        query_string: str = "",
        method: str = "GET",
    ) -> tuple[str, dict[str, str], str]:
        captured = {}

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: object = None,
        ) -> None:
            captured["status"] = status
            captured["headers"] = dict(headers)

        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
        }
        body = b"".join(wsgi.app(environ, start_response)).decode("utf-8")
        return captured["status"], captured["headers"], body


if __name__ == "__main__":
    unittest.main()
