"""T90-3 F09 staging-only endpoint: PDF -> true multipage TIFF.

Never loaded into the public OpenAPI schema until independently opted in.
All queue jobs use the existing owner, quota, audit and retention contracts.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import FileRecord
from app.routers.pdf import _create_job, _is_expired
from app.schemas import JobOut
from app.security import Principal, require_scope
from app.services.from_pdf_tiff import MAX_SOURCE_BYTES

router = APIRouter(prefix="/api/v1/pdf/from-pdf", tags=["from-pdf (staged)"])
settings = get_settings()


class PdfToTiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=150, strict=True, ge=72, le=300)


@router.post("/tiff", status_code=202, response_model=JobOut)
def pdf_to_tiff(
    req: PdfToTiffRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="File not found")
    # Staged tools are intentionally stricter than bootstrap-admin legacy flows.
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File is owned by a different account")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="A verified PDF source is required")
    if not 16 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds TIFF conversion budget")
    return _create_job(db, principal, "pdf-to-tiff", [req.file_id], {"dpi": req.dpi})


class PdfToGifRequest(BaseModel):
    """F16 animation: every PDF page is one 256-color GIF frame."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=96, strict=True, ge=72, le=150)
    frame_ms: int = Field(default=1200, strict=True, ge=300, le=5000)


@router.post("/gif", status_code=202, response_model=JobOut)
def pdf_to_gif(
    req: PdfToGifRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="File not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another account")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="Source PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="A verified PDF source is required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source PDF exceeds GIF conversion budget")
    return _create_job(
        db, principal, "pdf-to-gif", [req.file_id],
        {"dpi": req.dpi, "frame_ms": req.frame_ms},
    )


class PdfToBmpRequest(BaseModel):
    """F17 multi-output: PDF pages are individual BMPs inside one ZIP."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=96, strict=True, ge=72, le=150)


@router.post("/bmp", status_code=202, response_model=JobOut)
def pdf_to_bmp(
    req: PdfToBmpRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="Source exceeds BMP raster budget")
    return _create_job(db, principal, "pdf-to-bmp", [req.file_id], {"dpi": req.dpi})


class PdfToSvgRequest(BaseModel):
    """F12: one isolated SVG image per source page, returned as a ZIP."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/svg", status_code=202, response_model=JobOut)
def pdf_to_svg(
    req: PdfToSvgRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_svg import MAX_SOURCE_BYTES as SVG_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= SVG_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="Source exceeds SVG export budget")
    return _create_job(db, principal, "pdf-to-svg", [req.file_id], {})


class PdfToCsvRequest(BaseModel):
    """F13 only exports fully ruled text-only PDF tables."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/csv", status_code=202, response_model=JobOut)
def pdf_to_csv(
    req: PdfToCsvRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_csv import MAX_SOURCE_BYTES as CSV_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= CSV_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF table exceeds CSV extractor budget")
    return _create_job(db, principal, "pdf-to-csv", [req.file_id], {})


class PdfToRtfRequest(BaseModel):
    """F14: editable paragraphs from unambiguous selectable text only."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/rtf", status_code=202, response_model=JobOut)
def pdf_to_rtf(
    req: PdfToRtfRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_rtf import MAX_SOURCE_BYTES as RTF_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= RTF_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds text-only RTF budget")
    return _create_job(db, principal, "pdf-to-rtf", [req.file_id], {})


class PdfToOdtRequest(BaseModel):
    """F10: narrowly editable single-column PDF text in true ODF format."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/odt", status_code=202, response_model=JobOut)
def pdf_to_odt(
    req: PdfToOdtRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_rtf import MAX_SOURCE_BYTES as ODT_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= ODT_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="Source exceeds editable text-only ODT budget")
    return _create_job(db, principal, "pdf-to-odt", [req.file_id], {})


class PdfToDocxRequest(BaseModel):
    """F02/F06: editable Word DOCX, never mislabelled legacy binary DOC."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


def _submit_text_docx(req: PdfToDocxRequest, principal: Principal,
                      db: Session, operation: str) -> JobOut:
    from app.services.from_pdf_rtf import MAX_SOURCE_BYTES as DOCX_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= DOCX_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds text-only DOCX budget")
    return _create_job(db, principal, operation, [req.file_id], {})


@router.post("/docx", status_code=202, response_model=JobOut)
def pdf_to_docx(
    req: PdfToDocxRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    return _submit_text_docx(req, principal, db, "pdf-to-docx")


@router.post("/word", status_code=202, response_model=JobOut)
def pdf_to_word(
    req: PdfToDocxRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    return _submit_text_docx(req, principal, db, "pdf-to-word")


class PdfToExcelRequest(BaseModel):
    """F07: only fully ruled PDF tables become editable XLSX sheets."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/excel", status_code=202, response_model=JobOut)
def pdf_to_excel(
    req: PdfToExcelRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_csv import MAX_SOURCE_BYTES as XLSX_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= XLSX_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds table XLSX input budget")
    return _create_job(db, principal, "pdf-to-excel", [req.file_id], {})


class PdfToEpubRequest(BaseModel):
    """F05: EPUB3 only for reflowable selectable PDF text."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/epub", status_code=202, response_model=JobOut)
def pdf_to_epub(
    req: PdfToEpubRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_rtf import MAX_SOURCE_BYTES as EPUB_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= EPUB_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds text-only EPUB budget")
    return _create_job(db, principal, "pdf-to-epub", [req.file_id], {})


class PdfToRasterRequest(BaseModel):
    """F03/F04: strict PDF page export into a complete ordered image ZIP."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)
    dpi: int = Field(default=96, strict=True, ge=72, le=200)


def _submit_pdf_raster(req: PdfToRasterRequest, principal: Principal,
                       db: Session, operation: str) -> JobOut:
    from app.services.from_pdf_raster import MAX_SOURCE_BYTES as RASTER_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= RASTER_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds raster export budget")
    return _create_job(db, principal, operation, [req.file_id], {"dpi": req.dpi})


@router.post("/jpg", status_code=202, response_model=JobOut)
def pdf_to_jpg(
    req: PdfToRasterRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    return _submit_pdf_raster(req, principal, db, "pdf-to-jpg")


@router.post("/png", status_code=202, response_model=JobOut)
def pdf_to_png(
    req: PdfToRasterRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    return _submit_pdf_raster(req, principal, db, "pdf-to-png")


class PdfToPptRequest(BaseModel):
    """F08 Word-like single-column PDF pages -> modern editable PPTX slides."""
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


@router.post("/ppt", status_code=202, response_model=JobOut)
def pdf_to_ppt(
    req: PdfToPptRequest,
    principal: Principal = Depends(require_scope("pdf:pdf-to-image")),
    db: Session = Depends(get_db),
):
    from app.services.from_pdf_rtf import MAX_SOURCE_BYTES as PPTX_MAX_SOURCE
    if not settings.from_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="T90-3 conversion is disabled")
    source = db.get(FileRecord, req.file_id)
    if source is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    if source.source_system != principal.name:
        raise HTTPException(status_code=403, detail="PDF belongs to another owner")
    if _is_expired(source):
        raise HTTPException(status_code=410, detail="PDF has expired")
    if (source.content_type != "application/pdf"
            or not source.original_name.lower().endswith(".pdf")):
        raise HTTPException(status_code=415, detail="Verified PDF required")
    if not 24 <= source.size <= PPTX_MAX_SOURCE:
        raise HTTPException(status_code=413, detail="PDF exceeds PPTX text-only budget")
    return _create_job(db, principal, "pdf-to-ppt", [req.file_id], {})
