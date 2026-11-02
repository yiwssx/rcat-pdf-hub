"""One-purpose libheif version probe. Runs only in a restricted native sandbox.

Do not import this module from the trusted API/worker; ctypes.CDLL may execute
untrusted library constructors and is deliberately confined to the decoder's
network-denied, read-only sandbox and CPU/memory-capped subprocess.
"""
from __future__ import annotations

import ctypes
import re
import sys
from pathlib import Path

LIBRARY = "/opt/pdfhub/heif/lib/libheif.so.1"


def main() -> int:
    # Both original Bubblewrap (/input/source) and the new standalone
    # Docker decoder (private /tmp/source.heif) supply one validated input.
    # The probe never reads media; it only verifies native-library provenance.
    if len(sys.argv) != 2 or not Path(sys.argv[1]).is_file():
        return 2
    lib = ctypes.CDLL(LIBRARY)
    lib.heif_get_version.argtypes = []
    lib.heif_get_version.restype = ctypes.c_char_p
    raw = lib.heif_get_version()
    if not raw or len(raw) > 96 or not re.fullmatch(rb"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9._-]+)?", raw):
        return 3
    sys.stdout.buffer.write(raw + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, AttributeError, ValueError):
        raise SystemExit(4) from None
