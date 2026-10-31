"""T90-2 explicit opt-in conversion dispatch; never part of legacy ADAPTERS."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from fastapi import HTTPException

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services import to_pdf_engine

# Operation -> required persisted MIME and original upload suffix.
STAGED_TO_PDF_INPUTS: Mapping[str, tuple[str, str]] = {
    "txt-to-pdf": ("text/plain", ".txt"),
    "csv-to-pdf": ("text/csv", ".csv"),
    "md-to-pdf": ("text/markdown", ".md"),
    "svg-to-pdf": ("image/svg+xml", ".svg"),
    "dxf-to-pdf": ("image/vnd.dxf", ".dxf"),
    "djvu-to-pdf": ("image/vnd.djvu", ".djvu"),
    "xps-to-pdf": ("application/vnd.ms-xpsdocument", ".xps"),
    "ai-to-pdf": ("application/vnd.adobe.illustrator", ".ai"),
    "epub-to-pdf": ("application/epub+zip", ".epub"),
    "fb2-to-pdf": ("application/x-fictionbook+xml", ".fb2"),
    "mobi-to-pdf": ("application/x-mobipocket-ebook", ".mobi"),
    "html-to-pdf": ("text/html", ".html"),
    "xml-to-pdf": ("application/xml", ".xml"),
    "eml-to-pdf": ("message/rfc822", ".eml"),
    "zip-to-pdf": ("application/zip", ".zip"),
    "cbz-to-pdf": ("application/vnd.comicbook+zip", ".cbz"),
    "cbr-to-pdf": ("application/vnd.comicbook-rar", ".cbr"),
    "jfif-to-pdf": ("image/jpeg", ".jfif"),
    "gif-to-pdf": ("image/gif", ".gif"),
    "tiff-to-pdf": ("image/tiff", ".tiff"),
    "doc-to-pdf": ("application/msword", ".doc"),
    "docx-to-pdf": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    "xls-to-pdf": ("application/vnd.ms-excel", ".xls"),
    "xlsx-to-pdf": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "ppt-to-pdf": ("application/vnd.ms-powerpoint", ".ppt"),
    "pptx-to-pdf": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "odt-to-pdf": ("application/vnd.oasis.opendocument.text", ".odt"),
    "ods-to-pdf": ("application/vnd.oasis.opendocument.spreadsheet", ".ods"),
    "odp-to-pdf": ("application/vnd.oasis.opendocument.presentation", ".odp"),
    "rtf-to-pdf": ("application/rtf", ".rtf"),
    "pub-to-pdf": ("application/x-mspublisher", ".pub"),
    "hwp-to-pdf": ("application/x-hwp", ".hwp"),
    "pages-to-pdf": ("application/vnd.apple.pages", ".pages"),
    "jpg-to-pdf": ("image/jpeg", ".jpg"),
    "jpeg-to-pdf": ("image/jpeg", ".jpeg"),
    "png-to-pdf": ("image/png", ".png"),
    "webp-to-pdf": ("image/webp", ".webp"),
    "bmp-to-pdf": ("image/bmp", ".bmp"),
}
STAGED_TO_PDF_OPERATIONS = frozenset(STAGED_TO_PDF_INPUTS)
OFFICE_TO_PDF_OPERATIONS = frozenset({
    "doc-to-pdf", "docx-to-pdf", "xls-to-pdf", "xlsx-to-pdf",
    "ppt-to-pdf", "pptx-to-pdf", "odt-to-pdf", "ods-to-pdf",
    "odp-to-pdf", "rtf-to-pdf", "pub-to-pdf", "pages-to-pdf", "hwp-to-pdf",
})


def checked_source(operation: str, path: Path, *, name: str, mime: str) -> None:
    if operation not in STAGED_TO_PDF_INPUTS:
        raise ValueError("Unsupported staged conversion")
    expected_mime, suffix = STAGED_TO_PDF_INPUTS[operation]
    original_suffix = Path(name).suffix.lower()
    if mime != expected_mime or original_suffix not in (
        (".tif", ".tiff") if suffix == ".tiff" else (suffix,)
    ):
        raise ValueError("Format and persisted MIME do not match the requested conversion")
    try:
        actual_mime = validate_uploaded_file(path, name)
    except HTTPException as exc:
        raise ValueError("Uploaded format signature no longer validates") from exc
    if actual_mime != expected_mime:
        raise ValueError("Uploaded format signature does not match persisted MIME")


def execute_staged_to_pdf_operation(
    operation: str, inputs: list[Path], output: Path, params: dict,
    *, original_name: str, content_type: str,
) -> None:
    if not get_settings().to_pdf_tools_enabled:
        raise RuntimeError("Staged T90-2 tools are disabled")
    if operation not in STAGED_TO_PDF_OPERATIONS or len(inputs) != 1 or params:
        raise ValueError("Unknown staged conversion, input count or parameters")
    checked_source(operation, inputs[0], name=original_name, mime=content_type)
    if operation == "txt-to-pdf":
        to_pdf_engine.text_to_pdf(inputs[0], output)
    elif operation == "csv-to-pdf":
        to_pdf_engine.csv_to_pdf(inputs[0], output)
    elif operation == "md-to-pdf":
        to_pdf_engine.markdown_to_pdf(inputs[0], output)
    elif operation == "svg-to-pdf":
        to_pdf_engine.svg_to_pdf(inputs[0], output)
    elif operation == "dxf-to-pdf":
        from app.services.to_pdf_dxf import restricted_dxf_to_pdf
        restricted_dxf_to_pdf(inputs[0], output)
    elif operation == "djvu-to-pdf":
        from app.services.to_pdf_djvu import restricted_djvu_to_pdf
        restricted_djvu_to_pdf(inputs[0], output)
    elif operation == "xps-to-pdf":
        from app.services.to_pdf_special import restricted_xps_to_pdf
        restricted_xps_to_pdf(inputs[0], output)
    elif operation == "ai-to-pdf":
        from app.services.to_pdf_special import pdf_compatible_ai_to_pdf
        pdf_compatible_ai_to_pdf(inputs[0], output)
    elif operation == "epub-to-pdf":
        to_pdf_engine.epub_to_pdf(inputs[0], output)
    elif operation == "fb2-to-pdf":
        to_pdf_engine.fb2_to_pdf(inputs[0], output)
    elif operation == "mobi-to-pdf":
        from app.services.to_pdf_mobi import restricted_mobi_to_pdf
        restricted_mobi_to_pdf(inputs[0], output)
    elif operation == "html-to-pdf":
        to_pdf_engine.html_to_pdf(source=inputs[0], output=output)
    elif operation == "xml-to-pdf":
        to_pdf_engine.xml_to_pdf(source=inputs[0], output=output)
    elif operation == "eml-to-pdf":
        to_pdf_engine.eml_to_pdf(source=inputs[0], output=output)
    elif operation == "cbr-to-pdf":
        from app.services.to_pdf_cbr import rar4_stored_cbr_to_pdf
        rar4_stored_cbr_to_pdf(inputs[0], output)
    elif operation in {"zip-to-pdf", "cbz-to-pdf"}:
        to_pdf_engine.archive_images_to_pdf(
            inputs[0], output, kind=operation.split("-", 1)[0]
        )
    elif operation in OFFICE_TO_PDF_OPERATIONS:
        to_pdf_engine.office_document_to_pdf(
            inputs[0], output, original_suffix=Path(original_name).suffix.lower()
        )
    else:
        to_pdf_engine.image_frames_to_pdf(
            inputs[0], output, kind=operation.split("-", 1)[0]
        )
