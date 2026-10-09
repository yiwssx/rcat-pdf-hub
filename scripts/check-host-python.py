#!/usr/bin/env python3
"""Validate the host's stdlib-only tooling version.

Application dependencies and migrations run in the frozen API image, not in
the system Python installation. This guard does not select the Docker runtime.
"""

import sys

MINIMUM = (3, 11)


def main() -> None:
    version = sys.version_info[:2]
    if not (MINIMUM <= version < (4, 0)):
        raise SystemExit(
            f"Host Python >=3.11,<4 is required for supported tooling; "
            f"found {sys.version.split()[0]}. "
            "Python 3.10 is end-of-life and cannot run the OCRmyPDF 17.x runtime."
        )
    print(f"Host Python {sys.version.split()[0]}: PASS (>=3.11,<4)")


if __name__ == "__main__":
    main()
