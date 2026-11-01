"""Bounded PPTX/ODP slide inventory for fail-closed PDF page-count checks.

A nonblank first page does not imply the other slides survived conversion.
Count declared source slides and require exactly as many result pages before
writing the artifact. Does not prove slide content/typography equivalence.
"""
from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from app.services.zip_preflight import _checked_office_members

PRESENTATIONML = "http://schemas.openxmlformats.org/presentationml/2006/main"
ODF_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
ODF_DRAW = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"

MAX_SLIDE_XML_BYTES = 4 * 1024 * 1024
MAX_EXPECTED_SLIDES = 300


def expected_slide_pages(source: Path, *, original_suffix: str) -> int | None:
    """Determine printed slide count, or None for non-presentation formats.

    PPTX counts explicit p:sldId entries (including hidden slides; strict
    mismatch is preferable to a silently truncated export). ODP counts the
    direct draw:page children of office:presentation. Unsupported structure
    raises rather than allowing a potentially incomplete PDF to be delivered.
    """
    if original_suffix not in {".pptx", ".odp"}:
        return None
    member_path = "ppt/presentation.xml" if original_suffix == ".pptx" else "content.xml"
    try:
        with ZipFile(source) as archive:
            members = _checked_office_members(archive)
            info = members.get(member_path.casefold())
            if info is None or not 0 < info.file_size <= MAX_SLIDE_XML_BYTES:
                raise ValueError("Presentation slide inventory absent or oversized")
            payload = archive.read(info)
            if len(payload) != info.file_size:
                raise ValueError("Presentation XML length mismatch")
            root = SafeET.fromstring(payload)
    except (BadZipFile, OSError, EOFError, RuntimeError, DefusedXmlException,
            SafeET.ParseError, UnicodeError) as exc:
        raise ValueError("Presentation slide inventory invalid or unsafe") from exc

    if original_suffix == ".pptx":
        if root.tag != "{" + PRESENTATIONML + "}presentation":
            raise ValueError("PPTX presentation root is invalid")
        lists = root.findall("{" + PRESENTATIONML + "}sldIdLst")
        if len(lists) != 1:
            raise ValueError("PPTX slide inventory is missing or ambiguous")
        entries = list(lists[0])
        if any(entry.tag != "{" + PRESENTATIONML + "}sldId" for entry in entries):
            raise ValueError("PPTX contains unsupported slide references")
    else:
        if root.tag != "{" + ODF_OFFICE + "}document-content":
            raise ValueError("ODP content root is invalid")
        body = root.find("{" + ODF_OFFICE + "}body")
        if body is None:
            raise ValueError("ODP body missing")
        presentation = body.find("{" + ODF_OFFICE + "}presentation")
        if presentation is None:
            raise ValueError("ODP presentation missing")
        entries = presentation.findall("{" + ODF_DRAW + "}page")

    count = len(entries)
    if not 1 <= count <= MAX_EXPECTED_SLIDES:
        raise ValueError("Presentation slide count outside supported limits")
    return count
