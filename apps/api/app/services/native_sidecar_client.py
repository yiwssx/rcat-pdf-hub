"""T90-2 native format bridge: signed, bounded, no direct native code in worker.

The worker holds user documents and database credentials. Native libraries must
execute only inside the separate, capability-dropped native-decoder service.
No fallback to in-process native decoding or Bubblewrap in the trusted worker.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from pathlib import Path

import httpx

from app.config import get_settings
from app.services.to_pdf_engine import _checked_pdf

NATIVE_ENDPOINT = "http://native-decoder:8098"
MAX_INPUT = 24 * 1024 * 1024
MAX_PDF = 40 * 1024 * 1024
MAX_SKEW = 75


def signature(secret: bytes, label: bytes, operation: str, timestamp: str,
              nonce: str, payload: bytes) -> str:
    message = (label + b"\n" + operation.encode("ascii") + b"\n"
               + timestamp.encode("ascii") + b"\n" + nonce.encode("ascii")
               + b"\n" + payload)
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def convert_native_remotely(operation: str, source: Path, output: Path) -> None:
    """Send a single bounded source to isolated Docker-native worker."""
    from app.native_format_policy import NATIVE_DEV_TO_PDF_INPUTS
    if operation not in NATIVE_DEV_TO_PDF_INPUTS:
        raise ValueError("Native decoder operation is not allowlisted")
    secret_text = get_settings().native_sidecar_shared_secret
    if (len(secret_text) < 40 or len(secret_text) > 256
            or any(ord(c) < 33 or ord(c) > 126 for c in secret_text)):
        raise ValueError("Isolated native service is not provisioned")
    if source.is_symlink() or not source.is_file():
        raise ValueError("Native source is not one regular file")
    size = source.stat().st_size
    if not 16 <= size <= MAX_INPUT:
        raise ValueError("Native document exceeds service limits")
    with source.open("rb") as reader:
        body = reader.read(MAX_INPUT + 1)
    if len(body) != size:
        raise ValueError("Native file size changed while being read")
    secret = secret_text.encode("ascii")
    stamp = str(int(time.time()))
    nonce = secrets.token_hex(16)
    mac = signature(secret, b"request", operation, stamp, nonce, body)
    try:
        with httpx.Client(
            timeout=httpx.Timeout(180, connect=4, read=175, write=15, pool=4),
            follow_redirects=False, trust_env=False,
        ) as client:
            with client.stream(
                "POST", NATIVE_ENDPOINT + "/v1/convert/" + operation,
                content=body,
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-PdfHub-Timestamp": stamp,
                    "X-PdfHub-Nonce": nonce,
                    "X-PdfHub-Signature": mac,
                    "Cache-Control": "no-store",
                },
            ) as response:
                if response.status_code != 200:
                    raise ValueError("Isolated native decoder rejected this source")
                if response.headers.get("content-type", "").split(";", 1)[0] != "application/pdf":
                    raise ValueError("Native decoder did not return PDF")
                raw_length = response.headers.get("content-length", "")
                if not raw_length.isascii() or not raw_length.isdecimal():
                    raise ValueError("Native response length missing")
                expected = int(raw_length)
                if not 16 <= expected <= MAX_PDF:
                    raise ValueError("Native output exceeds PDF limits")
                chunks = []
                received = 0
                for chunk in response.iter_bytes():
                    received += len(chunk)
                    if received > expected or received > MAX_PDF:
                        raise ValueError("Native response violates byte limit")
                    chunks.append(chunk)
                result = b"".join(chunks)
                if received != expected:
                    raise ValueError("Native response is incomplete")
                actual = response.headers.get("x-pdfhub-response-mac", "")
                answer = signature(secret, b"response", operation, stamp, nonce, result)
                if not hmac.compare_digest(actual, answer):
                    raise ValueError("Native response authentication failed")
    except (httpx.HTTPError, OSError) as exc:
        raise ValueError("Isolated native decoder unavailable") from exc
    # Reparse output under trusted code. HMAC does not certify PDF safety.
    _checked_pdf(result, output)
