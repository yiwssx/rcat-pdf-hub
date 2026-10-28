"""T90-1.2: executable M02/M10/M15 PDF binary and scoped API regressions.

No new tool is activated. These tests deliberately use real Ghostscript/qpdf
in the pinned API image, rather than treating a mocked .pdf suffix as proof.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app import security
from app.db import SessionLocal
from app.identity import create_session_token
from app.main import app
from app.models import FileRecord, JobRecord
from app.routers import pdf as pdf_router
from app.services import pdf_tools


PAGES = (
    ("RCAT-ALPHA", (612, 792)),
    ("RCAT-BETA", (420, 595)),
    ("RCAT-GAMMA", (595, 842)),
)


def _source(path: Path) -> Path:
    document = canvas.Canvas(str(path), pageCompression=0)
    for text, dimensions in PAGES:
        document.setPageSize(dimensions)
        document.drawString(72, dimensions[1] - 72, text)
        document.showPage()
    document.save()
    return path


def _labels(pdf: Path) -> list[str]:
    reader = PdfReader(str(pdf), strict=True)
    return [page.extract_text() or "" for page in reader.pages]


def _geometry(pdf: Path) -> list[tuple[float, float]]:
    reader = PdfReader(str(pdf), strict=True)
    return [(float(page.mediabox.width), float(page.mediabox.height)) for page in reader.pages]


def _assert_pdf(result: Path, expected_labels: tuple[str, ...]) -> None:
    assert result.read_bytes().startswith(b"%PDF-")
    labels = _labels(result)
    assert len(labels) == len(expected_labels)
    assert all(word in text for word, text in zip(expected_labels, labels, strict=True))


@pytest.mark.skipif(shutil.which("gs") is None, reason="real Ghostscript executable required")
def test_m02_compress_binary_preserves_page_text_geometry_and_source(tmp_path: Path):
    source = _source(tmp_path / "source.pdf")
    result = tmp_path / "compressed.pdf"
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    pdf_tools.compress(source, result)

    _assert_pdf(result, tuple(text for text, _ in PAGES))
    assert len(_geometry(result)) == len(PAGES)
    for actual, (_, expected) in zip(_geometry(result), PAGES, strict=True):
        assert actual == pytest.approx(expected, abs=1.0)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    # Ghostscript can legitimately create a larger file for a short or heavily
    # compressed input. No guarantee or assertion that bytes always decrease.


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="real qpdf executable required")
def test_m10_rotate_only_selected_page_and_retain_text(tmp_path: Path):
    source = _source(tmp_path / "original.pdf")
    result = tmp_path / "rotated.pdf"
    before = source.read_bytes()

    pdf_tools.rotate(source, degrees=90, pages="2", output=result)

    _assert_pdf(result, tuple(text for text, _ in PAGES))
    reader = PdfReader(str(result), strict=True)
    assert [int(page.get("/Rotate", 0)) % 360 for page in reader.pages] == [0, 90, 0]
    for actual, expected in zip(_geometry(result), _geometry(source), strict=True):
        assert actual == pytest.approx(expected, abs=1.0)
    assert source.read_bytes() == before


@pytest.mark.skipif(shutil.which("qpdf") is None, reason="real qpdf executable required")
def test_m10_rotate_negative_angle_is_normalized(tmp_path: Path):
    source = _source(tmp_path / "original.pdf")
    result = tmp_path / "rotated.pdf"

    pdf_tools.rotate(source, degrees=-90, pages="1-z", output=result)

    _assert_pdf(result, tuple(text for text, _ in PAGES))
    assert [int(page.get("/Rotate", 0)) % 360 for page in PdfReader(str(result)).pages] == [270] * 3


@pytest.mark.parametrize("degrees,pages", [
    (45, "1-z"),
    (90, "1;rm -rf /"),
    (90, "\n1-z"),
])
def test_m10_invalid_rotation_is_rejected_before_external_command(
    monkeypatch, tmp_path: Path, degrees: int, pages: str
):
    monkeypatch.setattr(pdf_tools, "_run", lambda *_a, **_kw: pytest.fail("unsafe execution"))
    with pytest.raises(ValueError):
        pdf_tools.rotate(tmp_path / "source.pdf", degrees, pages, tmp_path / "output.pdf")


def test_m15_rearrange_duplicate_selection_page_rotation_and_immutability(tmp_path: Path):
    source = _source(tmp_path / "source.pdf")
    result = tmp_path / "rearranged.pdf"
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    pdf_tools.organize(source, [
        {"page": 3, "rotation": 90},
        {"page": 1, "rotation": 0},
        {"page": 3, "rotation": 0},
    ], result)

    _assert_pdf(result, ("RCAT-GAMMA", "RCAT-ALPHA", "RCAT-GAMMA"))
    reader = PdfReader(str(result), strict=True)
    assert [int(page.get("/Rotate", 0)) % 360 for page in reader.pages] == [90, 0, 0]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("items,pattern", [
    ([], "At least one"),
    ([{"page": 0, "rotation": 0}], "Page out of range"),
    ([{"page": 4, "rotation": 0}], "Page out of range"),
    ([{"page": 1, "rotation": 45}], "rotation must be"),
])
def test_m15_rejects_invalid_page_plan_without_output(
    tmp_path: Path, items: list[dict], pattern: str
):
    source = _source(tmp_path / "source.pdf")
    output = tmp_path / "invalid.pdf"
    with pytest.raises(ValueError, match=pattern):
        pdf_tools.organize(source, items, output)
    assert not output.exists()


def _token(actor: str, scopes: list[str]) -> str:
    return create_session_token({
        "name": actor, "subject": "test:" + actor, "display_name": actor,
        "groups": [], "scopes": scopes, "source": "session",
        "is_identity_admin": False,
    })


@pytest.mark.parametrize("endpoint,scope,operation,extra", [
    ("compress", "pdf:compress", "compress", {}),
    ("rotate", "pdf:rotate", "rotate", {"degrees": 90, "pages": "2"}),
    ("organize", "pdf:split", "organize", {"pages": [
        {"page": 2, "rotation": 90}, {"page": 1, "rotation": 0},
    ]}),
])
def test_core_pdf_api_enforces_scope_mime_and_source_owner_before_enqueue(
    monkeypatch, endpoint: str, scope: str, operation: str, extra: dict
):
    monkeypatch.setattr(security, "ensure_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf_router, "ensure_daily_job_quota", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf_router, "audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf_router, "set_queue_depth", lambda *args, **kwargs: None)
    monkeypatch.setattr(pdf_router, "record_job", lambda *args, **kwargs: None)

    queued: list[str] = []

    class Queue:
        name = "test-queue"

        def __len__(self):
            return 0

    def enqueue(op: str, job_id: str):
        queued.append(op)
        return Queue(), SimpleNamespace(id="rq-" + job_id)

    monkeypatch.setattr(pdf_router, "enqueue_processing_job", enqueue)
    owner, foreign = "user:core-owner", "user:other"
    db = SessionLocal()
    records = [
        FileRecord(original_name=name, stored_name="t90-1-2-" + name,
                   content_type=mime, size=128, sha256="b" * 64, source_system=actor)
        for name, mime, actor in [
            ("a.pdf", "application/pdf", owner),
            ("spoof.pdf", "image/png", owner),
            ("b.pdf", "application/pdf", foreign),
        ]
    ]
    db.add_all(records)
    db.commit()
    ids = [record.id for record in records]
    db.close()

    client = TestClient(app)
    url = "/api/v1/pdf/" + endpoint
    client.cookies.set("pdfhub_session", _token(owner, ["jobs:read"]))
    assert client.post(url, json={"file_id": ids[0], **extra}).status_code == 403
    client.cookies.set("pdfhub_session", _token(owner, ["jobs:read", scope]))
    assert client.post(url, json={"file_id": ids[1], **extra}).status_code == 415
    assert client.post(url, json={"file_id": ids[2], **extra}).status_code == 403
    assert not queued

    response = client.post(url, json={"file_id": ids[0], **extra})
    assert response.status_code == 202, response.text
    data = response.json()
    assert data["operation"] == operation
    assert data["requested_by"] == owner
    assert queued == [operation]
    db = SessionLocal()
    job = db.get(JobRecord, data["id"])
    assert job is not None and job.requested_by == owner
    db.close()
