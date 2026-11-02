"""Real localhost HTTP request/response boundary for the isolated native service.

Only the external codec call is mocked. Request framing, HMAC, nonce replay,
document transport, PDF strict revalidation and no-unsandboxed-fallback are
executed over actual HTTP with a fresh, loopback-only test server.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from threading import Thread
import time

import httpx
import pytest
from reportlab.pdfgen import canvas

from app.config import get_settings
from app.services import native_sidecar_server as server
from app.services import native_sidecar_client as client


def _pdf() -> bytes:
    out = BytesIO()
    page = canvas.Canvas(out)
    page.setFont("Helvetica", 12)
    page.drawString(50, 650, "Native transport verified")
    page.save()
    return out.getvalue()


@pytest.fixture
def live_native_test_server(monkeypatch):
    key = ("test-key-" + "K" * 48).encode("ascii")
    monkeypatch.setattr(server, "secret", key)
    monkeypatch.setattr(get_settings(), "native_sidecar_shared_secret", key.decode("ascii"))
    pdf_bytes = _pdf()

    def fake_decoder(operation: str, source: Path, output: Path):
        assert operation == "chm-to-pdf"
        assert source.read_bytes().startswith(b"ITSF")
        output.write_bytes(pdf_bytes)

    monkeypatch.setattr(server, "execute_isolated_native", fake_decoder)
    srv = server.Server(("127.0.0.1", 0), server.Handler)
    listener = Thread(target=srv.serve_forever, daemon=True)
    listener.start()
    monkeypatch.setattr(client, "NATIVE_ENDPOINT",
                        f"http://127.0.0.1:{srv.server_address[1]}")
    yield srv, key
    srv.shutdown()
    listener.join(timeout=3)
    srv.server_close()


def test_signed_native_http_round_trip_validates_returned_pdf(
    live_native_test_server, tmp_path,
):
    source = tmp_path / "document.chm"
    source.write_bytes(b"ITSF" + bytes(128))
    output = tmp_path / "converted.pdf"
    client.convert_native_remotely("chm-to-pdf", source, output)
    assert output.read_bytes().startswith(b"%PDF-")
    assert output.stat().st_size > 200


def test_native_http_rejects_bad_mac_and_unapproved_operation(live_native_test_server):
    srv, key = live_native_test_server
    endpoint = f"http://127.0.0.1:{srv.server_address[1]}"
    stamp = str(int(time.time()))
    nonce = "d" * 32
    payload = b"ITSF" + bytes(128)
    headers = {
        "X-PdfHub-Timestamp": stamp, "X-PdfHub-Nonce": nonce,
        "X-PdfHub-Signature": "0" * 64,
    }
    with httpx.Client(timeout=5, trust_env=False) as session:
        denied = session.post(endpoint + "/v1/convert/chm-to-pdf",
                              headers=headers, content=payload)
        assert denied.status_code == 403
        unknown = session.post(endpoint + "/v1/convert/arbitrary-to-pdf",
                               headers=headers, content=payload)
        assert unknown.status_code == 404


def test_native_http_nonce_cannot_be_replayed(live_native_test_server):
    srv, key = live_native_test_server
    endpoint = f"http://127.0.0.1:{srv.server_address[1]}"
    stamp = str(int(time.time()))
    nonce = "e" * 32
    payload = b"ITSF" + bytes(128)
    headers = {
        "X-PdfHub-Timestamp": stamp, "X-PdfHub-Nonce": nonce,
        "X-PdfHub-Signature": client.signature(
            key, b"request", "chm-to-pdf", stamp, nonce, payload,
        ),
    }
    with httpx.Client(timeout=5, trust_env=False) as session:
        first = session.post(endpoint + "/v1/convert/chm-to-pdf",
                             headers=headers, content=payload)
        assert first.status_code == 200
        second = session.post(endpoint + "/v1/convert/chm-to-pdf",
                              headers=headers, content=payload)
        assert second.status_code == 403
        assert second.text == "replay"
