import json
import unittest
from pathlib import Path

from wikipedia_template_filler import fill
from wikipedia_template_filler.sources.pubmed import (
    SourceLookupError,
    article_fields,
    expand_month,
    fill_pubmed,
    normalize_pages,
    normalize_pmid,
    parse_pubmed_article,
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


class PubMedTests(unittest.TestCase):
    def test_normalize_pmid(self):
        self.assertEqual(normalize_pmid("PMID: 18535242"), "18535242")

    def test_pubmed_url(self):
        self.assertEqual(
            pubmed_url("18535242"),
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=18535242&retmode=xml",
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
