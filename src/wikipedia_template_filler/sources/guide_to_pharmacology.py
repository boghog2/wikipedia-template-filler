"""IUPHAR/BPS Guide to Pharmacology (GtoPdb) ligand lookup helpers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from wikipedia_template_filler._http import USER_AGENT
from wikipedia_template_filler.api import TemplateFillerError

GTP_API_BASE = "https://www.guidetopharmacology.org/services"
GTP_API_KEY_ENV = "GTP_API_KEY"
GTPDB_API_KEY_ENV = "GTPDB_API_KEY"

JsonRequester = Callable[[Request], object]


class GuideToPharmacologyLookupError(TemplateFillerError):
    """Raised when an upstream GtoPdb lookup fails."""


def guide_to_pharmacology_ligand_id(
    *, pubchem_cid: str = "", inchikey: str = "", requester: JsonRequester | None = None
) -> str:
    """Return a GtoPdb ligand ID using PubChem CID, then InChIKey."""
    request_json = requester or fetch_json_request
    if pubchem_cid:
        ligand_id = first_ligand_id(request_json(ligand_request(pubchem_cid=pubchem_cid)))
        if ligand_id:
            return ligand_id
    if inchikey:
        return first_ligand_id(request_json(ligand_request(inchikey=inchikey)))
    return ""


def ligand_url(*, pubchem_cid: str = "", inchikey: str = "") -> str:
    """Build the documented GtoPdb ligand-list lookup URL."""
    if pubchem_cid:
        query = {"accession": pubchem_cid, "database": "PubChemCID"}
    elif inchikey:
        query = {"inchikey": inchikey}
    else:
        query = {}
    suffix = f"?{urlencode(query)}" if query else ""
    return f"{GTP_API_BASE}/ligands{suffix}"


def ligand_request(*, pubchem_cid: str = "", inchikey: str = "") -> Request:
    """Build a GtoPdb request with the optional registered-user API key."""
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    api_key = guide_to_pharmacology_api_key()
    if api_key:
        headers["GTP-API-Key"] = api_key
    return Request(ligand_url(pubchem_cid=pubchem_cid, inchikey=inchikey), headers=headers)


def guide_to_pharmacology_api_key() -> str:
    """Return the configured GtoPdb API key, accepting a compatibility alias."""
    return os.environ.get(GTP_API_KEY_ENV, "").strip() or os.environ.get(GTPDB_API_KEY_ENV, "").strip()


def fetch_json_request(request: Request) -> object:
    """Fetch one JSON response from the GtoPdb REST API."""
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GuideToPharmacologyLookupError(
            f"Guide to Pharmacology lookup failed: {exc.code} {exc.reason}"
        ) from exc
    except URLError as exc:
        raise GuideToPharmacologyLookupError(
            f"Guide to Pharmacology lookup failed: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise GuideToPharmacologyLookupError(
            "Guide to Pharmacology returned invalid JSON"
        ) from exc


def first_ligand_id(payload: object) -> str:
    """Return the first ligand ID from a GtoPdb ligand-list response."""
    if not isinstance(payload, list):
        return ""
    for record in payload:
        if not isinstance(record, Mapping):
            continue
        ligand_id = record.get("ligandId")
        if ligand_id is not None and str(ligand_id).strip():
            return str(ligand_id)
    return ""
