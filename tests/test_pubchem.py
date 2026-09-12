import unittest
from unittest import mock
from urllib.parse import parse_qs, unquote_plus, urlparse

from wikipedia_template_filler import fill
from wikipedia_template_filler._http import USER_AGENT
from wikipedia_template_filler.sources.chemspider import (
    CHEMSPIDER_API_KEY_ENV,
    RSC_API_KEY_ENV,
    chemspider_id_from_inchikey,
    first_result_id,
    inchikey_filter_request,
    query_results_request,
    rsc_api_key,
)
from wikipedia_template_filler.sources.pubchem import (
    SourceLookupError,
    as_list,
    compound_fields,
    enrich_compound_from_chemspider,
    enrich_compound_from_wikidata,
    fetch_json,
    fetch_pubchem_compound,
    fill_pubchem,
    fill_pubchem_chembox,
    html_formula,
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
from wikipedia_template_filler.sources.wikidata import (
    drug_identifier_url,
    enrich_drug_identifiers,
    parse_drug_identifier_response,
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


def wikidata_payload() -> dict:
    return {
        "results": {
            "bindings": [
                {
                    "inchikey": {"type": "literal", "value": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"},
                    "pubchem": {"type": "literal", "value": "2244"},
                    "chemspider": {"type": "literal", "value": "2157"},
                    "iuphar": {"type": "literal", "value": "4139"},
                    "drugbank": {"type": "literal", "value": "DB00945"},
                    "chebi": {"type": "literal", "value": "CHEBI:15365"},
                    "chembl": {"type": "literal", "value": "CHEMBL25"},
                    "unii": {"type": "literal", "value": "R16CO5Y76E"},
                }
            ]
        }
    }


def wikidata_payload_without_chemspider() -> dict:
    payload = wikidata_payload()
    payload["results"]["bindings"][0].pop("chemspider")
    return payload


def fake_fetcher(url: str) -> dict:
    if url == property_url("2244"):
        return property_payload()
    if url == synonyms_url("2244"):
        return synonyms_payload()
    if url == xrefs_url("2244"):
        return xrefs_payload()
    if url.startswith("https://query.wikidata.org/sparql?"):
        return wikidata_payload()
    raise AssertionError(f"unexpected URL {url}")


class PubChemTests(unittest.TestCase):
    def test_normalize_cid(self):
        self.assertEqual(normalize_cid("CID: 2244"), "2244")
        self.assertEqual(normalize_cid("2244"), "2244")

    def test_urls(self):
        self.assertEqual(property_url("2244").split("/compound/cid/2244/", 1)[1], "property/MolecularFormula,MolecularWeight,IsomericSMILES,CanonicalSMILES,ConnectivitySMILES,SMILES,InChI,InChIKey,IUPACName/JSON")
        self.assertEqual(synonyms_url("2244"), "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/synonyms/JSON")
        self.assertEqual(xrefs_url("2244"), "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2244/xrefs/RegistryID,SourceName/JSON")

    def test_fetch_json_sends_shared_user_agent(self):
        response = mock.MagicMock()
        response.read.return_value = b"{}"
        with mock.patch("wikipedia_template_filler.sources.pubchem.urlopen") as fake_urlopen:
            fake_urlopen.return_value.__enter__.return_value = response
            fetch_json(property_url("2244"))

        request = fake_urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), USER_AGENT)

    def test_rsc_api_key_prefers_rsc_env_var(self):
        with mock.patch.dict(
            "os.environ",
            {RSC_API_KEY_ENV: "rsc-key", CHEMSPIDER_API_KEY_ENV: "chemspider-key"},
            clear=True,
        ):
            self.assertEqual(rsc_api_key(), "rsc-key")

    def test_rsc_api_key_accepts_chemspider_env_alias(self):
        with mock.patch.dict("os.environ", {CHEMSPIDER_API_KEY_ENV: "chemspider-key"}, clear=True):
            self.assertEqual(rsc_api_key(), "chemspider-key")

    def test_chemspider_inchikey_request_uses_api_key_and_shared_user_agent(self):
        request = inchikey_filter_request("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", api_key="test-rsc-key")

        self.assertEqual(request.full_url, "https://api.rsc.org/compounds/v1/filter/inchikey")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Apikey"), "test-rsc-key")
        self.assertEqual(request.get_header("User-agent"), USER_AGENT)
        self.assertEqual(request.data, b'{"inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"}')

    def test_chemspider_results_request_uses_api_key_and_query_id(self):
        request = query_results_request("query-123", api_key="test-rsc-key")

        self.assertEqual(request.full_url, "https://api.rsc.org/compounds/v1/filter/query-123/results")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Apikey"), "test-rsc-key")

    def test_chemspider_id_from_inchikey_uses_two_step_rsc_lookup(self):
        urls = []

        def requester(request):
            urls.append(request.full_url)
            if request.full_url.endswith("/filter/inchikey"):
                return {"queryId": "query-123"}
            return {"results": [2157, 9999], "limitedToMaxAllowed": False}

        with mock.patch.dict("os.environ", {RSC_API_KEY_ENV: "test-rsc-key"}, clear=True):
            self.assertEqual(
                chemspider_id_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", requester=requester),
                "2157",
            )

        self.assertEqual(
            urls,
            [
                "https://api.rsc.org/compounds/v1/filter/inchikey",
                "https://api.rsc.org/compounds/v1/filter/query-123/results",
            ],
        )

    def test_chemspider_id_from_inchikey_is_blank_without_api_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(chemspider_id_from_inchikey("BSYNRYMUTXBXSQ-UHFFFAOYSA-N"), "")

    def test_first_result_id_returns_first_chemspider_record(self):
        self.assertEqual(first_result_id({"results": [2157, 9999]}), "2157")
        self.assertEqual(first_result_id({"results": []}), "")

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

    def test_wikidata_url_queries_pubchem_cid_and_inchikey(self):
        compound = fetch_pubchem_compound("2244", fetcher=fake_fetcher)
        query = unquote_plus(
            parse_qs(
                urlparse(
                    drug_identifier_url(pubchem_cid=compound.cid, inchikey=compound.inchikey)
                ).query
            )["query"][0]
        )

        self.assertIn('?item wdt:P662 "2244".', query)
        self.assertIn('?item wdt:P235 "BSYNRYMUTXBXSQ-UHFFFAOYSA-N".', query)
        self.assertIn("?item wdt:P661 ?chemspider.", query)
        self.assertIn("?item wdt:P595 ?iuphar.", query)

    def test_parse_wikidata_response_normalizes_drug_identifiers(self):
        identifiers = parse_drug_identifier_response(wikidata_payload())
        self.assertEqual(identifiers["pubchem"], "2244")
        self.assertEqual(identifiers["chemspider"], "2157")
        self.assertEqual(identifiers["iuphar_ligand"], "4139")
        self.assertEqual(identifiers["drug_bank"], "DB00945")
        self.assertEqual(identifiers["chebi"], "15365")
        self.assertEqual(identifiers["chembl"], "25")
        self.assertEqual(identifiers["unii"], "R16CO5Y76E")

    def test_wikidata_enrichment_fills_missing_drug_identifiers(self):
        compound = fetch_pubchem_compound("2244", fetcher=fake_fetcher)
        enriched = enrich_compound_from_wikidata(compound, fetcher=fake_fetcher)
        fields = dict(compound_fields(enriched))

        self.assertEqual(fields["ChemSpiderID"], "2157")
        self.assertEqual(fields["IUPHAR_ligand"], "4139")
        self.assertEqual(fields["DrugBank"], "DB00945")
        self.assertEqual(fields["ChEBI"], "15365")
        self.assertEqual(fields["ChEMBL"], "25")

    def test_chemspider_enrichment_fills_missing_chemspider_id_from_rsc(self):
        def fetcher(url: str) -> dict:
            if url.startswith("https://query.wikidata.org/sparql?"):
                return wikidata_payload_without_chemspider()
            return fake_fetcher(url)

        def requester(request):
            if request.full_url.endswith("/filter/inchikey"):
                return {"queryId": "query-123"}
            return {"results": [2157]}

        compound = enrich_compound_from_wikidata(fetch_pubchem_compound("2244", fetcher=fetcher), fetcher=fetcher)
        with mock.patch.dict("os.environ", {RSC_API_KEY_ENV: "test-rsc-key"}, clear=True):
            with mock.patch(
                "wikipedia_template_filler.sources.chemspider.fetch_json_request",
                side_effect=requester,
            ):
                enriched = enrich_compound_from_chemspider(compound)

        self.assertEqual(dict(compound_fields(compound))["ChemSpiderID"], "")
        self.assertEqual(dict(compound_fields(enriched))["ChemSpiderID"], "2157")

    def test_wikidata_enrichment_falls_back_to_inchikey_when_pubchem_cid_misses(self):
        requested_queries = []

        def fetcher(url: str) -> dict:
            query = unquote_plus(parse_qs(urlparse(url).query)["query"][0])
            requested_queries.append(query)
            if 'wdt:P235 "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"' in query:
                return wikidata_payload()
            return {"results": {"bindings": []}}

        identifiers = enrich_drug_identifiers(
            {"pubchem": "2244", "inchikey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"},
            pubchem_cid="2244",
            inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            fetcher=fetcher,
        )

        self.assertIn('wdt:P662 "2244"', requested_queries[0])
        self.assertNotIn('wdt:P235 "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"', requested_queries[0])
        self.assertIn('wdt:P235 "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"', requested_queries[1])
        self.assertNotIn('wdt:P662 "2244"', requested_queries[1])
        self.assertEqual(identifiers["chemspider"], "2157")
        self.assertEqual(identifiers["iuphar_ligand"], "4139")

    def test_fetch_pubchem_compound_fields(self):
        compound = fetch_pubchem_compound("2244", fetcher=fake_fetcher)
        fields = dict(compound_fields(compound))
        self.assertEqual(fields["drug_name"], "Aspirin")
        self.assertEqual(fields["PubChem"], "2244")
        self.assertEqual(fields["CAS_number"], "50-78-2")
        self.assertEqual(fields["ChEMBL"], "25")
        self.assertEqual(fields["IUPAC_name"], "<nowiki>2-acetyloxybenzoic acid</nowiki>")
        self.assertEqual(fields["chemical_formula"], "C9H8O4")

    def test_fill_pubchem_renders_compact_infobox_drug_by_default(self):
        output = fill_pubchem("CID:2244", json_fetcher=fake_fetcher)
        self.assertTrue(output.startswith("{{Infobox drug\n"))
        self.assertIn("<!-- Clinical data -->", output)
        self.assertIn("<!-- Legal status -->", output)
        self.assertIn("<!-- Pharmacokinetic data -->", output)
        self.assertIn("<!-- Identifiers -->", output)
        self.assertIn("<!-- Chemical and physical data -->", output)
        self.assertIn("|drug_name=Aspirin", output)
        self.assertIn("|PubChem=2244", output)
        self.assertIn("|IUPHAR_ligand=4139", output)
        self.assertIn("|ChEBI=15365", output)
        self.assertIn("|ChemSpiderID=2157", output)
        self.assertIn("| C=9 | H=8 | O=4", output)
        self.assertNotIn("|Ag=", output)
        self.assertNotIn("|charge=", output)
        self.assertIn("|StdInChIKey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N", output)

    def test_fill_pubchem_extended_and_spacing_options_affect_infobox_drug(self):
        output = fill_pubchem("CID:2244", json_fetcher=fake_fetcher, add_param_space=True, extended=True)
        self.assertIn("| drug_name               = Aspirin", output)
        self.assertIn("| INN                     = ", output)
        self.assertIn("| PubChem                 = 2244", output)
        self.assertIn("| IUPHAR_ligand           = 4139", output)
        self.assertIn("| ChemSpiderID            = 2157", output)
        self.assertIn("| C = 9 | H = 8 | O = 4", output)
        self.assertIn("| StdInChIKey             = BSYNRYMUTXBXSQ-UHFFFAOYSA-N", output)

    def test_fill_pubchem_chembox_suppresses_empty_fields_by_default(self):
        output = fill_pubchem_chembox("CID:2244", json_fetcher=fake_fetcher)
        self.assertTrue(output.startswith("{{chembox\n"))
        self.assertIn("|IUPACName=2-acetyloxybenzoic acid", output)
        self.assertIn("|Section1={{Chembox Identifiers", output)
        self.assertIn("|  CASNo=50-78-2", output)
        self.assertIn("|  PubChem=2244", output)
        self.assertIn("|  SMILES=CC(=O)OC1=CC=CC=C1C(=O)O", output)
        self.assertIn("|  InChIKey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N", output)
        self.assertIn("|Section2={{Chembox Properties", output)
        self.assertIn("|  Formula=C<sub>9</sub>H<sub>8</sub>O<sub>4</sub>", output)
        self.assertIn("|  MolarMass=180.16", output)
        self.assertNotIn("ImageFile", output)
        self.assertNotIn("Appearance", output)
        self.assertNotIn("Section3", output)

    def test_fill_pubchem_chembox_extended_and_spacing_options_affect_output(self):
        output = fill_pubchem_chembox("CID:2244", json_fetcher=fake_fetcher, add_param_space=True, extended=True)
        self.assertIn("| ImageFile = ", output)
        self.assertIn("| IUPACName = 2-acetyloxybenzoic acid", output)
        self.assertIn("| Section1 = {{Chembox Identifiers", output)
        self.assertIn("|  CASNo = 50-78-2", output)
        self.assertIn("|  PubChem = 2244", output)
        self.assertIn("| Section2 = {{Chembox Properties", output)
        self.assertIn("|  Appearance = ", output)
        self.assertIn("| Section3 = {{Chembox Hazards", output)
        self.assertIn("|  MainHazards = ", output)

    def test_html_formula_adds_subscripts(self):
        self.assertEqual(html_formula("C9H8O4"), "C<sub>9</sub>H<sub>8</sub>O<sub>4</sub>")

    def test_public_fill_routes_to_pubchem_source(self):
        output = fill("pubchem", "2244", json_fetcher=fake_fetcher, add_param_space=True)
        self.assertIn("{{Infobox drug", output)
        self.assertIn("| DrugBank                = DB00945", output)

    def test_public_fill_routes_to_pubchem_chembox_source(self):
        output = fill("chembox", "2244", json_fetcher=fake_fetcher)
        self.assertIn("{{chembox", output)
        self.assertIn("|  PubChem=2244", output)

    def test_fetch_raises_for_missing_compound(self):
        with self.assertRaisesRegex(SourceLookupError, "no compound matches"):
            parse_property_response({"PropertyTable": {"Properties": []}}, expected_cid="1")


if __name__ == "__main__":
    unittest.main()
