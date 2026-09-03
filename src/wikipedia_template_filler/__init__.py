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
from .renderer import TemplateField, fields_from_mapping, render_template

__all__ = [
    "NotImplementedSourceError",
    "SourceSpec",
    "TemplateFiller",
    "TemplateFillerError",
    "UnknownSourceError",
    "UnsupportedSourceError",
    "TemplateField",
    "fields_from_mapping",
    "fill",
    "render_template",
]
__version__ = "0.1.0"
