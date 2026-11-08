#!/usr/bin/env python3
"""Choose an available loopback TCP port for an isolated DR rehearsal.

A port is available only at the moment of this check; Docker may still report
a race if another process binds it before Caddy starts.
"""
from __future__ import annotations

import os
import socket
import sys


def choose_port(requested: str | None) -> int:
    if requested:
        if not requested.isascii() or not requested.isdecimal():
            raise ValueError("PDFHUB_DRILL_HTTP_PORT must be a decimal integer")
        port = int(requested)
        if not 1024 <= port <= 65535:
            raise ValueError("PDFHUB_DRILL_HTTP_PORT must be in 1024..65535")
    else:
        port = 0

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", port))
        return probe.getsockname()[1]


if __name__ == "__main__":
    try:
        print(choose_port(os.environ.get("PDFHUB_DRILL_HTTP_PORT")))
    except (OSError, ValueError) as exc:
        print(f"dr-drill: loopback port unavailable: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
