"""Python port of WWW::Wikipedia::TemplateFiller."""

from .api import (
    NotImplementedSourceError,
    SourceSpec,
    TemplateFiller,
    TemplateFillerError,
    UnknownSourceError,
    UnsupportedSourceError,
    fill,
)

__all__ = [
    "NotImplementedSourceError",
    "SourceSpec",
    "TemplateFiller",
    "TemplateFillerError",
    "UnknownSourceError",
    "UnsupportedSourceError",
    "fill",
]
__version__ = "0.1.0"
