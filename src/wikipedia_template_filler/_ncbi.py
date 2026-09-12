"""Shared NCBI E-utilities query helpers."""

from __future__ import annotations

import os

NCBI_API_KEY_ENV = "NCBI_API_KEY"
NCBI_EMAIL_ENV = "NCBI_EMAIL"
NCBI_TOOL = "wikipedia-template-filler"


def ncbi_query_params(params: dict[str, str]) -> dict[str, str]:
    """Return E-utilities query parameters with optional NCBI credentials."""
    query_params = dict(params)
    api_key = os.environ.get(NCBI_API_KEY_ENV, "").strip()
    email = os.environ.get(NCBI_EMAIL_ENV, "").strip()
    if api_key:
        query_params["api_key"] = api_key
    if email:
        query_params["tool"] = NCBI_TOOL
        query_params["email"] = email
    return query_params
