"""T33 URL importer sidecar: private authenticated ingress, bounded HTTPS egress.

No PDF/DB/Redis/admin/NAS access. The sidecar does NOT run on the ordinary API
or heavy-worker container. Must have an independently installed host egress
firewall and its operator attestation file before it can start.

Uses only Python stdlib. Do not add browser/JS execution, redirects, cookies,
site-provided proxy settings, local file access, remote image/CSS resources,
or fallback to direct fetch in the worker.
"""
from __future__ import annotations

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
from threading import BoundedSemaphore, Lock
import time

from url_fetch_core import URL_MAX_LENGTH, fetch_bounded_public_html

PORT = 8099
MAX_REQUEST = 2100
MAX_RESPONSE = 3_000_000
MAX_CLOCK_SKEW = 45
MAX_NONCES = 1000
NONCE_LIFETIME = 100
ATTESTATION = Path("/run/pdfhub/url-egress.attested")
FIREWALL_LEASE_VERSION = "RCAT-T90-2-URL-FETCH-EGRESS-V2"
MAX_FIREWALL_LEASE_AGE = 120  # seconds; renewed by reviewed host timer
HOST_BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
NONCE_RE = re.compile(r"^[a-f0-9]{32}$")
HMAC_RE = re.compile(r"^[a-f0-9]{64}$")
busy = BoundedSemaphore(value=2)
connection_slots = BoundedSemaphore(value=8)
nonce_lock = Lock()
used_nonces: dict[str, float] = {}
secret = b""


def _signature(label: bytes, timestamp: str, nonce: str, payload: bytes) -> str:
    body = label + b"\n" + timestamp.encode("ascii") + b"\n" + nonce.encode("ascii") + b"\n" + payload
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def _check_nonce(nonce: str, now: float) -> bool:
    with nonce_lock:
        for key, expiry in list(used_nonces.items()):
            if expiry < now:
                del used_nonces[key]
        if nonce in used_nonces or len(used_nonces) >= MAX_NONCES:
            return False
        used_nonces[nonce] = now + NONCE_LIFETIME
        return True


def _firewall_lease_valid() -> bool:
    """Check a host-verified *short-lived* lease on EVERY fetch request.

    This check is an operational tripwire, not a substitute for the kernel
    firewall. If the host guard stops or invalidates its marker, no subsequent
    URL requests are performed. The file must be updated IN PLACE by the host
    because Docker read-only bind mounts pin its inode.
    """
    try:
        if not ATTESTATION.is_file() or not HOST_BOOT_ID.is_file():
            return False
        lease = ATTESTATION.read_text(encoding="ascii").splitlines()
        if len(lease) != 3 or lease[0] != FIREWALL_LEASE_VERSION:
            return False
        if lease[1] != HOST_BOOT_ID.read_text(encoding="ascii").strip():
            return False
        if not lease[2].isascii() or not lease[2].isdecimal():
            return False
        age = time.time() - int(lease[2])
        return -10 <= age <= MAX_FIREWALL_LEASE_AGE
    except (OSError, ValueError, UnicodeError):
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "RCAT-URL-Fetch/0.1"
    sys_version = ""

    def setup(self):
        # Cap slowloris/header-read time before BaseHTTPRequestHandler starts
        # parsing user-supplied HTTP headers.
        self.request.settimeout(5)
        super().setup()

    def log_message(self, fmt: str, *args):
        # Don't log requests or source URLs. Operator observability should
        # log only aggregate counts and coarse error categories.
        return

    def _reply(self, status: int, body: bytes, *, nonce: str = "", timestamp: str = ""):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if status == 200 else "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        if status == 200:
            self.send_header("X-PdfHub-Response-Mac", _signature(b"response", timestamp, nonce, body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Health must fail when firewall verification has stopped; otherwise
        # a stale, still-running service could appear healthy.
        if self.path != "/healthz":
            self._reply(404, b"not-found")
        elif not _firewall_lease_valid():
            self._reply(503, b"egress-policy-not-verified")
        else:
            self._reply(200, b"ok")

    def do_POST(self):
        if self.path != "/v1/fetch":
            self._reply(404, b"not-found")
            return
        if not _firewall_lease_valid():
            self._reply(503, b"egress-policy-not-verified")
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self._reply(400, b"chunked requests unsupported")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
            self._reply(400, b"invalid request length")
            return
        length = int(lengths[0])
        if not 10 <= length <= MAX_REQUEST:
            self._reply(413, b"request outside limits")
            return
        stamp = self.headers.get("X-PdfHub-Timestamp", "")
        nonce = self.headers.get("X-PdfHub-Nonce", "")
        mac = self.headers.get("X-PdfHub-Signature", "")
        if not (stamp.isascii() and stamp.isdecimal() and len(stamp) <= 12
                and NONCE_RE.fullmatch(nonce) and HMAC_RE.fullmatch(mac)):
            self._reply(403, b"forbidden")
            return
        now = time.time()
        if abs(now - int(stamp)) > MAX_CLOCK_SKEW:
            self._reply(403, b"forbidden")
            return
        self.connection.settimeout(5)
        try:
            body = self.rfile.read(length)
        except OSError:
            self._reply(400, b"request incomplete")
            return
        if len(body) != length or not hmac.compare_digest(
            mac, _signature(b"request", stamp, nonce, body)
        ):
            self._reply(403, b"forbidden")
            return
        if not _check_nonce(nonce, now):
            self._reply(403, b"replayed")
            return
        if not busy.acquire(blocking=False):
            self._reply(429, b"busy")
            return
        try:
            # Recheck immediately before starting outbound network I/O.
            if not _firewall_lease_valid():
                self._reply(503, b"egress-policy-not-verified")
                return
            try:
                url = body.decode("utf-8", errors="strict")
                if len(url) > URL_MAX_LENGTH:
                    raise ValueError("URL length exceeds limit")
                printable = fetch_bounded_public_html(url)
                raw = printable.encode("utf-8", errors="strict")
                if not 0 < len(raw) <= MAX_RESPONSE:
                    raise ValueError("Rendered content exceeds response limits")
            except (ValueError, UnicodeError, OSError):
                self._reply(422, b"unsupported source or unavailable public page")
                return
            self._reply(200, raw, nonce=nonce, timestamp=stamp)
        finally:
            busy.release()


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def process_request(self, request, client_address):
        if not connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            connection_slots.release()


def main():
    global secret
    supplied = os.environ.get("PDFHUB_URL_FETCHER_SHARED_SECRET", "")
    if (len(supplied) < 40 or len(supplied) > 256
            or supplied.startswith("change-me")
            or any(ord(c) < 33 or ord(c) > 126 for c in supplied)):
        raise SystemExit("URL fetcher requires a unique high-entropy shared secret")
    secret = supplied.encode("ascii")
    # The host guard checks actual ordered firewall rules and refreshes a
    # short-lived boot-bound lease. A one-time marker is insufficient when
    # Docker reloads or a firewall manager rewrites the host's rules.
    if not _firewall_lease_valid():
        raise SystemExit("URL fetcher requires fresh verified host egress firewall policy")
    server = BoundedHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
