"""Optional RSC ChemSpider lookup helpers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from wikipedia_template_filler._http import USER_AGENT
from wikipedia_template_filler.api import TemplateFillerError

CHEMSPIDER_API_BASE = "https://api.rsc.org/compounds/v1"
RSC_API_KEY_ENV = "RSC_API_KEY"
CHEMSPIDER_API_KEY_ENV = "CHEMSPIDER_API_KEY"

JsonRequester = Callable[[Request], Mapping[str, Any]]


class ChemSpiderLookupError(TemplateFillerError):
    """Raised when optional ChemSpider lookup fails."""


def chemspider_id_from_inchikey(inchikey: str, *, requester: JsonRequester | None = None) -> str:
    """Return the first ChemSpider record ID for an InChIKey, if configured."""
    api_key = rsc_api_key()
    if not inchikey or not api_key:
        return ""
    request_json = requester or fetch_json_request
    query_payload = request_json(inchikey_filter_request(inchikey, api_key=api_key))
    query_id = str(query_payload.get("queryId", ""))
    if not query_id:
        return ""
    results_payload = request_json(query_results_request(query_id, api_key=api_key))
    return first_result_id(results_payload)


def rsc_api_key() -> str:
    """Return the configured RSC ChemSpider API key."""
    return os.environ.get(RSC_API_KEY_ENV, "").strip() or os.environ.get(CHEMSPIDER_API_KEY_ENV, "").strip()


def inchikey_filter_request(inchikey: str, *, api_key: str) -> Request:
    """Build the ChemSpider InChIKey filter request."""
    body = json.dumps({"inchikey": inchikey}).encode("utf-8")
    return Request(
        f"{CHEMSPIDER_API_BASE}/filter/inchikey",
        data=body,
        headers=chemspider_headers(api_key),
        method="POST",
    )


def query_results_request(query_id: str, *, api_key: str) -> Request:
    """Build the ChemSpider query results request."""
    return Request(
        f"{CHEMSPIDER_API_BASE}/filter/{query_id}/results",
        headers=chemspider_headers(api_key),
        method="GET",
    )


def chemspider_headers(api_key: str) -> dict[str, str]:
    """Return headers used for RSC ChemSpider requests."""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "apikey": api_key,
    }


def fetch_json_request(request: Request) -> Mapping[str, Any]:
    """Fetch one JSON response from an RSC ChemSpider request."""
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ChemSpiderLookupError(f"ChemSpider lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise ChemSpiderLookupError(f"ChemSpider lookup failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ChemSpiderLookupError("ChemSpider returned invalid JSON") from exc


def first_result_id(payload: Mapping[str, Any]) -> str:
    """Return the first ChemSpider result ID from a results payload."""
    results = payload.get("results", [])
    if isinstance(results, list) and results:
        return str(results[0])
    return ""
