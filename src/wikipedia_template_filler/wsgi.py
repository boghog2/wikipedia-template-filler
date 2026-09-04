"""WSGI entry point for Toolforge and other Python webservers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from http import HTTPStatus
from urllib.parse import parse_qs

from .web import is_xml_request, render_fill_page, render_page, render_xml_response

ROUTES = {"/", "/fill", "/cgi-bin/index.cgi"}


def app(environ: dict[str, object], start_response: Callable[..., object]) -> Iterable[bytes]:
    """Serve the template-filler web interface as a WSGI application."""
    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    if method not in {"GET", "HEAD"}:
        return respond(
            start_response,
            HTTPStatus.METHOD_NOT_ALLOWED,
            "Method not allowed",
            method,
            headers=[("Allow", "GET, HEAD")],
        )

    path = str(environ.get("PATH_INFO", "/") or "/")
    query_string = str(environ.get("QUERY_STRING", ""))
    if path not in ROUTES:
        return respond(start_response, HTTPStatus.NOT_FOUND, "Not found", method)

    params = parse_qs(query_string)
    if is_xml_request(params):
        body = render_xml_response(params)
        return respond(start_response, HTTPStatus.OK, body, method, content_type="application/xml; charset=utf-8")
    if path == "/" and not params:
        body = render_page()
    else:
        body = render_fill_page(params)
    return respond(start_response, HTTPStatus.OK, body, method)


def respond(
    start_response: Callable[..., object],
    status: HTTPStatus,
    body: str,
    method: str,
    *,
    headers: list[tuple[str, str]] | None = None,
    content_type: str = "text/html; charset=utf-8",
) -> Iterable[bytes]:
    data = body.encode("utf-8")
    response_headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(data))),
    ]
    if headers:
        response_headers.extend(headers)
    start_response(f"{status.value} {status.phrase}", response_headers)
    if method == "HEAD":
        return []
    return [data]
