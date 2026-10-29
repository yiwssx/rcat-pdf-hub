"""Strict ASCII DXF conversion tests: real vectors, security and flag gating."""
import hashlib
from io import BytesIO

import pytest
from fastapi import HTTPException
from pypdf import PdfReader

from app.config import get_settings
from app.filetypes import validate_uploaded_file
from app.services.to_pdf_dxf import parse_dxf
from app.staged_to_pdf_adapters import checked_source, execute_staged_to_pdf_operation

DXF = ("0\nSECTION\n2\nENTITIES\n"
       "0\nLINE\n8\nLayer_1\n10\n0\n20\n0\n11\n120\n21\n80\n"
       "0\nCIRCLE\n10\n50\n20\n40\n40\n15\n"
       "0\nENDSEC\n0\nEOF\n")


def test_dxf_real_pdf_and_source_immutability(monkeypatch, tmp_path):
    source = tmp_path / "cad.dxf"
    source.write_text(DXF, encoding="ascii")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(parse_dxf(source)) == 2
    with pytest.raises(HTTPException) as exc:
        validate_uploaded_file(source, source.name)
    assert exc.value.status_code == 415
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", True)
    assert validate_uploaded_file(source, source.name) == "image/vnd.dxf"
    output = tmp_path / "result.pdf"
    execute_staged_to_pdf_operation(
        "dxf-to-pdf", [source], output, {},
        original_name=source.name, content_type="image/vnd.dxf",
    )
    pdf = PdfReader(BytesIO(output.read_bytes()), strict=True)
    assert not pdf.is_encrypted
    assert len(pdf.pages) == 1
    assert b" re" not in output.read_bytes() or len(output.read_bytes()) > 500
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="persisted MIME"):
        checked_source("dxf-to-pdf", source, name="cad.dxf", mime="text/plain")
    with pytest.raises(ValueError, match="differ"):
        execute_staged_to_pdf_operation(
            "dxf-to-pdf", [source], source, {},
            original_name=source.name, content_type="image/vnd.dxf",
        )


@pytest.mark.parametrize("payload", [
    "0\nSECTION\n2\nOBJECTS\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nINSERT\n2\nexternal_block\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0\n20\n0\n11\n10\n21\n10\n1\nhttp://example.com\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nCIRCLE\n10\n0\n20\n0\n40\nNaN\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nCIRCLE\n10\n0\n20\n0\n40\n-1\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0\n20\n0\n11\n2\n21\n2\n30\n5\n0\nENDSEC\n0\nEOF\n",
    "0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0\n20\n0\n11\n10\n21\n20\n0\nENDSEC\n0\nEOF\n0\nSECTION\n2\nHEADER\n",
])
def test_dxf_rejects_untrusted_or_out_of_scope_entities(tmp_path, payload):
    src = tmp_path / "bad.dxf"
    src.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        parse_dxf(src)


def test_dxf_rejects_binary_input_large_size_and_flag_off(monkeypatch, tmp_path):
    source = tmp_path / "cad.dxf"
    source.write_bytes(DXF.encode() + b"\x00")
    with pytest.raises(ValueError, match="control"):
        parse_dxf(source)
    source.write_bytes(b"A" * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="1 MiB"):
        parse_dxf(source)
    source.write_text(DXF, encoding="ascii")
    monkeypatch.setattr(get_settings(), "to_pdf_tools_enabled", False)
    with pytest.raises(RuntimeError, match="disabled"):
        execute_staged_to_pdf_operation(
            "dxf-to-pdf", [source], tmp_path / "out.pdf", {},
            original_name=source.name, content_type="image/vnd.dxf",
        )
