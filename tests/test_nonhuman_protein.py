import os
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from wikipedia_template_filler import fill
from wikipedia_template_filler._http import USER_AGENT
from wikipedia_template_filler._ncbi import NCBI_API_KEY_ENV, NCBI_EMAIL_ENV, NCBI_TOOL
from wikipedia_template_filler.sources.nonhuman_protein import (
    SourceLookupError,
    fetch_json,
    fill_ncbi_gene,
    fill_uniprot,
    format_organism,
    ncbi_gene_url,
    nonhuman_protein_fields,
    normalize_gene_id,
    normalize_uniprot,
    parse_ncbi_gene_response,
    parse_uniprot_search_response,
    parse_uniprot_response,
    strip_accession_version,
    uniprot_gene_search_url,
    uniprot_url,
)


def uniprot_payload() -> dict:
    return {
        "primaryAccession": "P02769",
        "organism": {"scientificName": "Bos taurus", "commonName": "domestic cow", "taxonId": 9913},
        "proteinDescription": {"recommendedName": {"fullName": {"value": "Albumin"}}},
        "genes": [{"geneName": {"value": "ALB"}}],
        "uniProtKBCrossReferences": [
            {
                "database": "RefSeq",
                "id": "NP_851335.1",
                "properties": [{"key": "NucleotideSequenceId", "value": "NM_180992.2"}],
            },
            {"database": "PDB", "id": "3V03"},
            {"database": "GeneID", "id": "280717"},
        ],
    }


def ncbi_gene_payload() -> dict:
    return {
        "result": {
            "uids": ["280717"],
            "280717": {
                "uid": "280717",
                "name": "ALB",
                "description": "albumin",
                "nomenclaturesymbol": "ALB",
                "otheraliases": "",
                "chromosome": "6",
                "organism": {"scientificname": "Bos taurus", "commonname": "domestic cow", "taxid": 9913},
                "genomicinfo": [
                    {
                        "chrloc": "6",
                        "chraccver": "NC_007304.4",
                        "chrstart": 91543999,
                        "chrstop": 91567876,
                    }
                ],
            },
        }
    }


def fake_fetcher(url: str) -> dict:
    if url == uniprot_url("P02769"):
        return uniprot_payload()
    if url == uniprot_gene_search_url("280717"):
        return {"results": [{"primaryAccession": "P02769"}]}
    if url == ncbi_gene_url("280717"):
        return ncbi_gene_payload()
    raise AssertionError(f"unexpected URL {url}")


