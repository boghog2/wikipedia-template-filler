"""PubMed lookup through NCBI E-utilities."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from wikipedia_template_filler.api import TemplateFillerError
from wikipedia_template_filler.renderer import render_template

NCBI_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MONTHS = {
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}


class SourceLookupError(TemplateFillerError):
    """Raised when an upstream PubMed lookup fails."""


XmlFetcher = Callable[[str], str]


@dataclass(frozen=True)
class PubMedArticle:
    """Normalized PubMed article data used for citation rendering."""

    vauthors: str
    title: str
    journal: str
    journal_title: str
    volume: str
    issue: str
    pages: str
    date: str
    pmid: str
    pmc: str
    doi: str
    url: str = ""


def fill_pubmed(identifier: str, *, xml_fetcher: XmlFetcher | None = None, **options: object) -> str:
    """Return a ``{{cite journal}}`` template for a PubMed ID."""
    pmid = normalize_pmid(identifier)
    if not pmid:
        raise SourceLookupError("no PubMed ID given")

    xml = (xml_fetcher or fetch_xml)(pubmed_url(pmid))
    article = parse_pubmed_article(
        xml,
        expected_pmid=pmid,
        strip_title_period=not bool(options.get("dont_strip_trailing_period", False)),
    )
    return render_article(article, **options)


def fill_pmc(identifier: str, *, xml_fetcher: XmlFetcher | None = None, **options: object) -> str:
    """Return a ``{{cite journal}}`` template for a PubMed Central ID."""
    pmcid = normalize_pmcid(identifier)
    if not pmcid:
        raise SourceLookupError("no PubMed Central ID given")

    fetcher = xml_fetcher or fetch_xml
    linked_pmid = parse_linked_pmid(fetcher(pmc_to_pubmed_url(pmcid)), expected_pmcid=pmcid)
    article = parse_pubmed_article(
        fetcher(pubmed_url(linked_pmid)),
        expected_pmid=linked_pmid,
        strip_title_period=not bool(options.get("dont_strip_trailing_period", False)),
    )
    if article.pmc and article.pmc != pmcid:
        raise SourceLookupError(f"no article matches the given PubMed Central ID ({pmcid})")
    return render_article(article, **options)


def render_article(article: PubMedArticle, **options: object) -> str:
    """Render normalized article data as a ``{{cite journal}}`` template."""
    return render_template(
        "cite journal",
        article_fields(
            article,
            full_journal_title=bool(options.get("full_journal_title", False)),
            link_journal=bool(options.get("link_journal", False)),
            add_text_url=bool(options.get("add_text_url", False)),
            omit_url_if_doi_filled=bool(options.get("omit_url_if_doi_filled", False)),
            add_accessdate=bool(options.get("add_accessdate", False)),
        ),
        add_param_space=bool(options.get("add_param_space", False)),
        vertical=bool(options.get("vertical", False)),
        include_empty=bool(options.get("extended", False)),
    )


def normalize_pmid(identifier: str) -> str:
    """Return digits only for a PubMed identifier."""
    return re.sub(r"\D", "", identifier)


def normalize_pmcid(identifier: str) -> str:
    """Return digits only for a PubMed Central identifier."""
    return re.sub(r"^\s*PMC", "", identifier, flags=re.IGNORECASE).strip()


def pubmed_url(pmid: str) -> str:
    """Build the NCBI efetch URL for *pmid*."""
    query = urlencode({"db": "pubmed", "id": pmid, "retmode": "xml"})
    return f"{NCBI_EUTILS_BASE}/efetch.fcgi?{query}"


def pmc_to_pubmed_url(pmcid: str) -> str:
    """Build the NCBI elink URL that maps a PMCID to its PubMed ID."""
    query = urlencode({"dbfrom": "pmc", "db": "pubmed", "id": pmcid, "retmode": "xml"})
    return f"{NCBI_EUTILS_BASE}/elink.fcgi?{query}"


def fetch_xml(url: str) -> str:
    """Fetch XML from *url* using the standard library."""
    request = Request(url, headers={"User-Agent": "wikipedia-template-filler/0.1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise SourceLookupError(f"PubMed lookup failed: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise SourceLookupError(f"PubMed lookup failed: {exc.reason}") from exc


def parse_linked_pmid(xml: str, *, expected_pmcid: str | None = None) -> str:
    """Parse an NCBI elink response and return the linked PubMed ID."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SourceLookupError("PubMed Central lookup returned invalid XML") from exc

    for link in root.findall("LinkSet/LinkSetDb/Link/Id"):
        pmid = text(link)
        if pmid:
            return pmid

    if expected_pmcid:
        raise SourceLookupError(f"no PubMed article is linked to PubMed Central ID ({expected_pmcid})")
    raise SourceLookupError("no PubMed article is linked to the given PubMed Central ID")


