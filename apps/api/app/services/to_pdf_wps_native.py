"""Experimental Microsoft Works WPS text import via independent writerperfect.

The pinned Gotenberg LibreOffice direct .wps import previously returned a
valid but blank PDF for authentic Works documents. This alternative pipeline
converts WPS to an ODT package with writerperfect's dedicated wps2odt reader,
validates real printable output and only then converts the ODT using the
existing LibreOffice/PDF checker.

No Kingsoft .wps, password-protected content or guarantee of complete
proprietary Works layout is implied. This module is UNTESTED, not routed,
and gated off until native input sandboxing and real-file comparisons.
"""
from __future__ import annotations

from pathlib import Path
import resource
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from app.config import get_settings
from app.services.zip_preflight import _checked_office_members
from app.services.native_sandbox import SANDBOX_INPUT, isolated_native_command
from app.services.native_output_guard import copy_native_regular_output

MAX_WPS_BYTES = 12 * 1024 * 1024
MAX_ODT_BYTES = 20 * 1024 * 1024
MAX_CONTENT_XML_BYTES = 6 * 1024 * 1024
WPS_CONVERTER = Path("/usr/bin/wps2odt")
ODF_TEXT_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
ODF_OFFICE_NAMESPACE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
WORKS_TIMEOUT_SECONDS = 30


def _wps_resource_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_ODT_BYTES, MAX_ODT_BYTES))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))


def _validated_works_odt(document: Path) -> int:
    """Require a native reader-produced ODT with actual printable text.

    A ZIP/ODT package merely being valid is NOT evidence Works was decoded;
    some unsupported source formats silently generate an empty document.
    """
    # The low-trust native converter controls /output. Reject symlinks,
    # including links to host paths outside its writable task directory.
    # is_file()/stat() alone would follow those links in the trusted worker.
    if (document.is_symlink() or not document.is_file()
            or not 256 <= document.stat().st_size <= MAX_ODT_BYTES):
        raise ValueError("Works importer produced no usable regular ODT package")
    try:
        with ZipFile(document) as package:
            members = _checked_office_members(package)
            mime_member = members.get("mimetype")
            content_member = members.get("content.xml")
            if (mime_member is None or content_member is None
                    or mime_member.file_size > 256
                    or not 0 < content_member.file_size <= MAX_CONTENT_XML_BYTES):
                raise ValueError("Works importer omitted required ODT contents")
            mimetype = package.read(mime_member)
            if mimetype != b"application/vnd.oasis.opendocument.text":
                raise ValueError("Works importer ODT mimetype mismatched")
            source = package.read(content_member)
            if len(source) != content_member.file_size:
                raise ValueError("Works importer generated partial document content")
            root = SafeET.fromstring(source)
    except (BadZipFile, OSError, EOFError, RuntimeError, SafeET.ParseError,
            DefusedXmlException) as exc:
        raise ValueError("Works importer returned malformed ODT") from exc

    if root.tag != "{" + ODF_OFFICE_NAMESPACE + "}document-content":
        raise ValueError("Works ODT has invalid document structure")
    printable_chunks: list[str] = []
    nodes_seen = 0
    printable_count = 0
    for node in root.iter():
        nodes_seen += 1
        if nodes_seen > 30_000:
            raise ValueError("Works importer ODT XML complexity exceeds limits")
        if node.tag in {
            "{" + ODF_TEXT_NAMESPACE + "}p",
            "{" + ODF_TEXT_NAMESPACE + "}h",
        }:
            # Count only the paragraph's direct text/tails, avoiding
            # quadratic nested paragraph expansion.
            paragraph = "".join(node.itertext())
            printable_count += len(paragraph)
            if printable_count > 200_000:
                raise ValueError("Works imported text exceeds supported limits")
            printable_chunks.append(paragraph)
    if not "".join(printable_chunks).strip():
        raise ValueError("Works importer produced blank source text")
    return printable_count


def wps_works_to_pdf(source: Path, output: Path) -> None:
    """Development-only WPS -> ODT -> Gotenberg PDF pipeline."""
    if source.resolve() == output.resolve():
        raise ValueError("Works source and PDF must differ")
    settings = get_settings()
    if not settings.to_pdf_tools_enabled or not settings.wps_native_dev_enabled:
        raise RuntimeError("Works WPS importer is disabled")
    if not 16 <= source.stat().st_size <= MAX_WPS_BYTES:
        raise ValueError("Works WPS source size unsupported")
    # No password / output-format / encoding flags supplied by user.
    if not WPS_CONVERTER.is_file():
        raise ValueError("Dedicated wps2odt native importer is unavailable")

    with (TemporaryDirectory(prefix="pdfhub-works-wps-native-") as folder,
          TemporaryDirectory(prefix="pdfhub-works-wps-trusted-") as trusted):
        native_odt = Path(folder) / "document.odt"
        verified_odt = Path(trusted) / "document.odt"
        try:
            command = isolated_native_command(
                source, Path(folder),
                [str(WPS_CONVERTER), SANDBOX_INPUT, "/output/document.odt"],
            )
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                start_new_session=True,
                close_fds=True,
                preexec_fn=_wps_resource_limits,
                timeout=WORKS_TIMEOUT_SECONDS,
                env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Works native importer timed out or failed to start") from exc
        if result.returncode != 0:
            raise ValueError("Works native importer rejected the document")
        # Never let Gotenberg or the ODT parser reopen a path that the
        # sandboxed native process controlled. The trusted copy is outside
        # /output and cannot be rewritten by a compromised native decoder.
        copy_native_regular_output(
            native_odt, verified_odt,
            maximum_bytes=MAX_ODT_BYTES, minimum_bytes=256,
        )
        _validated_works_odt(verified_odt)

        # Gotenberg's LibreOffice import of genuine .odt works normally.
        # _checked_pdf rejects HTTP 200 outputs that are blank/invisible.
        from app.services.to_pdf_engine import office_document_to_pdf
        office_document_to_pdf(verified_odt, output, original_suffix=".odt")
