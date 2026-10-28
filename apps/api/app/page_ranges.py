"""Canonical bounded qpdf page-range syntax for existing split/rotate operations.

This validates syntax only. The selected PDF's actual page count is checked by
qpdf at execution time; this module never reads an untrusted document.
Supported: 1, 1-3, 1-z, z-1, 3-1, 2,4-6. Descending ranges preserve
qpdf's existing reverse-page semantics.
"""
from __future__ import annotations

import re

MAX_PAGE_RANGE_LENGTH = 256
MAX_PAGE_NUMBER = 100_000
PAGE_ENDPOINT = r"(?:[1-9][0-9]{0,5}|z)"
PAGE_RANGE_RE = re.compile(
    rf"{PAGE_ENDPOINT}(?:-{PAGE_ENDPOINT})?(?:,{PAGE_ENDPOINT}(?:-{PAGE_ENDPOINT})?)*"
)


def validated_page_range(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_PAGE_RANGE_LENGTH:
        raise ValueError("pages must be a nonempty range of at most 256 characters")
    if PAGE_RANGE_RE.fullmatch(value) is None:
        raise ValueError("invalid pages range: expected 1,2-4,5-z or z-1")
    for section in value.split(","):
        for endpoint in section.split("-"):
            if endpoint != "z" and int(endpoint) > MAX_PAGE_NUMBER:
                raise ValueError("page number exceeds 100000")
    return value
