import json
import unittest
from pathlib import Path

from wikipedia_template_filler import fill
from wikipedia_template_filler.sources.pubmed import (
    SourceLookupError,
    article_fields,
    expand_month,
    fill_pmc,
    fill_pubmed,
    normalize_pages,
    normalize_pmcid,
    normalize_pmid,
    parse_linked_pmid,
    parse_pubmed_article,
    pmc_to_pubmed_url,
    pubmed_url,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"
GOLDEN_DIR = FIXTURE_DIR / "golden"
NORMALIZED_DIR = FIXTURE_DIR / "normalized"


def load_fixture(directory: Path, name: str) -> dict:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def pubmed_xml() -> str:
    return """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle>
<MedlineCitation><PMID>18535242</PMID><Article>
<Journal><JournalIssue><Volume>320</Volume><Issue>5881</Issue><PubDate><Year>2008</Year><Month>Jun</Month></PubDate></JournalIssue><ISOAbbreviation>Science</ISOAbbreviation></Journal>
<ArticleTitle>Subdiffraction multicolor imaging of the nuclear periphery with 3D structured illumination microscopy.</ArticleTitle>
<Pagination><MedlinePgn>1332-6</MedlinePgn></Pagination>
<AuthorList>
<Author><LastName>Schermelleh</LastName><Initials>L</Initials></Author>
<Author><LastName>Carlton</LastName><Initials>PM</Initials></Author>
<Author><LastName>Haase</LastName><Initials>S</Initials></Author>
<Author><LastName>Shao</LastName><Initials>L</Initials></Author>
<Author><LastName>Winoto</LastName><Initials>L</Initials></Author>
<Author><LastName>Kner</LastName><Initials>P</Initials></Author>
<Author><LastName>Burke</LastName><Initials>B</Initials></Author>
<Author><LastName>Cardoso</LastName><Initials>MC</Initials></Author>
<Author><LastName>Agard</LastName><Initials>DA</Initials></Author>
<Author><LastName>Gustafsson</LastName><Initials>MGL</Initials></Author>
<Author><LastName>Leonhardt</LastName><Initials>H</Initials></Author>
<Author><LastName>Sedat</LastName><Initials>JW</Initials></Author>
</AuthorList>
</Article></MedlineCitation>
<PubmedData><ArticleIdList>
<ArticleId IdType="pubmed">18535242</ArticleId>
<ArticleId IdType="pmc">PMC2916659</ArticleId>
<ArticleId IdType="doi">10.1126/science.1156947</ArticleId>
</ArticleIdList></PubmedData>
</PubmedArticle>
</PubmedArticleSet>"""


def pmc_link_xml() -> str:
    return """<?xml version="1.0" ?>
<!DOCTYPE eLinkResult PUBLIC "-//NLM//DTD elink 20101123//EN" "https://eutils.ncbi.nlm.nih.gov/eutils/dtd/20101123/elink.dtd">
<eLinkResult>
<LinkSet>
<DbFrom>pmc</DbFrom>
<IdList><Id>137841</Id></IdList>
<LinkSetDb>
<DbTo>pubmed</DbTo>
<LinkName>pmc_pubmed</LinkName>
<Link><Id>12384568</Id></Link>
</LinkSetDb>
</LinkSet>
</eLinkResult>"""


def pmc_pubmed_xml() -> str:
    return """<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle>
<MedlineCitation><PMID>12384568</PMID><Article>
<Journal><JournalIssue><Volume>99</Volume><Issue>22</Issue><PubDate><Year>2002</Year><Month>Oct</Month></PubDate></JournalIssue><ISOAbbreviation>Proc Natl Acad Sci U S A</ISOAbbreviation></Journal>
<ArticleTitle>Does RNA polymerase help drive chromosome segregation in bacteria?</ArticleTitle>
<Pagination><MedlinePgn>14089-94</MedlinePgn></Pagination>
<AuthorList>
<Author><LastName>Dworkin</LastName><Initials>J</Initials></Author>
<Author><LastName>Losick</LastName><Initials>R</Initials></Author>
</AuthorList>
</Article></MedlineCitation>
<PubmedData><ArticleIdList>
<ArticleId IdType="pubmed">12384568</ArticleId>
<ArticleId IdType="pmc">PMC137841</ArticleId>
<ArticleId IdType="doi">10.1073/pnas.182539899</ArticleId>
</ArticleIdList></PubmedData>
</PubmedArticle>
</PubmedArticleSet>"""


class PubMedTests(unittest.TestCase):
    def test_normalize_pmid(self):
        self.assertEqual(normalize_pmid("PMID: 18535242"), "18535242")

    def test_normalize_pmcid(self):
        self.assertEqual(normalize_pmcid("PMC137841"), "137841")
        self.assertEqual(normalize_pmcid(" 137841 "), "137841")

    def test_pubmed_url(self):
        self.assertEqual(
            pubmed_url("18535242"),
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=18535242&retmode=xml",
        )

    def test_pmc_to_pubmed_url(self):
        self.assertEqual(
            pmc_to_pubmed_url("137841"),
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pmc&db=pubmed&id=137841&retmode=xml",
        )

    def test_format_helpers(self):
        self.assertEqual(expand_month("Jun"), "June")
        self.assertEqual(normalize_pages("1332-6"), "1332–6")

    def test_parse_pubmed_article_matches_normalized_fixture(self):
        normalized = load_fixture(NORMALIZED_DIR, "pubmed_18535242.json")
        article = parse_pubmed_article(pubmed_xml(), expected_pmid="18535242")
        self.assertEqual(article_fields(article), [(field["name"], field["value"]) for field in normalized["fields"]])

    def test_fill_pubmed_matches_golden_fixture_with_fake_fetcher(self):
        golden = load_fixture(GOLDEN_DIR, "pubmed_18535242.json")

        def fake_fetcher(url: str) -> str:
            self.assertEqual(url, pubmed_url(golden["id"]))
            return pubmed_xml()

        self.assertEqual(fill_pubmed(golden["id"], xml_fetcher=fake_fetcher, **golden["options"]), golden["output"])

    def test_fetch_raises_for_missing_article(self):
        with self.assertRaisesRegex(SourceLookupError, "no article matches"):
            parse_pubmed_article("<PubmedArticleSet />", expected_pmid="1")

    def test_public_fill_routes_to_pubmed_source(self):
        self.assertEqual(fill("pmid", "18535242", xml_fetcher=lambda url: pubmed_xml(), add_param_space=True), load_fixture(GOLDEN_DIR, "pubmed_18535242.json")["output"])

    def test_parse_linked_pmid(self):
        self.assertEqual(parse_linked_pmid(pmc_link_xml(), expected_pmcid="137841"), "12384568")

    def test_parse_pmc_article_matches_normalized_fixture(self):
        normalized = load_fixture(NORMALIZED_DIR, "pmc_137841.json")
        article = parse_pubmed_article(pmc_pubmed_xml(), expected_pmid="12384568")
        self.assertEqual(article_fields(article), [(field["name"], field["value"]) for field in normalized["fields"]])

    def test_fill_pmc_matches_golden_fixture_with_fake_fetcher(self):
        golden = load_fixture(GOLDEN_DIR, "pmc_137841.json")

        def fake_fetcher(url: str) -> str:
            if url == pmc_to_pubmed_url(golden["id"]):
                return pmc_link_xml()
            self.assertEqual(url, pubmed_url("12384568"))
            return pmc_pubmed_xml()

        self.assertEqual(fill_pmc(f"PMC{golden['id']}", xml_fetcher=fake_fetcher, **golden["options"]), golden["output"])

    def test_fetch_raises_when_pmc_has_no_linked_pubmed_article(self):
        with self.assertRaisesRegex(SourceLookupError, "no PubMed article is linked"):
            parse_linked_pmid("<eLinkResult />", expected_pmcid="1")

    def test_public_fill_routes_to_pmc_source(self):
        def fake_fetcher(url: str) -> str:
            if url == pmc_to_pubmed_url("137841"):
                return pmc_link_xml()
            return pmc_pubmed_xml()

        self.assertEqual(fill("pmc", "137841", xml_fetcher=fake_fetcher, add_param_space=True), load_fixture(GOLDEN_DIR, "pmc_137841.json")["output"])


if __name__ == "__main__":
    unittest.main()
