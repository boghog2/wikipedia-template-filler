"""Wikidata enrichment helpers for source modules."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlencode

WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

JsonFetcher = Callable[[str], Mapping[str, Any]]


def enrich_drug_identifiers(
    identifiers: Mapping[str, str],
    *,
    pubchem_cid: str = "",
    inchikey: str = "",
    fetcher: JsonFetcher,
) -> dict[str, str]:
    """Fill blank drug identifiers from Wikidata using PubChem CID or InChIKey."""
    enriched = dict(identifiers)
    if not pubchem_cid and not inchikey:
        return enriched
    wikidata_identifiers = parse_drug_identifier_response(
        fetcher(drug_identifier_url(pubchem_cid=pubchem_cid, inchikey=inchikey))
    )
    for key, value in wikidata_identifiers.items():
        if value and not enriched.get(key):
            enriched[key] = value
    return enriched


def drug_identifier_url(*, pubchem_cid: str = "", inchikey: str = "") -> str:
    """Build a Wikidata SPARQL URL for a drug identifier lookup."""
    match_patterns = []
    if pubchem_cid:
        match_patterns.append(f"?item wdt:P662 {sparql_string(pubchem_cid)}.")
    if inchikey:
        match_patterns.append(f"?item wdt:P235 {sparql_string(inchikey)}.")
    query = f"""
SELECT ?item ?inchikey ?pubchem ?chemspider ?iuphar ?drugbank ?chebi ?chembl ?unii WHERE {{
  {" UNION ".join("{ " + pattern + " }" for pattern in match_patterns)}
  OPTIONAL {{ ?item wdt:P235 ?inchikey. }}
  OPTIONAL {{ ?item wdt:P662 ?pubchem. }}
  OPTIONAL {{ ?item wdt:P661 ?chemspider. }}
  OPTIONAL {{ ?item wdt:P595 ?iuphar. }}
  OPTIONAL {{ ?item wdt:P715 ?drugbank. }}
  OPTIONAL {{ ?item wdt:P683 ?chebi. }}
  OPTIONAL {{ ?item wdt:P592 ?chembl. }}
  OPTIONAL {{ ?item wdt:P652 ?unii. }}
}}
LIMIT 1
""".strip()
    return f"{WIKIDATA_SPARQL_ENDPOINT}?{urlencode({'query': query, 'format': 'json'})}"


def sparql_string(value: str) -> str:
    """Return a quoted SPARQL string literal."""
    return json.dumps(value)


def parse_drug_identifier_response(payload: Mapping[str, Any]) -> dict[str, str]:
    """Return drug identifiers from a Wikidata SPARQL JSON response."""
    bindings = payload.get("results", {}).get("bindings", [])
    first = bindings[0] if isinstance(bindings, list) and bindings else {}
    if not isinstance(first, Mapping):
        first = {}
    return {
        "inchikey": wikidata_binding(first, "inchikey"),
        "pubchem": wikidata_binding(first, "pubchem"),
        "chemspider": wikidata_binding(first, "chemspider"),
        "iuphar_ligand": wikidata_binding(first, "iuphar"),
        "drug_bank": wikidata_binding(first, "drugbank"),
        "chebi": normalize_prefixed_identifier(wikidata_binding(first, "chebi"), "CHEBI:"),
        "chembl": normalize_prefixed_identifier(wikidata_binding(first, "chembl"), "CHEMBL"),
        "unii": wikidata_binding(first, "unii"),
    }


def wikidata_binding(binding: Mapping[str, Any], name: str) -> str:
    """Return one SPARQL binding value."""
    value = binding.get(name, {})
    return str(value.get("value", "")) if isinstance(value, Mapping) else ""


def normalize_prefixed_identifier(value: str, prefix: str) -> str:
    """Strip an optional external-ID prefix from values that templates expect bare."""
    return value[len(prefix):] if value.upper().startswith(prefix) else value
