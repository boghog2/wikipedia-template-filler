"""PubChem lookup for infobox drug templates."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from wikipedia_template_filler.api import TemplateFillerError

PUBCHEM_PUG_REST_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTY_NAMES = (
    "MolecularFormula",
    "MolecularWeight",
    "IsomericSMILES",
    "CanonicalSMILES",
    "ConnectivitySMILES",
    "SMILES",
    "InChI",
    "InChIKey",
    "IUPACName",
)


class SourceLookupError(TemplateFillerError):
    """Raised when an upstream PubChem lookup fails."""


JsonFetcher = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class PubChemCompound:
    """Normalized PubChem compound data used for drug infobox rendering."""

    cid: str
    title: str
    molecular_formula: str
    molecular_weight: str
    smiles: str
    inchi: str
    inchikey: str
    iupac_name: str
    cas: str
    chebi: str
    chembl: str
    drug_bank: str
    kegg: str
    unii: str


def fill_pubchem(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return an Infobox drug template for a PubChem CID."""
    compound = lookup_pubchem_compound(identifier, json_fetcher=json_fetcher)
    return render_drug_template(compound)


def fill_pubchem_chembox(identifier: str, *, json_fetcher: JsonFetcher | None = None, **options: object) -> str:
    """Return a Chembox template for a PubChem CID."""
    compound = lookup_pubchem_compound(identifier, json_fetcher=json_fetcher)
    return render_chembox_template(compound, add_iupac_name=bool(options.get("add_iupac_name", True)))


def lookup_pubchem_compound(identifier: str, *, json_fetcher: JsonFetcher | None = None) -> PubChemCompound:
    """Fetch normalized PubChem data for a CID-like identifier."""
    cid = normalize_cid(identifier)
    if not cid:
        raise SourceLookupError("no PubChem CID given")
    return fetch_pubchem_compound(cid, fetcher=json_fetcher or fetch_json)


def normalize_cid(identifier: str) -> str:
    """Return digits only for a PubChem CID."""
    match = re.search(r"(\d+)", identifier)
    return match.group(1) if match else ""


def property_url(cid: str) -> str:
    properties = ",".join(PROPERTY_NAMES)
    return f"{PUBCHEM_PUG_REST_BASE}/compound/cid/{quote(cid)}/property/{properties}/JSON"


def synonyms_url(cid: str) -> str:
    return f"{PUBCHEM_PUG_REST_BASE}/compound/cid/{quote(cid)}/synonyms/JSON"


def xrefs_url(cid: str) -> str:
    return f"{PUBCHEM_PUG_REST_BASE}/compound/cid/{quote(cid)}/xrefs/RegistryID,SourceName/JSON"


