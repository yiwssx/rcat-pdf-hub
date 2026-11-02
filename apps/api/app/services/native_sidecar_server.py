"""Dedicated native converter process inside a restricted Docker service.

The service has no database, Redis, NAS, Docker socket, cloud credentials or
published port. One inbound bounded request is decoded at a time. Its *own*
Docker container (not nested bwrap) provides network, mount, UID and cgroup
isolation. Conversion is NEVER executed in the credential-bearing RQ worker.
"""
from __future__ import annotations

from collections import OrderedDict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
from threading import BoundedSemaphore, Lock
import time
from tempfile import TemporaryDirectory

from app.native_format_policy import NATIVE_DEV_TO_PDF_INPUTS, native_dev_enabled
from app.filetypes import validate_uploaded_file
from app.services.native_sidecar_client import MAX_PDF, signature

MAX_BODY = 24 * 1024 * 1024
MAX_SKEW = 75
MAX_NONCES = 300
NONCE_TTL = 180
busy = BoundedSemaphore(1)
slots = BoundedSemaphore(4)
lock = Lock()
seen: OrderedDict[str, float] = OrderedDict()
secret = b""


def _use_nonce(nonce: str) -> bool:
    with lock:
        now = time.time()
        for token, expiry in list(seen.items()):
            if expiry < now:
                del seen[token]
        if nonce in seen or len(seen) >= MAX_NONCES:
            return False
        seen[nonce] = now + NONCE_TTL
        return True


def execute_isolated_native(operation: str, source: Path, output: Path) -> None:
    """Execute only within the dedicated, capability-dropped decoder container.

    This is intentionally NOT the privileged RQ worker's dispatch function.
    """
    if operation not in NATIVE_DEV_TO_PDF_INPUTS or not native_dev_enabled(operation):
        raise ValueError("Native operation unavailable")
    mime, _suffix, _flag = NATIVE_DEV_TO_PDF_INPUTS[operation]
    if validate_uploaded_file(source, source.name) != mime:
        raise ValueError("Source signature mismatches operation")
    if operation in {"heic-to-pdf", "heif-to-pdf"}:
        from app.services.to_pdf_heif_native import heif_to_pdf
        heif_to_pdf(source, output, suffix=source.suffix)
    elif operation == "dwg-to-pdf":
        from app.services.to_pdf_dwg_native import restricted_dwg_to_pdf
        restricted_dwg_to_pdf(source, output)
    elif operation == "chm-to-pdf":
        from app.services.to_pdf_chm_native import chm_to_pdf
        chm_to_pdf(source, output)
    elif operation == "wps-to-pdf":
        from app.services.to_pdf_wps_native import wps_works_to_pdf
        wps_works_to_pdf(source, output)
    else:
        raise ValueError("Native format is unsupported")


class Handler(BaseHTTPRequestHandler):
    server_version = "RCAT-Native-Converter/0.1"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        self.request.settimeout(6)
        super().setup()

    def log_message(self, fmt, *args):
        # Never log user filenames, document contents, request MAC or URL.
        pass

    def reply(self, status: int, value: bytes,
              *, operation: str = "", stamp: str = "", nonce: str = ""):
        self.send_response(status)
        self.send_header("Content-Type",
                         "application/pdf" if status == 200 else "text/plain")
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 200:
            self.send_header("X-PdfHub-Response-Mac",
                             signature(secret, b"response", operation, stamp, nonce, value))
        self.end_headers()
        self.wfile.write(value)

    def do_GET(self):
        self.reply(200 if self.path == "/healthz" else 404,
                   b"ok" if self.path == "/healthz" else b"not-found")

    def do_POST(self):
        prefix = "/v1/convert/"
        operation = self.path[len(prefix):] if self.path.startswith(prefix) else ""
        if operation not in NATIVE_DEV_TO_PDF_INPUTS:
            self.reply(404, b"not-found")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self.reply(400, b"chunked-not-supported")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if (len(lengths) != 1 or not lengths[0].isascii()
                or not lengths[0].isdecimal()):
            self.reply(400, b"bad-length")
            return
        n = int(lengths[0])
        if n < 16 or n > MAX_BODY:
            self.reply(413, b"size-limit")
            return
        stamp = self.headers.get("X-PdfHub-Timestamp", "")
        nonce = self.headers.get("X-PdfHub-Nonce", "")
        mac = self.headers.get("X-PdfHub-Signature", "")
        if (not stamp.isascii() or not stamp.isdecimal()
                or len(stamp) > 12
                or not re.fullmatch(r"[a-f0-9]{32}", nonce)
                or not re.fullmatch(r"[a-f0-9]{64}", mac)
                or abs(time.time() - int(stamp)) > MAX_SKEW):
            self.reply(403, b"forbidden")
            return
        if not busy.acquire(blocking=False):
            self.reply(429, b"busy")
            return
        try:
            try:
                data = self.rfile.read(n)
                if (len(data) != n or not hmac.compare_digest(
                    mac, signature(secret, b"request", operation, stamp, nonce, data),
                )):
                    self.reply(403, b"bad-signature")
                    return
                if not _use_nonce(nonce):
                    self.reply(403, b"replay")
                    return
                mime, suffix, _flag = NATIVE_DEV_TO_PDF_INPUTS[operation]
                with TemporaryDirectory(prefix="pdfhub-native-request-") as folder:
                    source = Path(folder) / ("source" + suffix)
                    output = Path(folder) / "result.pdf"
                    with source.open("xb") as target:
                        target.write(data)
                    # Sidecar alone has the required OFF->ON experiment flags;
                    # its parent Worker never imports or executes codecs.
                    execute_isolated_native(operation, source, output)
                    if output.is_symlink() or not output.is_file():
                        raise ValueError("No checked regular output PDF")
                    size = output.stat().st_size
                    if not 16 <= size <= MAX_PDF:
                        raise ValueError("Output PDF violates limits")
                    payload = output.read_bytes()
                    if len(payload) != size or not payload.startswith(b"%PDF-"):
                        raise ValueError("Output PDF is invalid or changed")
                self.reply(200, payload, operation=operation, stamp=stamp, nonce=nonce)
            except (OSError, ValueError, RuntimeError, UnicodeError):
                self.reply(422, b"invalid-or-unsupported-native-source")
        finally:
            busy.release()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 4

    def process_request(self, request, client_address):
        if not slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            slots.release()


def main():
    global secret
    key = os.environ.get("PDFHUB_NATIVE_SIDECAR_SHARED_SECRET", "")
    if (len(key) < 40 or len(key) > 256 or key.startswith("change-me")
            or any(ord(c) < 33 or ord(c) > 126 for c in key)):
        raise SystemExit("Native decoder requires a unique high-entropy shared secret")
    if os.environ.get("PDFHUB_NATIVE_ISOLATED_CONTAINER") != "1":
        raise SystemExit("Native service must use a dedicated Docker confinement profile")
    if os.geteuid() == 0:
        raise SystemExit("Native sidecar must never run as root")
    # Refuse accidental DB and storage mounts inside the codec container.
    for forbidden in ("/data", "/mnt/pdfhub-nas", "/var/run/docker.sock"):
        if Path(forbidden).exists():
            raise SystemExit("Native service has forbidden filesystem access")
    secret = key.encode("ascii")
    Server(("0.0.0.0", 8098), Handler).serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
