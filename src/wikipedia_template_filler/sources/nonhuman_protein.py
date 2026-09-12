"""Non-human protein lookup through UniProt and NCBI Gene."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from wikipedia_template_filler._http import USER_AGENT
from wikipedia_template_filler._ncbi import ncbi_query_params
from wikipedia_template_filler.api import TemplateFillerError
from wikipedia_template_filler.renderer import render_template

NCBI_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"


class SourceLookupError(TemplateFillerError):
    """Raised when an upstream non-human protein lookup fails."""


JsonFetcher = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class NonhumanProtein:
    """Normalized non-human protein data used for infobox rendering."""

    name: str
    organism: str
    tax_id: str
    symbol: str
    alt_symbols: str
    entrez_gene: str
    homologene: str
    pdb: str
    refseq_mrna: str
    refseq_protein: str
    uniprot: str
    ec_number: str
    chromosome: str
    entrez_chromosome: str
    genloc_start: str
    genloc_end: str


def fill_uniprot(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return an ``{{infobox nonhuman protein}}`` template for a UniProt accession."""
    accession = normalize_uniprot(identifier)
    if not accession:
        raise SourceLookupError("no UniProt accession given")

    fetcher = json_fetcher or fetch_json
    payload = fetcher(uniprot_url(accession))
    protein = parse_uniprot_response(payload, expected_accession=accession)
    if protein.entrez_gene:
        gene = parse_ncbi_gene_response(fetcher(ncbi_gene_url(protein.entrez_gene)), expected_gene_id=protein.entrez_gene)
        protein = merge_protein_data(protein, gene)
    return render_nonhuman_protein(protein, **options)