def fetch_json(url: str) -> Mapping[str, Any]:
    request = Request(url, headers={"User-Agent": "wikipedia-template-filler/0.2.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SourceLookupError(f"PubChem lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SourceLookupError(f"PubChem lookup failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SourceLookupError("PubChem returned invalid JSON") from exc


def fetch_pubchem_compound(cid: str, *, fetcher: JsonFetcher) -> PubChemCompound:
    properties = parse_property_response(fetcher(property_url(cid)), expected_cid=cid)
    synonyms = parse_synonyms_response(fetcher(synonyms_url(cid)))
    identifiers = registry_identifiers(synonyms, fetcher(xrefs_url(cid)))
    return PubChemCompound(
        cid=cid,
        title=first_synonym(synonyms),
        molecular_formula=str(properties.get("MolecularFormula", "")),
        molecular_weight=str(properties.get("MolecularWeight", "")),
        smiles=str(properties.get("IsomericSMILES") or properties.get("CanonicalSMILES") or properties.get("SMILES") or properties.get("ConnectivitySMILES") or ""),
        inchi=str(properties.get("InChI", "")),
        inchikey=str(properties.get("InChIKey", "")),
        iupac_name=str(properties.get("IUPACName", "")),
        cas=identifiers["cas"],
        chebi=identifiers["chebi"],
        chembl=identifiers["chembl"],
        drug_bank=identifiers["drug_bank"],
        kegg=identifiers["kegg"],
        unii=identifiers["unii"],
    )


def parse_property_response(payload: Mapping[str, Any], *, expected_cid: str | None = None) -> Mapping[str, Any]:
    properties = payload.get("PropertyTable", {}).get("Properties", [])
    if not isinstance(properties, list) or not properties:
        raise SourceLookupError(f"no compound matches the given PubChem CID ({expected_cid})")
    record = properties[0]
    if not isinstance(record, Mapping):
        raise SourceLookupError("PubChem returned an invalid property record")
    if expected_cid and str(record.get("CID", "")) != expected_cid:
        raise SourceLookupError(f"no compound matches the given PubChem CID ({expected_cid})")
    return record


def parse_synonyms_response(payload: Mapping[str, Any]) -> list[str]:
    information = payload.get("InformationList", {}).get("Information", [])
    if not isinstance(information, list) or not information:
        return []
    first = information[0]
    synonyms = first.get("Synonym", []) if isinstance(first, Mapping) else []
    return [str(item) for item in synonyms] if isinstance(synonyms, list) else []


def first_synonym(synonyms: list[str]) -> str:
    return synonyms[0] if synonyms else ""


def registry_identifiers(synonyms: list[str], xrefs: Mapping[str, Any]) -> dict[str, str]:
    identifiers = {
        "cas": first_matching_group(synonyms, r"^(\d{2,7}-\d{2}-\d)$"),
        "chebi": first_matching_group(synonyms, r"^CHEBI:(\d+)$"),
        "chembl": first_matching_group(synonyms, r"^CHEMBL(\d+)$"),
        "drug_bank": first_matching_group(synonyms, r"^(DB\d{5})$"),
        "kegg": first_matching_group(synonyms, r"^(D\d{5})$"),
        "unii": first_matching_group(synonyms, r"^(?:UNII[-:\s])?([A-Z0-9]{10})$"),
    }
    identifiers["chembl"] = identifiers["chembl"] or registry_id_from_xrefs(xrefs, ("ChEMBL",), r"^CHEMBL(\d+)$")
    identifiers["drug_bank"] = identifiers["drug_bank"] or registry_id_from_xrefs(xrefs, ("DrugBank",), r"^(DB\d{5})$")
    identifiers["unii"] = identifiers["unii"] or registry_id_from_xrefs(xrefs, ("FDA Global Substance Registration System", "GSRS"), r"^([A-Z0-9]{10})$")
    return identifiers


def first_matching_group(values: list[str], pattern: str) -> str:
    regex = re.compile(pattern)
    for value in values:
        match = regex.match(value)
        if match:
            return match.group(1)
    return ""


def registry_id_from_xrefs(xrefs: Mapping[str, Any], source_names: tuple[str, ...], pattern: str) -> str:
    information = xrefs.get("InformationList", {}).get("Information", [])
    if not isinstance(information, list):
        return ""
    regex = re.compile(pattern)
    for info in information:
        if not isinstance(info, Mapping):
            continue
        sources = as_list(info.get("SourceName"))
        registry_ids = as_list(info.get("RegistryID"))
        candidates: list[str] = []
        if len(sources) == len(registry_ids):
            candidates.extend(registry_id for source, registry_id in zip(sources, registry_ids) if any(source_name in source for source_name in source_names))
        elif any(source_name in source for source in sources for source_name in source_names):
            candidates.extend(registry_ids)
        info_id = info.get("ID")
        if info_id is not None and any(source_name in source for source in sources for source_name in source_names):
            candidates.append(str(info_id))
        for candidate in candidates:
            match = regex.match(candidate)
            if match:
                return match.group(1)
    return ""


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value is None:
        return []
    return [str(value)]


def compound_fields(compound: PubChemCompound) -> list[tuple[str, str]]:
    return [
        ("drug_name", compound.title),
        ("INN", ""),
        ("type", "<!-- empty -->"),
        ("image", ""),
        ("image_class", "skin-invert-image"),
        ("width", ""),
        ("alt", ""),
        ("caption", ""),
        ("CAS_number", compound.cas),
        ("PubChem", compound.cid),
        ("IUPHAR_ligand", ""),
        ("DrugBank", compound.drug_bank),
        ("ChemSpiderID", ""),
        ("UNII", compound.unii),
        ("KEGG", compound.kegg),
        ("ChEBI", compound.chebi),
        ("ChEMBL", compound.chembl),
        ("synonyms", ""),
        ("IUPAC_name", f"<nowiki>{compound.iupac_name}</nowiki>" if compound.iupac_name else ""),
        ("chemical_formula", compound.molecular_formula),
        ("molecular_weight", compound.molecular_weight),
        ("SMILES", compound.smiles),
        ("Jmol", ""),
        ("StdInChI", compound.inchi),
        ("StdInChI_comment", ""),
        ("StdInChIKey", compound.inchikey),
    ]


ELEMENT_FIELDS = (
    "C", "H", "Ag", "Al", "As", "Au", "B", "Bi", "Br", "Ca", "Cl", "Co", "F", "Fe", "Gd", "I",
    "K", "Li", "Mg", "Mn", "N", "Na", "O", "P", "Pt", "S", "Sb", "Se", "Sr", "Tc", "Zn", "charge",
)

DRUG_TEMPLATE_LINES = (
    "drug_name", "INN", "type", "image", "image_class", "width", "alt", "caption",
    "image2", "image_class2", "width2", "alt2", "caption2", "imageL", "image_classL", "widthL", "altL",
    "imageR", "image_classR", "widthR", "altR", "captionLR",
    "<!-- Clinical data -->",
    "pronounce", "tradename", "Drugs.com", "MedlinePlus", "licence_CA", "licence_EU", "DailyMedID", "licence_US",
    "pregnancy_AU", "pregnancy_AU_comment", "pregnancy_category", "tolerance_potential", "dependency_liability",
    "addiction_liability", "routes_of_administration", "class", "ATCvet", "ATC_prefix", "ATC_suffix", "ATC_supplemental",
    "<!-- Legal status -->",
    "legal_AU", "legal_AU_comment", "legal_BR", "legal_BR_comment", "legal_CA", "legal_CA_comment", "legal_DE",
    "legal_DE_comment", "legal_NZ", "legal_NZ_comment", "legal_UK", "legal_UK_comment", "legal_US", "legal_US_comment",
    "legal_EU", "legal_EU_comment", "legal_UN", "legal_UN_comment", "legal_status",
    "<!-- Pharmacokinetic data -->",
    "bioavailability", "protein_bound", "metabolism", "metabolites", "onset", "elimination_half-life", "duration_of_action", "excretion",
    "<!-- Identifiers -->",
    "CAS_number", "CAS_supplemental", "PubChem", "PubChemSubstance", "IUPHAR_ligand", "DrugBank", "ChemSpiderID",
    "UNII", "KEGG", "ChEBI", "ChEMBL", "NIAID_ChemDB", "PDB_ligand", "synonyms",
    "<!-- Chemical and physical data -->",
    "IUPAC_name", "chemical_formula", "__ELEMENTS__", "molecular_weight", "SMILES", "Jmol", "StdInChI", "StdInChI_comment",
    "StdInChIKey", "density", "density_notes", "melting_point", "melting_high", "melting_notes", "boiling_point",
    "boiling_notes", "solubility", "sol_units", "specific_rotation",
)

FIELD_DEFAULTS = {
    "type": "<!-- empty -->",
    "image_class": "<!-- skin-invert-image / bg-transparent / dark_mode_safe -->",
    "image_class2": "<!-- skin-invert-image / bg-transparent / dark_mode_safe -->",
    "image_classL": "<!-- skin-invert-image / bg-transparent / dark_mode_safe -->",
    "image_classR": "<!-- skin-invert-image / bg-transparent / dark_mode_safe -->",
    "pregnancy_AU": "<!-- A / B1 / B2 / B3 / C / D / X -->",
    "licence_CA": "<!-- Health Canada may use generic or brand name (generic name preferred) -->",
    "licence_EU": "<!-- EMA uses INN (or special INN_EMA) -->",
    "DailyMedID": "<!-- DailyMed may use generic or brand name (generic name preferred) -->",
    "licence_US": "<!-- FDA may use generic or brand name (generic name preferred) -->",
    "ATC_prefix": "<!-- none if uncategorised -->",
    "legal_AU": "<!-- S2, S3, S4, S5, S6, S7, S8, S9 or Unscheduled -->",
    "legal_BR": "<!-- OTC, A1, A2, A3, B1, B2, C1, C2, C3, C5, D1, D2, E, F1, F2, F3, F4 -->",
    "legal_CA": "<!-- OTC, Rx-only, Schedule I, II, III, IV, V, VI, VII, VIII -->",
    "legal_DE": "<!-- Anlage I, II, III or Unscheduled -->",
    "legal_NZ": "<!-- Class A, B, C -->",
    "legal_UK": "<!-- GSL, P, POM, CD, CD Lic, CD POM, CD No Reg POM, CD (Benz) POM, CD (Anab) POM or CD Inv POM / Class A, B, C -->",
    "legal_US": "<!-- OTC / Rx-only / Schedule I, II, III, IV, V -->",
    "legal_UN": "<!-- N I, II, III, IV / P I, II, III, IV -->",
    "legal_status": "<!-- For countries not listed above -->",
}


def render_chembox_template(compound: PubChemCompound, *, add_iupac_name: bool = True) -> str:
    """Render the legacy PubChem CID Chembox template."""
    iupac_name = compound.iupac_name if add_iupac_name else ""
    formula_html = html_formula(compound.molecular_formula)
    return "\n".join(
        (
            "{{chembox",
            "| ImageFile=",
            "| ImageSize=",
            f"| IUPACName={iupac_name}",
            "| OtherNames=",
            "| Section1={{Chembox Identifiers",
            f"|  CASNo={compound.cas}",
            f"|  PubChem={compound.cid}",
            f"|  SMILES={compound.smiles}",
            f"|  InChI={compound.inchi}",
            f"|  InChIKey={compound.inchikey}",
            "  }}",
            "| Section2={{Chembox Properties",
            f"|  Formula={formula_html}",
            f"|  MolarMass={compound.molecular_weight}",
            "|  Appearance=",
            "|  Density=",
            "|  MeltingPt=",
            "|  BoilingPt=",
            "|  Solubility=",
            "  }}",
            "| Section3={{Chembox Hazards",
            "|  MainHazards=",
            "|  FlashPt=",
            "|  Autoignition=",
            "  }}",
            "}}",
        )
    )


def html_formula(formula: str) -> str:
    """Return a chemical formula with numeric counts as HTML subscripts."""
    return re.sub(r"(\d+)", r"<sub>\1</sub>", formula)


def render_drug_template(compound: PubChemCompound) -> str:
    """Render the full single-drug Infobox drug template with section comments."""
    values = drug_template_values(compound)
    lines = ["{{Infobox drug"]
    for item in DRUG_TEMPLATE_LINES:
        if item.startswith("<!--"):
            lines.append(item)
            continue
        if item == "__ELEMENTS__":
            element_line = element_parameter_line(values)
            if element_line:
                lines.append(element_line)
            continue
        value = values.get(item, FIELD_DEFAULTS.get(item, ""))
        lines.append(f"| {item:<24}= {value}")
    lines.append("}}")
    return "\n".join(lines)


def drug_template_values(compound: PubChemCompound) -> dict[str, str]:
    """Return filled values for the full single-drug template."""
    elements = formula_elements(compound.molecular_formula)
    values = {name: "" for name in DRUG_TEMPLATE_LINES if not name.startswith("<!--")}
    values.update(FIELD_DEFAULTS)
    values.update(
        {
            "drug_name": compound.title,
            "CAS_number": compound.cas,
            "PubChem": compound.cid,
            "DrugBank": compound.drug_bank,
            "UNII": compound.unii,
            "KEGG": compound.kegg,
            "ChEBI": compound.chebi,
            "ChEMBL": compound.chembl,
            "IUPAC_name": f"<nowiki>{compound.iupac_name}</nowiki>" if compound.iupac_name else "",
            "chemical_formula": "" if any(elements.values()) else compound.molecular_formula,
            "molecular_weight": compound.molecular_weight,
            "SMILES": compound.smiles,
            "StdInChI": compound.inchi,
            "StdInChIKey": compound.inchikey,
        }
    )
    values.update({element: str(count) if count else "" for element, count in elements.items()})
    return values


def formula_elements(formula: str) -> dict[str, int]:
    """Return element counts for fields supported by Infobox drug."""
    counts = {element: 0 for element in ELEMENT_FIELDS}
    for element, count in re.findall(r"([A-Z][a-z]?)(\d*)", formula):
        if element in counts:
            counts[element] += int(count) if count else 1
    return counts


def element_parameter_line(values: Mapping[str, str]) -> str:
    """Return one compact element-parameter line, omitting absent elements."""
    return " ".join(f"| {element} = {value}" for element in ELEMENT_FIELDS if (value := values.get(element, "")))
