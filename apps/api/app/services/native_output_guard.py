"""Trusted promotion of untrusted native decoder output into a private task area.

The decoder may control every filename in its writable /output mount. Before
parsing, rendering or returning that content, copy from an O_NOFOLLOW regular-
file descriptor into a new file under a separate directory not mounted into
Bubblewrap. Reject symlinks, devices, FIFOs, hardlinks and size changes.

This is a necessary file-identity check, not a substitute for sandboxing.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

_CHUNK = 1024 * 1024


def copy_native_regular_output(
    source: Path, trusted_target: Path, *, maximum_bytes: int,
    minimum_bytes: int = 1,
) -> int:
    """Copy a bounded native file to a fresh trusted path; fail closed.

    The parent of trusted_target must be a newly allocated task directory
    inaccessible to the native process. No existing target may be overwritten.
    """
    if not 1 <= minimum_bytes <= maximum_bytes:
        raise ValueError("Native output size limits are invalid")
    if (source.parent.resolve() == trusted_target.parent.resolve()
            or not trusted_target.parent.is_dir()
            or trusted_target.exists() or trusted_target.is_symlink()):
        raise ValueError("Native output cannot overwrite an untrusted directory")

    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK | os.O_NOFOLLOW
    try:
        fd = os.open(source, flags)
    except OSError as exc:
        raise ValueError("Native decoder output is unavailable or unsafe") from exc

    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or not minimum_bytes <= info.st_size <= maximum_bytes):
            raise ValueError("Native decoder did not produce one bounded regular file")
        total = 0
        with os.fdopen(fd, "rb", closefd=False) as untrusted:
            with trusted_target.open("xb") as destination:
                while True:
                    chunk = untrusted.read(min(_CHUNK, maximum_bytes - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > maximum_bytes:
                        raise ValueError("Native output grew beyond allowed size")
                    destination.write(chunk)
        if total != info.st_size:
            raise ValueError("Native output changed while being copied")
        return total
    finally:
        os.close(fd)
