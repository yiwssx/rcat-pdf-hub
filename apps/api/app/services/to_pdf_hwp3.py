"""A bounded authenticated HWP 3.0 (1997 vintage) importer guard.

The 30-byte identity and 128-byte Document Info offsets follow the public
Hangul Document File Format 3.0 specification, not guessed MIME extensions.
No HWP5 OLE or HWPX ZIP support is implied by this legacy subset.
"""
from pathlib import Path
import struct

MAGIC = b"HWP Document File V3.00 \x1a\x01\x02\x03\x04\x05"
MAX_HWP_BYTES = 8 * 1024 * 1024
MIN_HWP_BYTES = 30 + 128 + 1008


def validate_hwp3(source: Path) -> None:
    size = source.stat().st_size
    if not MIN_HWP_BYTES <= size <= MAX_HWP_BYTES:
        raise ValueError("HWP3 source outside bounded size")
    with source.open("rb") as fh:
        prefix = fh.read(30 + 128)
    if prefix[:30] != MAGIC:
        raise ValueError("Only legacy Hangul HWP V3.00 is supported")
    # Document information begins at absolute byte 30.
    # Offset +24: 32-bit document protection.
    # Offset +96: 16-bit password flag; nonzero means encrypted.
    if struct.unpack_from("<I", prefix, 30 + 24)[0] != 0:
        raise ValueError("HWP3 protected documents unsupported")
    if struct.unpack_from("<H", prefix, 30 + 96)[0] != 0:
        raise ValueError("HWP3 password-protected documents unsupported")
