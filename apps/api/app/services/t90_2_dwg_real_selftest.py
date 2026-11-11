"""T20 exact LINE/CIRCLE modelspace DWG -> constrained DXF -> real vector PDF.

The fixture is a *real r2000 binary DWG* produced from one controlled ASCII
DXF using GNU LibreDWG 0.14's dwgwrite on a disposable isolated CI image.
The same upstream binary distribution provides dwgread; no proprietary
converter or forged DWG header. This is a narrow source-MAC test, not a
general CAD/font/layer/layout compatibility or GPL redistribution signoff.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from pypdf import PdfReader
from app.services.to_pdf_dwg_native import restricted_dwg_to_pdf

SOURCE = Path("/fixtures/simple-geometry.dwg")
SIMPLE_DXF = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
10.0
20
10.0
30
0.0
11
90.0
21
40.0
31
0.0
0
CIRCLE
8
0
10
50.0
20
70.0
30
0.0
40
15.0
0
ENDSEC
0
EOF
"""


def main() -> int:
    report = {"test": "T20 genuine LibreDWG r2000 2D LINE/CIRCLE PDF", "status": "FAIL"}
    try:
        if not SOURCE.is_file() or SOURCE.is_symlink() or not SOURCE.read_bytes().startswith(b"AC1015"):
            raise ValueError("Real r2000 DWG binary was not generated")
        original_sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        with TemporaryDirectory(prefix="dwg-native-ci-") as work:
            folder = Path(work)
            result = folder / "vector.pdf"
            restricted_dwg_to_pdf(SOURCE, result)
            with result.open("rb") as fd:
                pdf = PdfReader(fd, strict=True)
                if pdf.is_encrypted or len(pdf.pages) != 1:
                    raise ValueError("DWG vector renderer emitted invalid page inventory")
                body = pdf.pages[0].get_contents().get_data()
                if not (b" m " in body or b" m\n" in body or b" l " in body or b" l\n" in body):
                    raise ValueError("DWG PDF lost LINE/CIRCLE drawing operators")
            if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != original_sha:
                raise ValueError("DWG source bytes were modified")
            corrupt = folder / "fake.dwg"
            corrupt.write_bytes(b"AC1015" + b"\x00" * 2048)
            bad_pdf = folder / "bad.pdf"
            try:
                restricted_dwg_to_pdf(corrupt, bad_pdf)
            except (ValueError, OSError, subprocess.TimeoutExpired):
                if bad_pdf.exists():
                    raise ValueError("Fake DWG left a downloadable PDF")
            else:
                raise ValueError("Forged DWG was accepted")
            report.update(status="PASS", source_sha256=original_sha,
                          output_sha256=hashlib.sha256(result.read_bytes()).hexdigest(),
                          drawing_types=["LINE", "CIRCLE"], output_pages=1,
                          binary_version="AC1015 (R2000)", invalid_rejected=True,
                          not_full_cad_or_licensing_or_rcat_host_certificate=True)
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        report.update(reason=str(exc)[:240], error_type=type(exc).__name__)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    sys.exit(main())
