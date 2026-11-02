"""T33 URL -> PDF worker adapter. Never perform Internet HTTP here.

The API/heavy worker sends a signed, replay-protected request to the dedicated
low-trust URL fetcher on a private Docker network. The sidecar alone resolves
public DNS and opens outbound HTTPS. Failure always fails closed.
"""
from __future__ import annotations

import hashlib
import hmac
import http.client
from pathlib import Path
import secrets
import time

from app.config import get_settings
from app.services.url_fetch_core import URL_MAX_LENGTH, validate_public_https_url

MAX_RESPONSE = 3_000_000
FETCHER_HOST = "url-fetcher"
FETCHER_PORT = 8099


def _sign(secret: bytes, label: bytes, stamp: str, nonce: str, body: bytes) -> str:
    payload = label + b"\n" + stamp.encode("ascii") + b"\n" + nonce.encode("ascii") + b"\n" + body
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def _fetch_via_sidecar(url: str, secret: bytes) -> str:
    # Revalidate at worker dispatch, then send the original validated URL.
    # The sidecar independently validates and percent-encodes the remote
    # request path, preventing API/worker double-encoding Unicode paths.
    validate_public_https_url(url)
    body = url.encode("utf-8")
    if not 10 <= len(body) <= URL_MAX_LENGTH:
        raise ValueError("URL body outside allowed byte limits")
    timestamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    connection = http.client.HTTPConnection(FETCHER_HOST, FETCHER_PORT, timeout=40)
    try:
        connection.request(
            "POST", "/v1/fetch",
            body=body,
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "X-PdfHub-Timestamp": timestamp,
                "X-PdfHub-Nonce": nonce,
                "X-PdfHub-Signature": _sign(secret, b"request", timestamp, nonce, body),
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Dedicated public URL fetch service rejected the source")
        if response.getheader("Content-Type", "").lower() != "text/html; charset=utf-8":
            raise ValueError("URL fetcher response media type mismatched")
        declared = response.getheader("Content-Length")
        if declared is None or not declared.isascii() or not declared.isdecimal():
            raise ValueError("URL fetcher omitted bounded response length")
        length = int(declared)
        if not 0 < length <= MAX_RESPONSE:
            raise ValueError("URL fetcher response exceeds limits")
        payload = response.read(MAX_RESPONSE + 1)
        if len(payload) != length:
            raise ValueError("URL fetcher returned partial or excessive content")
        actual_mac = response.getheader("X-PdfHub-Response-Mac", "")
        expected_mac = _sign(secret, b"response", timestamp, nonce, payload)
        if not hmac.compare_digest(actual_mac, expected_mac):
            raise ValueError("Dedicated URL fetcher response authentication failed")
        html = payload.decode("utf-8", errors="strict")
        if not html.strip():
            raise ValueError("URL fetcher returned empty printable content")
        return html
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError("Dedicated URL fetcher unavailable or interrupted") from exc
    finally:
        connection.close()


def url_to_pdf(url: str, output: Path) -> None:
    settings = get_settings()
    if not settings.to_pdf_tools_enabled or not settings.url_to_pdf_dev_enabled:
        raise RuntimeError("URL-to-PDF development feature is disabled")
    secret_str = settings.url_fetcher_shared_secret
    if (len(secret_str) < 40 or len(secret_str) > 256
            or secret_str.startswith("change-me")
            or not secret_str.isascii()
            or any(ord(c) < 33 or ord(c) > 126 for c in secret_str)):
        raise RuntimeError("Dedicated URL fetcher shared secret is missing or invalid")
    html = _fetch_via_sidecar(url, secret_str.encode("ascii"))
    # The isolated fetcher is still lower-trust than the PDF worker. An HMAC
    # proves who sent the HTML, not that a compromised fetcher sanitized it.
    # Independently parse, reject all attributes/active elements and escape
    # all text before giving Chromium any document content.
    from app.services.url_html_boundary import validate_offline_url_html
    safe_html = validate_offline_url_html(html)
    from app.services.to_pdf_engine import _html_to_pdf
    _html_to_pdf(safe_html, output)
