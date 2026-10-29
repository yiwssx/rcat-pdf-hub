"""T90-2 opt-in format-specific routes, absent from default OpenAPI."""
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
from app.staged_to_pdf_adapters import STAGED_TO_PDF_INPUTS

router = APIRouter(prefix="/api/v1/pdf/to-pdf", tags=["T90-2 (staged)"])
settings = get_settings()


class ConvertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: str = Field(min_length=1, max_length=36)


def _submit(req: ConvertRequest, principal: Principal, db: Session, operation: str) -> JobOut:
    if not settings.to_pdf_tools_enabled:
        raise HTTPException(status_code=404, detail="Staged conversion is disabled")
    record = db.get(FileRecord, req.file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="File not found")
    if record.source_system != principal.name:
        raise HTTPException(status_code=403, detail="File belongs to another owner")
    if _is_expired(record):
        raise HTTPException(status_code=410, detail="File data has expired")
    mime, suffix = STAGED_TO_PDF_INPUTS[operation]
    extensions = (".tif", ".tiff") if suffix == ".tiff" else (suffix,)
    if record.content_type != mime or not record.original_name.lower().endswith(extensions):
        raise HTTPException(status_code=415, detail="Uploaded format does not match conversion")
    return _create_job(db, principal, operation, [req.file_id], {})


@router.post("/txt", response_model=JobOut, status_code=202)
def txt_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:convert")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "txt-to-pdf")


@router.post("/csv", response_model=JobOut, status_code=202)
def csv_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:convert")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "csv-to-pdf")


@router.post("/md", response_model=JobOut, status_code=202)
def md_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:convert")),
              db: Session = Depends(get_db)):
    return _submit(req, principal, db, "md-to-pdf")


@router.post("/jfif", response_model=JobOut, status_code=202)
def jfif_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
                db: Session = Depends(get_db)):
    return _submit(req, principal, db, "jfif-to-pdf")


@router.post("/gif", response_model=JobOut, status_code=202)
def gif_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
               db: Session = Depends(get_db)):
    return _submit(req, principal, db, "gif-to-pdf")


@router.post("/tiff", response_model=JobOut, status_code=202)
def tiff_to_pdf(req: ConvertRequest, principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
                db: Session = Depends(get_db)):
    return _submit(req, principal, db, "tiff-to-pdf")


@router.post("/doc", response_model=JobOut, status_code=202)
def doc_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "doc-to-pdf")


@router.post("/docx", response_model=JobOut, status_code=202)
def docx_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "docx-to-pdf")


@router.post("/xls", response_model=JobOut, status_code=202)
def xls_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "xls-to-pdf")


@router.post("/xlsx", response_model=JobOut, status_code=202)
def xlsx_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "xlsx-to-pdf")


@router.post("/ppt", response_model=JobOut, status_code=202)
def ppt_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "ppt-to-pdf")


@router.post("/pptx", response_model=JobOut, status_code=202)
def pptx_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "pptx-to-pdf")


@router.post("/odt", response_model=JobOut, status_code=202)
def odt_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "odt-to-pdf")


@router.post("/ods", response_model=JobOut, status_code=202)
def ods_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "ods-to-pdf")


@router.post("/odp", response_model=JobOut, status_code=202)
def odp_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "odp-to-pdf")


@router.post("/rtf", response_model=JobOut, status_code=202)
def rtf_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "rtf-to-pdf")


@router.post("/jpg", response_model=JobOut, status_code=202)
def jpg_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "jpg-to-pdf")


@router.post("/jpeg", response_model=JobOut, status_code=202)
def jpeg_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "jpeg-to-pdf")


@router.post("/png", response_model=JobOut, status_code=202)
def png_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "png-to-pdf")


@router.post("/webp", response_model=JobOut, status_code=202)
def webp_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "webp-to-pdf")


@router.post("/bmp", response_model=JobOut, status_code=202)
def bmp_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:image-to-pdf")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "bmp-to-pdf")


@router.post("/html", response_model=JobOut, status_code=202)
def html_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "html-to-pdf")

@router.post("/xml", response_model=JobOut, status_code=202)
def xml_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "xml-to-pdf")

@router.post("/eml", response_model=JobOut, status_code=202)
def eml_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "eml-to-pdf")

@router.post("/zip", response_model=JobOut, status_code=202)
def zip_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "zip-to-pdf")

@router.post("/cbr", response_model=JobOut, status_code=202)
def restricted_stored_rar4_cbr_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "cbr-to-pdf")


@router.post("/cbz", response_model=JobOut, status_code=202)
def cbz_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "cbz-to-pdf")


@router.post("/epub", response_model=JobOut, status_code=202)
def epub_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "epub-to-pdf")


@router.post("/hwp", response_model=JobOut, status_code=202)
def legacy_hwp3_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "hwp-to-pdf")


@router.post("/pub", response_model=JobOut, status_code=202)
def publisher_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "pub-to-pdf")


@router.post("/mobi", response_model=JobOut, status_code=202)
def restricted_mobi_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "mobi-to-pdf")


@router.post("/fb2", response_model=JobOut, status_code=202)
def fb2_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "fb2-to-pdf")

@router.post("/djvu", response_model=JobOut, status_code=202)
def djvu_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "djvu-to-pdf")


@router.post("/dxf", response_model=JobOut, status_code=202)
def dxf_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "dxf-to-pdf")


@router.post("/svg", response_model=JobOut, status_code=202)
def svg_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "svg-to-pdf")


@router.post("/xps", response_model=JobOut, status_code=202)
def restricted_xps_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "xps-to-pdf")


@router.post("/ai", response_model=JobOut, status_code=202)
def pdf_compatible_ai_to_pdf(
    req: ConvertRequest,
    principal: Principal = Depends(require_scope("pdf:convert")),
    db: Session = Depends(get_db),
):
    return _submit(req, principal, db, "ai-to-pdf")
