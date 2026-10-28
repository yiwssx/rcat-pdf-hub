"""Real T90-1.7 M31 mixed-size, rotated and Thai document fixture."""
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from app.services.pdf_header_footer import add_header_footer


def _fixture(path: Path) -> Path:
    c = canvas.Canvas(str(path), pagesize=(480, 720))
    c.drawString(40, 600, "Original unchanged content")
    c.showPage()
    c.setPageSize((700, 480))
    c.drawString(40, 300, "Second original content")
    c.showPage()
    c.save()
    writer = PdfWriter(clone_from=str(path))
    writer.pages[1].rotate(90)
    rotated = path.parent / "rotated.pdf"
    writer.write(str(rotated))
    return rotated


def test_header_footer_thai_and_page_number_on_rotated_mixed_pages(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    target = tmp_path / "header.pdf"
    add_header_footer(
        source, target, header="เอกสารราชการ หน้า {page}",
        footer="RCAT {page}/{total}", font_size=12, margin=30,
    )
    result = PdfReader(str(target), strict=True)
    assert len(result.pages) == 2
    assert "Original unchanged content" in result.pages[0].extract_text()
    assert "Second original content" in result.pages[1].extract_text()
    assert "RCAT 1/2" in result.pages[0].extract_text()
    assert "RCAT 2/2" in result.pages[1].extract_text()
    assert result.pages[0].get_contents() is not None
    assert int(result.pages[1].get("/Rotate", 0)) % 360 == 0


@pytest.mark.parametrize("header", ["{bad}", "{page:x}", "a" * 300, "bad\nline"])
def test_invalid_header_template_rejected(tmp_path: Path, header: str):
    source = _fixture(tmp_path / "source.pdf")
    target = tmp_path / "no.pdf"
    with pytest.raises(ValueError):
        add_header_footer(source, target, header=header)
    assert not target.exists()


def test_empty_and_same_source_rejected(tmp_path: Path):
    source = _fixture(tmp_path / "source.pdf")
    target = tmp_path / "no.pdf"
    with pytest.raises(ValueError):
        add_header_footer(source, target)
    with pytest.raises(ValueError, match="differ"):
        add_header_footer(source, source, header="Title")
    assert not target.exists()
