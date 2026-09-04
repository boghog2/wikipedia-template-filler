"""HGNC lookup through the public genenames.org REST API."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from wikipedia_template_filler.api import TemplateFillerError
from wikipedia_template_filler.renderer import render_template

HGNC_REST_BASE = "https://rest.genenames.org"


class SourceLookupError(TemplateFillerError):
    """Raised when an upstream HGNC lookup fails."""


JsonFetcher = Callable[[str], str]


@dataclass(frozen=True)
class HgncGene:
    """Normalized HGNC gene data used for protein infobox rendering."""

    name: str
    hgnc_id: str
    symbol: str
    previous_symbols: tuple[str, ...]
    entrez_gene: str
    omim: str
    refseq: str
    uniprot: str
    chromosome: str
    arm: str
    band: str


def fill_hgnc(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return an infobox protein template for an HGNC ID."""
    hgnc_id = normalize_hgnc_id(identifier)
    if not hgnc_id:
        raise SourceLookupError("no HGNC ID given")

    payload = (json_fetcher or fetch_json)(hgnc_url(hgnc_id))
    gene = parse_hgnc_response(payload, expected_hgnc_id=hgnc_id)
    return render_template(
        "infobox protein",
        gene_fields(gene),
        add_param_space=bool(options.get("add_param_space", False)),
        vertical=True,
        include_empty=bool(options.get("extended", False)),
    )


def normalize_hgnc_id(identifier: str) -> str:
    """Return the numeric part of an HGNC identifier."""
    match = re.search(r"(?:HGNC:\s*)?(\d+)", identifier, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def hgnc_url(hgnc_id: str) -> str:
    """Build the public HGNC REST API URL for hgnc_id."""
    return HGNC_REST_BASE + "/fetch/hgnc_id/" + quote("HGNC:" + hgnc_id)


def fetch_json(url: str) -> str:
    """Fetch JSON from url using the standard library."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "wikipedia-template-filler/0.2.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise SourceLookupError(f"HGNC lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SourceLookupError(f"HGNC lookup failed: {exc.reason}") from exc


def parse_hgnc_response(payload: str, *, expected_hgnc_id: str | None = None) -> HgncGene:
    """Parse one HGNC REST JSON response into normalized gene data."""
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SourceLookupError("HGNC returned invalid JSON") from exc

    docs = data.get("response", {}).get("docs", [])
    if not docs:
        raise SourceLookupError(f"no gene matches the given HGNC ID ({expected_hgnc_id})")

    doc = docs[0]
    hgnc_id = normalize_hgnc_id(str(doc.get("hgnc_id", "")))
    if expected_hgnc_id and hgnc_id != expected_hgnc_id:
        raise SourceLookupError(f"no gene matches the given HGNC ID ({expected_hgnc_id})")

    chromosome, arm, band = split_location(str(doc.get("location", "")))
    return HgncGene(
        name=str(doc.get("name", "")),
        hgnc_id=hgnc_id,
        symbol=str(doc.get("symbol", "")),
        previous_symbols=tuple(doc.get("prev_symbol", []) or []),
        entrez_gene=str(doc.get("entrez_id", "")),
        omim=first_value(doc.get("omim_id")),
        refseq=strip_accession_version(first_value(doc.get("refseq_accession"))),
        uniprot=first_value(doc.get("uniprot_ids")),
        chromosome=chromosome,
        arm=arm,
        band=band,
    )


def gene_fields(gene: HgncGene) -> list[tuple[str, str]]:
    """Return ordered infobox protein fields for an HGNC gene."""
    return [
        ("name", gene.name),
        ("caption", ""),
        ("image", ""),
        ("width", ""),
        ("HGNCid", gene.hgnc_id),
        ("Symbol", gene.symbol),
        ("AltSymbols", ", ".join(gene.previous_symbols)),
        ("EntrezGene", gene.entrez_gene),
        ("OMIM", gene.omim),
        ("RefSeq", gene.refseq),
        ("UniProt", gene.uniprot),
        ("PDB", ""),
        ("ECnumber", ""),
        ("Chromosome", gene.chromosome),
        ("Arm", gene.arm),
        ("Band", gene.band),
        ("LocusSupplementaryData", ""),
    ]


def first_value(value: object) -> str:
    """Return the first scalar value from a JSON string/list field."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return "" if value is None else str(value)


def strip_accession_version(value: str) -> str:
    """Drop RefSeq version suffixes, matching the Perl fixture output."""
    return re.sub(r"\.\d+$", "", value)


def split_location(location: str) -> tuple[str, str, str]:
    """Split an HGNC cytogenetic location such as 11q13.3."""
    match = re.match(r"^(\d+|X|Y|MT)([pq])?(.*)$", location, flags=re.IGNORECASE)
    if not match:
        return location, "", ""
    chromosome, arm, band = match.groups()
    return chromosome, arm or "", band or ""
