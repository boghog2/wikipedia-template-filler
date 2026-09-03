import unittest

from wikipedia_template_filler import fill
from wikipedia_template_filler.sources.pubchem import (
    SourceLookupError,
    as_list,
    compound_fields,
    fetch_pubchem_compound,
    fill_pubchem,
    first_matching_group,
    normalize_cid,
    parse_property_response,
    parse_synonyms_response,
    formula_elements,
    property_url,
    registry_id_from_xrefs,
    registry_identifiers,
    synonyms_url,
    xrefs_url,
)


def property_payload() -> dict:
    return {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 2244,
                    "MolecularFormula": "C9H8O4",
                    "MolecularWeight": "180.16",
                    "IsomericSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "CanonicalSMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "InChI": "InChI=1S/C9H8O4/c1-6(10)13-8-5-3-2-4-7(8)9(11)12/h2-5H,1H3,(H,11,12)",
                    "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                    "IUPACName": "2-acetyloxybenzoic acid",
                }
            ]
        }
    }


def synonyms_payload() -> dict:
    return {
        "InformationList": {
            "Information": [
                {
                    "CID": 2244,
                    "Synonym": [
                        "Aspirin",
                        "50-78-2",
                        "CHEBI:15365",
                        "CHEMBL25",
                        "DB00945",
                        "D00109",
                        "R16CO5Y76E",
                    ],
                }
            ]
        }
    }


def xrefs_payload() -> dict:
    return {"InformationList": {"Information": []}}


def fake_fetcher(url: str) -> dict:
    if url == property_url("2244"):
        return property_payload()
    if url == synonyms_url("2244"):
        return synonyms_payload()
    if url == xrefs_url("2244"):
        return xrefs_payload()
    raise AssertionError(f"unexpected URL {url}")


class PubChemTests(unittest.TestCase):
    def test_normalize_cid(self):
        self.assertEqual(normalize_cid("CID: 2244"), "2244")
        self.assertEqual(normalize_cid("2244"), "2244")

    def test_urls(self):
        self.assertEqual(property_url("2244").split("/compound/cid/2244/", 1)[1], "property/MolecularFormula,MolecularWeight,IsomericSMILES,CanonicalSMILES,ConnectivitySMILES,SMILES,InChI,InChIKey,IUPACName/JSON")
        self.assertEqual(synonyms_url("2244"), "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/synonyms/JSON")
        self.assertEqual(xrefs_url("2244"), "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/xrefs/RegistryID,SourceName/JSON")

    def test_parse_helpers(self):
        self.assertEqual(parse_property_response(property_payload(), expected_cid="2244")["MolecularFormula"], "C9H8O4")
        self.assertEqual(parse_synonyms_response(synonyms_payload())[0], "Aspirin")
        self.assertEqual(as_list("ChEMBL"), ["ChEMBL"])
        self.assertEqual(first_matching_group(["CHEBI:15365"], r"^CHEBI:(\d+)$"), "15365")
        self.assertEqual(formula_elements("C9H8O4")["C"], 9)
        self.assertEqual(formula_elements("C9H8O4")["H"], 8)
        self.assertEqual(formula_elements("C9H8O4")["O"], 4)

    def test_registry_identifiers_from_synonyms(self):
        identifiers = registry_identifiers(parse_synonyms_response(synonyms_payload()), xrefs_payload())
        self.assertEqual(identifiers["cas"], "50-78-2")
        self.assertEqual(identifiers["chebi"], "15365")
        self.assertEqual(identifiers["chembl"], "25")
        self.assertEqual(identifiers["drug_bank"], "DB00945")
        self.assertEqual(identifiers["kegg"], "D00109")
        self.assertEqual(identifiers["unii"], "R16CO5Y76E")

    def test_registry_identifier_from_xrefs(self):
        xrefs = {"InformationList": {"Information": [{"SourceName": ["ChEMBL"], "RegistryID": ["CHEMBL25"]}]}}
        self.assertEqual(registry_id_from_xrefs(xrefs, ("ChEMBL",), r"^CHEMBL(\d+)$"), "25")

    def test_fetch_pubchem_compound_fields(self):
        compound = fetch_pubchem_compound("2244", fetcher=fake_fetcher)
        fields = dict(compound_fields(compound))
        self.assertEqual(fields["drug_name"], "Aspirin")
        self.assertEqual(fields["PubChem"], "2244")
        self.assertEqual(fields["CAS_number"], "50-78-2")
        self.assertEqual(fields["ChEMBL"], "25")
        self.assertEqual(fields["IUPAC_name"], "<nowiki>2-acetyloxybenzoic acid</nowiki>")
        self.assertEqual(fields["chemical_formula"], "C9H8O4")

    def test_fill_pubchem_renders_vertical_infobox_drug(self):
        output = fill_pubchem("CID:2244", json_fetcher=fake_fetcher, add_param_space=True)
        self.assertTrue(output.startswith("{{Infobox drug\n"))
        self.assertIn("<!-- Clinical data -->", output)
        self.assertIn("<!-- Legal status -->", output)
        self.assertIn("<!-- Pharmacokinetic data -->", output)
        self.assertIn("<!-- Identifiers -->", output)
        self.assertIn("<!-- Chemical and physical data -->", output)
        self.assertIn("| drug_name               = Aspirin", output)
        self.assertIn("| PubChem                 = 2244", output)
        self.assertIn("| ChEBI                   = 15365", output)
        self.assertIn("| C = 9 | H = 8 | O = 4", output)
        self.assertNotIn("| Ag =", output)
        self.assertNotIn("| charge =", output)
        self.assertIn("| StdInChIKey             = BSYNRYMUTXBXSQ-UHFFFAOYSA-N", output)

    def test_public_fill_routes_to_pubchem_source(self):
        output = fill("pubchem", "2244", json_fetcher=fake_fetcher, add_param_space=True)
        self.assertIn("{{Infobox drug", output)
        self.assertIn("| DrugBank                = DB00945", output)

    def test_fetch_raises_for_missing_compound(self):
        with self.assertRaisesRegex(SourceLookupError, "no compound matches"):
            parse_property_response({"PropertyTable": {"Properties": []}}, expected_cid="1")


if __name__ == "__main__":
    unittest.main()