def parse_pubmed_article(xml: str, *, expected_pmid: str | None = None, strip_title_period: bool = True) -> PubMedArticle:
    """Parse one PubMed efetch XML response into normalized article data."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SourceLookupError("PubMed returned invalid XML") from exc

    article_node = root.find("PubmedArticle")
    if article_node is None:
        raise SourceLookupError(f"no article matches the given PubMed ID ({expected_pmid})")

    medline = article_node.find("MedlineCitation")
    article = medline.find("Article") if medline is not None else None
    journal = article.find("Journal") if article is not None else None
    pubmed_data = article_node.find("PubmedData")

    pmid = text(medline.find("PMID") if medline is not None else None)
    if expected_pmid and pmid != expected_pmid:
        raise SourceLookupError(f"no article matches the given PubMed ID ({expected_pmid})")

    return PubMedArticle(
        vauthors=vancouver_authors(article.find("AuthorList") if article is not None else None),
        title=article_title(text(article.find("ArticleTitle") if article is not None else None), strip_period=strip_title_period),
        journal=text(journal.find("ISOAbbreviation") if journal is not None else None),
        journal_title=text(journal.find("Title") if journal is not None else None),
        volume=text(journal.find("JournalIssue/Volume") if journal is not None else None),
        issue=text(journal.find("JournalIssue/Issue") if journal is not None else None),
        pages=normalize_pages(text(article.find("Pagination/MedlinePgn") if article is not None else None)),
        date=publication_date(journal.find("JournalIssue/PubDate") if journal is not None else None),
        pmid=pmid,
        pmc=article_id(pubmed_data, "pmc").removeprefix("PMC"),
        doi=article_id(pubmed_data, "doi") or text(article.find('ELocationID[@EIdType="doi"]') if article is not None else None),
    )


def article_fields(
    article: PubMedArticle,
    *,
    full_journal_title: bool = False,
    link_journal: bool = False,
    add_text_url: bool = False,
    omit_url_if_doi_filled: bool = False,
    add_accessdate: bool = False,
) -> list[tuple[str, str]]:
    """Return ordered ``{{cite journal}}`` fields for a PubMed article."""
    journal = article.journal_title if full_journal_title and article.journal_title else article.journal
    if link_journal and journal:
        journal = f"[[{journal}]]"
    url = f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/" if add_text_url and article.pmid else article.url
    if omit_url_if_doi_filled and article.doi:
        url = ""
    accessdate = current_accessdate() if add_accessdate and url else ""
    return [
        ("vauthors", article.vauthors),
        ("title", article.title),
        ("journal", journal),
        ("volume", article.volume),
        ("issue", article.issue),
        ("pages", article.pages),
        ("date", article.date),
        ("pmid", article.pmid),
        ("pmc", article.pmc),
        ("doi", article.doi),
        ("url", url),
        ("accessdate", accessdate),
    ]


def current_accessdate() -> str:
    """Return today's date in the citation access-date style."""
    return date.today().strftime("%-d %B %Y")


def text(node: ET.Element | None) -> str:
    """Return concatenated text for an XML node."""
    if node is None:
        return ""
    return unescape("".join(node.itertext()).strip())


def article_title(value: str, *, strip_period: bool = True) -> str:
    """Return the article title, optionally preserving a final period."""
    return strip_trailing_period(value) if strip_period else value


def strip_trailing_period(value: str) -> str:
    """Match Perl behavior by stripping one trailing article-title period."""
    return value[:-1] if value.endswith(".") else value


def normalize_pages(value: str) -> str:
    """Use en dashes in page ranges, matching the Perl golden output."""
    return value.replace("-", "–")


def publication_date(pub_date: ET.Element | None) -> str:
    """Return a citation date from a PubMed ``PubDate`` node."""
    if pub_date is None:
        return ""
    year = text(pub_date.find("Year"))
    month = expand_month(text(pub_date.find("Month")))
    return " ".join(part for part in (month, year) if part)


def expand_month(month: str) -> str:
    """Expand NCBI three-letter month abbreviations."""
    return MONTHS.get(month[:3].lower(), month)


def vancouver_authors(author_list: ET.Element | None) -> str:
    """Return PubMed authors as Vancouver-style names."""
    if author_list is None:
        return ""
    authors = []
    for author in author_list.findall("Author"):
        last = text(author.find("LastName"))
        initials = text(author.find("Initials"))[:2]
        if last:
            authors.append(f"{last} {initials}" if initials else last)
    return ", ".join(authors)


def article_id(pubmed_data: ET.Element | None, id_type: str) -> str:
    """Return an article identifier by PubMed ``IdType``."""
    if pubmed_data is None:
        return ""
    for node in pubmed_data.findall("ArticleIdList/ArticleId"):
        if node.attrib.get("IdType", "").lower() == id_type.lower():
            return text(node)
    return ""
