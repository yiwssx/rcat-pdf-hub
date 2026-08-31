#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DATA_DIR = Path(os.environ.get("PDFHUB_ALERT_SINK_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
ALERT_FILE = DATA_DIR / "alerts.jsonl"


class Handler(BaseHTTPRequestHandler):
    server_version = "PdfHubAlertSink/0.5.1"

    def log_message(self, fmt, *args):
        print("alert-sink:", fmt % args, flush=True)

    def _reply(self, status: int, body: bytes = b"ok\n") -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._reply(200)
        else:
            self._reply(404, b"not found\n")

    def do_POST(self):
        if self.path != "/alerts":
            self._reply(404, b"not found\n")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 2 * 1024 * 1024:
                raise ValueError("invalid alert payload length")
            payload = json.loads(self.rfile.read(length))
            record = {
                "received_at": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            fd = os.open(ALERT_FILE, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
            print(line.rstrip(), flush=True)
            self._reply(200)
        except Exception as exc:
            print(f"alert-sink error: {exc}", flush=True)
            self._reply(400, b"invalid alert payload\n")


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()