class NonhumanProteinTests(unittest.TestCase):
    def test_normalizers(self):
        self.assertEqual(normalize_uniprot("UniProt:P02769"), "P02769")
        self.assertEqual(normalize_uniprot("P02769"), "P02769")
        self.assertEqual(normalize_gene_id("GeneID: 280717"), "280717")

    def test_urls(self):
        self.assertEqual(uniprot_url("P02769"), "https://rest.uniprot.org/uniprotkb/P02769.json")
        self.assertIn("xref%3AGeneID-280717", uniprot_gene_search_url("280717"))
        self.assertIn("reviewed%3Atrue", uniprot_gene_search_url("280717"))
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                ncbi_gene_url("280717"),
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=280717&retmode=json",
            )

    def test_ncbi_gene_url_includes_optional_api_key_and_email(self):
        with mock.patch.dict(
            os.environ,
            {NCBI_API_KEY_ENV: "test-api-key", NCBI_EMAIL_ENV: "boghog@example.org"},
        ):
            query = parse_qs(urlparse(ncbi_gene_url("280717")).query)

        self.assertEqual(query["api_key"], ["test-api-key"])
        self.assertEqual(query["tool"], [NCBI_TOOL])
        self.assertEqual(query["email"], ["boghog@example.org"])

    def test_fetch_json_sends_shared_user_agent(self):
        response = mock.MagicMock()
        response.read.return_value = b"{}"
        with mock.patch("wikipedia_template_filler.sources.nonhuman_protein.urlopen") as fake_urlopen:
            fake_urlopen.return_value.__enter__.return_value = response
            fetch_json(uniprot_url("P02769"))

        request = fake_urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), USER_AGENT)

    def test_parse_helpers(self):
        self.assertEqual(strip_accession_version("NP_851335.1"), "NP_851335")
        self.assertEqual(format_organism("Bos taurus", "domestic cow"), "''Bos taurus'' (domestic cow)")
        self.assertEqual(parse_uniprot_search_response({"results": [{"primaryAccession": "P02769"}]}), "P02769")
        self.assertEqual(parse_uniprot_search_response({"results": []}), "")

    def test_parse_uniprot_response(self):
        protein = parse_uniprot_response(uniprot_payload(), expected_accession="P02769")
        fields = dict(nonhuman_protein_fields(protein))
        self.assertEqual(fields["Name"], "Albumin")
        self.assertEqual(fields["Organism"], "''Bos taurus'' (domestic cow)")
        self.assertEqual(fields["TaxID"], "9913")
        self.assertEqual(fields["Symbol"], "ALB")
        self.assertEqual(fields["EntrezGene"], "280717")
        self.assertEqual(fields["PDB"], "3V03")
        self.assertEqual(fields["RefSeqmRNA"], "NM_180992")
        self.assertEqual(fields["RefSeqProtein"], "NP_851335")
        self.assertEqual(fields["UniProt"], "P02769")

    def test_parse_uniprot_response_joins_multiple_pdb_ids_with_plus(self):
        payload = uniprot_payload()
        payload["uniProtKBCrossReferences"] = [
            ref
            for ref in payload["uniProtKBCrossReferences"]
            if ref["database"] != "PDB"
        ]
        payload["uniProtKBCrossReferences"].extend(
            [
                {"database": "PDB", "id": "1MI6"},
                {"database": "PDB", "id": "1MVR"},
                {"database": "PDB", "id": "4GMK"},
                {"database": "PDB", "id": "4GSB"},
            ]
        )

        def fetcher(url: str) -> dict:
            return ncbi_gene_payload() if url == ncbi_gene_url("280717") else payload

        protein = parse_uniprot_response(payload, expected_accession="P02769")
        output = fill_uniprot("P02769", json_fetcher=fetcher, add_param_space=True)

        self.assertEqual(dict(nonhuman_protein_fields(protein))["PDB"], "1MI6+1MVR+4GMK+4GSB")
        self.assertIn("| PDB = 1MI6+1MVR+4GMK+4GSB", output)

    def test_parse_ncbi_gene_response(self):
        protein = parse_ncbi_gene_response(ncbi_gene_payload(), expected_gene_id="280717")
        fields = dict(nonhuman_protein_fields(protein))
        self.assertEqual(fields["Name"], "albumin")
        self.assertEqual(fields["Organism"], "''Bos taurus'' (domestic cow)")
        self.assertEqual(fields["TaxID"], "9913")
        self.assertEqual(fields["Symbol"], "ALB")
        self.assertEqual(fields["EntrezGene"], "280717")
        self.assertEqual(fields["Chromosome"], "6")
        self.assertEqual(fields["EntrezChromosome"], "NC_007304.4")
        self.assertEqual(fields["GenLoc_start"], "91543999")
        self.assertEqual(fields["GenLoc_end"], "91567876")

    def test_fill_uniprot_merges_ncbi_gene_location_fields(self):
        output = fill_uniprot("P02769", json_fetcher=fake_fetcher, add_param_space=True, extended=True)
        self.assertTrue(output.startswith("{{Infobox nonhuman protein\n"))
        self.assertIn("| Name = Albumin", output)
        self.assertIn("| Organism = ''Bos taurus'' (domestic cow)", output)
        self.assertIn("| EntrezGene = 280717", output)
        self.assertIn("| RefSeqmRNA = NM_180992", output)
        self.assertIn("| RefSeqProtein = NP_851335", output)
        self.assertIn("| UniProt = P02769", output)
        self.assertIn("| Chromosome = 6", output)
        self.assertIn("| EntrezChromosome = NC_007304.4", output)
        self.assertIn("| GenLoc_start = 91543999", output)
        self.assertIn("| GenLoc_end = 91567876", output)

    def test_fill_ncbi_gene_renders_nonhuman_protein(self):
        output = fill_ncbi_gene("280717", json_fetcher=fake_fetcher, add_param_space=True, extended=True)
        self.assertIn("| Name = Albumin", output)
        self.assertIn("| EntrezGene = 280717", output)
        self.assertIn("| RefSeqmRNA = NM_180992", output)
        self.assertIn("| RefSeqProtein = NP_851335", output)
        self.assertIn("| UniProt = P02769", output)
        self.assertIn("| PDB = 3V03", output)
        self.assertIn("| Chromosome = 6", output)

    def test_public_fill_routes_to_nonhuman_sources(self):
        self.assertIn("{{Infobox nonhuman protein", fill("uniprot", "P02769", json_fetcher=fake_fetcher))
        self.assertIn("{{Infobox nonhuman protein", fill("gene", "280717", json_fetcher=fake_fetcher))

    def test_parse_raises_for_missing_records(self):
        with self.assertRaisesRegex(SourceLookupError, "no UniProt entry matches"):
            parse_uniprot_response({"primaryAccession": "Q00000"}, expected_accession="P02769")
        with self.assertRaisesRegex(SourceLookupError, "no NCBI Gene record matches"):
            parse_ncbi_gene_response({"result": {"uids": []}}, expected_gene_id="280717")


if __name__ == "__main__":
    unittest.main()
