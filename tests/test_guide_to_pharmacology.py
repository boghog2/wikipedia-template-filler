import unittest
from unittest import mock

from wikipedia_template_filler.sources.guide_to_pharmacology import (
    GTPDB_API_KEY_ENV,
    GTP_API_KEY_ENV,
    GuideToPharmacologyLookupError,
    first_ligand_id,
    guide_to_pharmacology_api_key,
    guide_to_pharmacology_ligand_id,
    ligand_request,
    ligand_url,
)
from wikipedia_template_filler.sources.pubchem import (
    PubChemCompound,
    enrich_compound_from_guide_to_pharmacology,
    fill_pubchem,
)


def compound(iuphar_ligand: str = "") -> PubChemCompound:
    return PubChemCompound(
        cid="2244",
        title="Aspirin",
        molecular_formula="C9H8O4",
        molecular_weight="180.16",
        smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
        inchi="",
        inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        iupac_name="2-acetyloxybenzoic acid",
        cas="50-78-2",
        chebi="15365",
        chembl="25",
        drug_bank="DB00945",
        chemspider="2157",
        iuphar_ligand=iuphar_ligand,
        kegg="D00109",
        unii="R16CO5Y76E",
    )


class GuideToPharmacologyTests(unittest.TestCase):
    def test_ligand_urls_use_documented_parameters(self):
        self.assertEqual(
            ligand_url(pubchem_cid="2244"),
            "https://www.guidetopharmacology.org/services/ligands?accession=2244&database=PubChemCID",
        )
        self.assertEqual(
            ligand_url(inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N"),
            "https://www.guidetopharmacology.org/services/ligands?inchikey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
        )

    def test_api_key_header_and_environment_alias(self):
        with mock.patch.dict("os.environ", {GTP_API_KEY_ENV: "primary", GTPDB_API_KEY_ENV: "alias"}, clear=True):
            self.assertEqual(guide_to_pharmacology_api_key(), "primary")
            request = ligand_request(pubchem_cid="2244")
        self.assertEqual(request.get_header("Gtp-api-key"), "primary")
        self.assertTrue(request.get_header("User-agent"))

    def test_no_api_key_header_when_unconfigured(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            request = ligand_request(pubchem_cid="2244")
        self.assertIsNone(request.get_header("Gtp-api-key"))

    def test_first_ligand_id(self):
        self.assertEqual(first_ligand_id([{"ligandId": 4139, "name": "aspirin"}]), "4139")
        self.assertEqual(first_ligand_id([]), "")
        self.assertEqual(first_ligand_id({"ligandId": 4139}), "")

    def test_lookup_prefers_pubchem_then_falls_back_to_inchikey(self):
        urls = []

        def requester(request):
            urls.append(request.full_url)
            return [] if "accession=" in request.full_url else [{"ligandId": 4139}]

        result = guide_to_pharmacology_ligand_id(
            pubchem_cid="2244",
            inchikey="BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
            requester=requester,
        )
        self.assertEqual(result, "4139")
        self.assertIn("accession=2244", urls[0])
        self.assertIn("inchikey=BSYNRYMUTXBXSQ-UHFFFAOYSA-N", urls[1])

    def test_pubchem_enrichment_fills_only_missing_iuphar_id(self):
        enriched = enrich_compound_from_guide_to_pharmacology(
            compound(), requester=lambda request: [{"ligandId": 4139}]
        )
        self.assertEqual(enriched.iuphar_ligand, "4139")

        calls = []
        unchanged = enrich_compound_from_guide_to_pharmacology(
            compound("999"), requester=lambda request: calls.append(request)
        )
        self.assertEqual(unchanged.iuphar_ligand, "999")
        self.assertEqual(calls, [])

    def test_pubchem_fill_uses_gtopdb_when_wikidata_has_no_iuphar_id(self):
        def fetcher(url):
            if "/property/" in url:
                return {"PropertyTable": {"Properties": [{
                    "CID": 2244,
                    "MolecularFormula": "C9H8O4",
                    "MolecularWeight": "180.16",
                    "InChIKey": "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
                }]}}
            if "/synonyms/" in url:
                return {"InformationList": {"Information": [{"Synonym": ["Aspirin"]}]}}
            if "/xrefs/" in url:
                return {"InformationList": {"Information": []}}
            if "query.wikidata.org" in url:
                return {"results": {"bindings": []}}
            raise AssertionError(f"unexpected URL: {url}")

        output = fill_pubchem(
            "2244",
            json_fetcher=fetcher,
            gtopdb_requester=lambda request: [{"ligandId": 4139}],
        )
        self.assertIn("|IUPHAR_ligand=4139", output)

    def test_optional_enrichment_does_not_block_pubchem_on_gtopdb_error(self):
        def unavailable(request):
            raise GuideToPharmacologyLookupError("temporary failure")

        self.assertEqual(
            enrich_compound_from_guide_to_pharmacology(compound(), requester=unavailable),
            compound(),
        )


if __name__ == "__main__":
    unittest.main()
