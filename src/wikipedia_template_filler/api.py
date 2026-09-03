"""Public API for Wikipedia template filling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


class TemplateFillerError(Exception):
    """Base exception for wikipedia-template-filler errors."""


class UnknownSourceError(TemplateFillerError):
    """Raised when a source type is not recognized."""


class UnsupportedSourceError(TemplateFillerError):
    """Raised when a recognized source is intentionally unsupported."""


class NotImplementedSourceError(TemplateFillerError, NotImplementedError):
    """Raised when a recognized source has not been ported yet."""


@dataclass(frozen=True)
class SourceSpec:
    """Description of a public identifier source handled by the filler."""

    source_type: str
    template: str
    status: str
    aliases: tuple[str, ...] = ()
    message: str | None = None


SUPPORTED_SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec("pubmed_id", "cite journal", "supported", aliases=("pmid", "pubmed")),
    SourceSpec(
        "pubmedcentral_id",
        "cite journal",
        "supported",
        aliases=("pmc", "pmcid", "pubmed_central_id"),
    ),
    SourceSpec("hgnc_id", "infobox protein", "supported", aliases=("hgnc",)),
    SourceSpec("isbn", "cite book", "supported"),
    SourceSpec("pubchem_cid", "infobox drug", "supported", aliases=("pubchem", "cid", "drug")),
    SourceSpec("pubchem_id", "chembox", "supported", aliases=("chembox", "pubchem_chembox")),
    SourceSpec(
        "url",
        "cite web",
        "pending",
        aliases=("cite_web", "web"),
        message="URL -> {{cite web}} lookup is recognized but has not been ported yet.",
    ),
    SourceSpec(
        "drugbank_id",
        "drugbox",
        "unsupported",
        aliases=("drugbank",),
        message=(
            "DrugBank/drugbox lookup is currently unsupported because DrugBank no "
            "longer provides unauthenticated public lookup data suitable for this tool."
        ),
    ),
)


def _source_index() -> dict[str, SourceSpec]:
    index: dict[str, SourceSpec] = {}
    for spec in SUPPORTED_SOURCES:
        index[spec.source_type] = spec
        index[spec.source_type.lower()] = spec
        for alias in spec.aliases:
            index[alias] = spec
            index[alias.lower()] = spec
    return index


_SOURCE_INDEX = _source_index()


@dataclass
class TemplateFiller:
    """Generate Wikipedia template markup from public identifiers.

    This is the primary Python API. The implementation is intentionally
    source-oriented so each Perl source can be ported independently while
    preserving a stable caller interface.
    """

    default_options: Mapping[str, object] = field(default_factory=dict)

    def fill(self, source_type: str, identifier: str, **options: object) -> str:
        """Return wiki template markup for *identifier* from *source_type*."""
        spec = self.source_spec(source_type)
        if spec.status == "unsupported":
            raise UnsupportedSourceError(unavailable_source_message(spec))
        if spec.status == "pending":
            raise NotImplementedSourceError(unavailable_source_message(spec))

        merged_options = {**self.default_options, **options}
        if spec.source_type == "isbn":
            from wikipedia_template_filler.sources.isbn import fill_isbn

            return fill_isbn(identifier, **merged_options)
        if spec.source_type == "pubmed_id":
            from wikipedia_template_filler.sources.pubmed import fill_pubmed

            return fill_pubmed(identifier, **merged_options)
        if spec.source_type == "pubmedcentral_id":
            from wikipedia_template_filler.sources.pubmed import fill_pmc

            return fill_pmc(identifier, **merged_options)
        if spec.source_type == "hgnc_id":
            from wikipedia_template_filler.sources.hgnc import fill_hgnc

            return fill_hgnc(identifier, **merged_options)
        if spec.source_type == "pubchem_cid":
            from wikipedia_template_filler.sources.pubchem import fill_pubchem

            return fill_pubchem(identifier, **merged_options)
        if spec.source_type == "pubchem_id":
            from wikipedia_template_filler.sources.pubchem import fill_pubchem_chembox

            return fill_pubchem_chembox(identifier, **merged_options)
        return self._fill_pending_source(spec, identifier, **merged_options)

    def source_spec(self, source_type: str) -> SourceSpec:
        """Return metadata for *source_type*, accepting known aliases."""
        normalized = source_type.strip().lower()
        try:
            return _SOURCE_INDEX[normalized]
        except KeyError as exc:
            known = ", ".join(spec.source_type for spec in SUPPORTED_SOURCES)
            raise UnknownSourceError(f"unknown source type {source_type!r}; expected one of: {known}") from exc

    def _fill_pending_source(self, spec: SourceSpec, identifier: str, **options: object) -> str:
        raise NotImplementedSourceError(unavailable_source_message(spec))


def unavailable_source_message(spec: SourceSpec) -> str:
    """Return a user-facing message for a recognized source that cannot run."""
    if spec.message:
        return spec.message
    if spec.status == "pending":
        return f"{spec.source_type} -> {{{{{spec.template}}}}} lookup is recognized but has not been ported yet."
    return f"{spec.source_type} -> {{{{{spec.template}}}}} lookup is currently unsupported."


def fill(source_type: str, identifier: str, **options: object) -> str:
    """Return wiki template markup for *identifier* from *source_type*.

    Convenience wrapper around :class:`TemplateFiller` for one-off lookups.
    """
    return TemplateFiller().fill(source_type, identifier, **options)