def fill_ncbi_gene(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return an ``{{infobox nonhuman protein}}`` template for an NCBI Gene ID."""
    gene_id = normalize_gene_id(identifier)
    if not gene_id:
        raise SourceLookupError("no NCBI Gene ID given")

    fetcher = json_fetcher or fetch_json
    gene = parse_ncbi_gene_response(fetcher(ncbi_gene_url(gene_id)), expected_gene_id=gene_id)
    accession = parse_uniprot_search_response(fetcher(uniprot_gene_search_url(gene_id)))
    if accession:
        protein = parse_uniprot_response(fetcher(uniprot_url(accession)), expected_accession=accession)
        gene = merge_protein_data(protein, gene)
    return render_nonhuman_protein(gene, **options)


def normalize_uniprot(identifier: str) -> str:
    """Return a UniProt accession-like token."""
    value = re.sub(r"^\s*(?:UniProt(?:KB)?|accession)\s*:\s*", "", identifier, flags=re.IGNORECASE)
    match = re.search(r"([A-Z0-9][A-Z0-9_-]{1,14})", value.strip(), flags=re.IGNORECASE)
    return match.group(1).upper().replace("_", "-") if match else ""


def normalize_gene_id(identifier: str) -> str:
    """Return digits only for an NCBI Gene identifier."""
    return re.sub(r"\D", "", identifier)


def uniprot_url(accession: str) -> str:
    """Build the UniProtKB JSON URL for *accession*."""
    return f"{UNIPROT_BASE}/{quote(accession)}.json"


def uniprot_gene_search_url(gene_id: str) -> str:
    """Build a UniProtKB search URL for reviewed entries cross-referenced to an NCBI Gene ID."""
    query = urlencode(
        {
            "query": f"(xref:GeneID-{gene_id}) AND (reviewed:true)",
            "fields": "accession",
            "format": "json",
            "size": "1",
        }
    )
    return f"{UNIPROT_BASE}/search?{query}"


def ncbi_gene_url(gene_id: str) -> str:
    """Build the NCBI Gene esummary URL for *gene_id*."""
    query = urlencode(ncbi_query_params({"db": "gene", "id": gene_id, "retmode": "json"}))
    return f"{NCBI_EUTILS_BASE}/esummary.fcgi?{query}"


def fetch_json(url: str) -> Mapping[str, Any]:
    """Fetch JSON from *url* using the standard library."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SourceLookupError(f"non-human protein lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SourceLookupError(f"non-human protein lookup failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SourceLookupError("non-human protein source returned invalid JSON") from exc


def parse_uniprot_response(payload: Mapping[str, Any], *, expected_accession: str | None = None) -> NonhumanProtein:
    """Parse one UniProtKB JSON response into normalized infobox data."""
    accession = str(payload.get("primaryAccession", ""))
    if expected_accession and accession.upper() != expected_accession.upper():
        raise SourceLookupError(f"no UniProt entry matches the given accession ({expected_accession})")

    organism = payload.get("organism", {})
    protein_name = nested_value(payload, "proteinDescription", "recommendedName", "fullName", "value")
    gene = first_mapping(payload.get("genes"))
    refs = cross_references(payload)
    refseq = first_refseq(refs)
    return NonhumanProtein(
        name=protein_name,
        organism=format_organism(str(organism.get("scientificName", "")), str(organism.get("commonName", "")) if isinstance(organism, Mapping) else ""),
        tax_id=str(organism.get("taxonId", "")) if isinstance(organism, Mapping) else "",
        symbol=nested_value(gene, "geneName", "value"),
        alt_symbols=", ".join(nested_value(item, "value") for item in as_list(gene.get("synonyms")) if nested_value(item, "value")),
        entrez_gene=first_cross_reference(refs, "GeneID"),
        homologene=first_cross_reference(refs, "HomoloGene"),
        pdb=", ".join(cross_reference_ids(refs, "PDB")),
        refseq_mrna=strip_accession_version(refseq[0]),
        refseq_protein=strip_accession_version(refseq[1]),
        uniprot=accession,
        ec_number=nested_value(payload, "proteinDescription", "recommendedName", "ecNumbers", 0, "value"),
        chromosome="",
        entrez_chromosome="",
        genloc_start="",
        genloc_end="",
    )


def parse_ncbi_gene_response(payload: Mapping[str, Any], *, expected_gene_id: str | None = None) -> NonhumanProtein:
    """Parse one NCBI Gene esummary JSON response into normalized infobox data."""
    result = payload.get("result", {})
    uid = first_value(result.get("uids")) if isinstance(result, Mapping) else ""
    gene_id = expected_gene_id or uid
    doc = result.get(gene_id) if isinstance(result, Mapping) else None
    if not isinstance(doc, Mapping):
        raise SourceLookupError(f"no NCBI Gene record matches the given Gene ID ({gene_id})")

    if expected_gene_id and str(doc.get("uid", "")) != expected_gene_id:
        raise SourceLookupError(f"no NCBI Gene record matches the given Gene ID ({expected_gene_id})")

    organism = doc.get("organism", {})
    genomic = first_mapping(doc.get("genomicinfo"))
    return NonhumanProtein(
        name=str(doc.get("description", "")),
        organism=format_organism(str(organism.get("scientificname", "")), str(organism.get("commonname", "")) if isinstance(organism, Mapping) else ""),
        tax_id=str(organism.get("taxid", "")) if isinstance(organism, Mapping) else "",
        symbol=str(doc.get("nomenclaturesymbol") or doc.get("name") or ""),
        alt_symbols=str(doc.get("otheraliases", "")),
        entrez_gene=str(doc.get("uid", "")),
        homologene="",
        pdb="",
        refseq_mrna="",
        refseq_protein="",
        uniprot="",
        ec_number="",
        chromosome=str(doc.get("chromosome", "")),
        entrez_chromosome=str(genomic.get("chraccver", "")),
        genloc_start=str(genomic.get("chrstart", "")),
        genloc_end=str(genomic.get("chrstop", "")),
    )


def parse_uniprot_search_response(payload: Mapping[str, Any]) -> str:
    """Return the first accession from a UniProt search response."""
    first = first_mapping(payload.get("results"))
    return str(first.get("primaryAccession", ""))


def merge_protein_data(primary: NonhumanProtein, supplemental: NonhumanProtein) -> NonhumanProtein:
    """Fill blank UniProt-derived fields with NCBI Gene data."""
    return NonhumanProtein(
        **{
            field: getattr(primary, field) or getattr(supplemental, field)
            for field in primary.__dataclass_fields__
        }
    )


def render_nonhuman_protein(protein: NonhumanProtein, **options: object) -> str:
    """Render normalized data as an ``{{infobox nonhuman protein}}`` template."""
    return render_template(
        "Infobox nonhuman protein",
        nonhuman_protein_fields(protein),
        add_param_space=bool(options.get("add_param_space", False)),
        vertical=True,
        include_empty=bool(options.get("extended", False)),
    )


def nonhuman_protein_fields(protein: NonhumanProtein) -> list[tuple[str, str]]:
    """Return ordered ``{{infobox nonhuman protein}}`` fields."""
    return [
        ("Name", protein.name),
        ("image", ""),
        ("width", ""),
        ("caption", ""),
        ("Organism", protein.organism),
        ("TaxID", protein.tax_id),
        ("Symbol", protein.symbol),
        ("AltSymbols", protein.alt_symbols),
        ("ATC_prefix", ""),
        ("ATC_suffix", ""),
        ("ATC_supplemental", ""),
        ("CAS_number", ""),
        ("CAS_supplemental", ""),
        ("DrugBank", ""),
        ("EntrezGene", protein.entrez_gene),
        ("HomoloGene", protein.homologene),
        ("PDB", protein.pdb),
        ("RefSeqmRNA", protein.refseq_mrna),
        ("RefSeqProtein", protein.refseq_protein),
        ("UniProt", protein.uniprot),
        ("ECnumber", protein.ec_number),
        ("Chromosome", protein.chromosome),
        ("EntrezChromosome", protein.entrez_chromosome),
        ("GenLoc_start", protein.genloc_start),
        ("GenLoc_end", protein.genloc_end),
    ]


def nested_value(data: object, *path: object) -> str:
    """Return a nested scalar value from mappings/lists."""
    value = data
    for key in path:
        if isinstance(key, int) and isinstance(value, list) and len(value) > key:
            value = value[key]
        elif isinstance(value, Mapping):
            value = value.get(key)
        else:
            return ""
    return "" if value is None or isinstance(value, (Mapping, list)) else str(value)


def first_mapping(value: object) -> Mapping[str, Any]:
    """Return the first mapping in a list-like API field."""
    if isinstance(value, list) and value and isinstance(value[0], Mapping):
        return value[0]
    if isinstance(value, Mapping):
        return value
    return {}


def as_list(value: object) -> list[Any]:
    """Return value as a list."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def first_value(value: object) -> str:
    """Return the first scalar value from a list or scalar."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return "" if value is None else str(value)


def cross_references(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return UniProt cross-reference mappings."""
    refs = payload.get("uniProtKBCrossReferences", [])
    return [ref for ref in refs if isinstance(ref, Mapping)] if isinstance(refs, list) else []


def cross_reference_ids(refs: list[Mapping[str, Any]], database: str) -> list[str]:
    """Return all IDs for a UniProt cross-reference database."""
    return [str(ref.get("id", "")) for ref in refs if ref.get("database") == database and ref.get("id")]


def first_cross_reference(refs: list[Mapping[str, Any]], database: str) -> str:
    """Return the first ID for a UniProt cross-reference database."""
    values = cross_reference_ids(refs, database)
    return values[0] if values else ""


def first_refseq(refs: list[Mapping[str, Any]]) -> tuple[str, str]:
    """Return the first UniProt RefSeq mRNA/protein pair."""
    for ref in refs:
        if ref.get("database") != "RefSeq":
            continue
        protein = str(ref.get("id", ""))
        mrna = property_value(ref, "NucleotideSequenceId")
        if mrna or protein:
            return mrna, protein
    return "", ""


def property_value(ref: Mapping[str, Any], key: str) -> str:
    """Return one UniProt cross-reference property value."""
    for item in as_list(ref.get("properties")):
        if isinstance(item, Mapping) and item.get("key") == key:
            return str(item.get("value", ""))
    return ""


def strip_accession_version(value: str) -> str:
    """Drop accession version suffixes for Wikipedia infobox fields."""
    return re.sub(r"\.\d+$", "", value)


def format_organism(scientific_name: str, common_name: str = "") -> str:
    """Return a Wikipedia-style organism label."""
    scientific_name = scientific_name.strip()
    common_name = common_name.strip()
    if scientific_name and common_name:
        return f"''{scientific_name}'' ({common_name})"
    if scientific_name:
        return f"''{scientific_name}''"
    return common_name
