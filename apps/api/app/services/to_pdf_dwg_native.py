"""Development-only DWG -> DXF -> vector PDF bridge.

GNU LibreDWG 'dwgread -O DXF' is an EXTERNAL native decoder under GPLv3+.
The project must review redistribution obligations before shipping any binary.
No embedded DWG decoder is linked into the API and no public DWG route exists.

This first pass deliberately accepts LINE/CIRCLE-only drawings and refuses
every other drawn entity, INSERT/BLOCK/XREF and unsupported 3D operations.
Metadata / styling are NOT equivalent to the original CAD model. Never call
a geometry-only transcript "full DWG fidelity".
"""
from __future__ import annotations

from pathlib import Path
import re
import resource
import subprocess
from tempfile import TemporaryDirectory

from app.config import get_settings
from app.services.to_pdf_dxf import parse_dxf, restricted_dxf_to_pdf
from app.services.native_sandbox import SANDBOX_INPUT, isolated_native_command
from app.services.native_output_guard import copy_native_regular_output

DWG_BINARY = Path("/opt/pdfhub/cad/bin/dwgread")
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_INTERMEDIATE_BYTES = 8 * 1024 * 1024
MAX_PAIR_COUNT = 150_000
MAX_ENTITY_COUNT = 2000
DWG_RUN_TIMEOUT = 35
DWG_VERSIONS = frozenset({
    b"AC1009", b"AC1012", b"AC1014", b"AC1015",
    b"AC1018", b"AC1021", b"AC1024", b"AC1027", b"AC1032",
})
ENTITY_COORD_CODES = frozenset({10, 20, 11, 21, 30, 31, 40})
# Only non-rendering identifiers and canonical DXF AcDb boilerplate
# may be dropped. Layers, colors, lineweights, scale overrides, visibility
# and layout selection must NOT be silently erased from engineering drawings.
IGNORED_ENTITY_HEADER_CODES = frozenset({5, 100, 330})
# Standard CAD frontends may emit zero thickness and a canonical +Z
# extrusion direction even for pure 2D LINE/CIRCLE. Accept only these exact
# semantic defaults; reject tilted planes, 3D geometry or styled drawings.
RESTRICTED_2D_NUMERIC_DEFAULTS = {39: 0.0, 210: 0.0, 220: 0.0, 230: 1.0}
RESTRICTED_ENTITY_DEFAULTS = {
    8: "0",       # default layer only
    6: "BYLAYER", # no custom line types
    48: "1.0",   # no line-type scaling
    60: "0",      # visible
    62: "256",    # bylayer color (layer 0)
    67: "0",      # model space
    370: "-1",    # bylayer line weight only
    410: "Model",
}


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (25, 26))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_INTERMEDIATE_BYTES,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))


def _verify_dwg_source(source: Path) -> None:
    if not 48 <= source.stat().st_size <= MAX_SOURCE_BYTES:
        raise ValueError("DWG file is absent or exceeds supported size")
    with source.open("rb") as stream:
        version = stream.read(6)
    if version not in DWG_VERSIONS:
        raise ValueError("DWG version is not supported by restricted CAD bridge")
    if not DWG_BINARY.is_file():
        raise ValueError("Audited, externally provisioned DWG native reader unavailable")


def _normalize_dwg_dxf(source: Path, target: Path) -> int:
    """Project a DXF ENTITIES section onto the strict LINE/CIRCLE shape grammar.

    Source DXF may contain HEADER/TABLES metadata; the restricted renderer
    reconstructs only explicitly supported simple geometry. If any drawing
    entity or geometry attribute is unrecognized, fail instead of dropping it.
    """
    # The external native reader may control the output directory. Do not
    # follow any symlink back into the privileged worker's filesystem.
    if (source.is_symlink() or not source.is_file()
            or not 0 < source.stat().st_size <= MAX_INTERMEDIATE_BYTES):
        raise ValueError("DWG decoder produced absent, unsafe or oversized DXF")
    raw = source.read_bytes()
    if b"\x00" in raw:
        raise ValueError("DWG reader produced unsupported binary DXF")
    try:
        lines = raw.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("DWG reader DXF is not ASCII/UTF-8") from exc
    if len(lines) % 2 or len(lines) // 2 > MAX_PAIR_COUNT:
        raise ValueError("DWG decoder emitted malformed or excessive DXF pairs")
    pairs: list[tuple[int, str]] = []
    for i in range(0, len(lines), 2):
        raw_code = lines[i].strip()
        value = lines[i + 1].strip()
        # Native DXF streams can contain negative temporary group codes and
        # extended 1000–1071 XDATA codes in HEADER/OBJECTS sections. They are
        # legitimate structural metadata, but MUST NOT enter our rendered
        # ENTITIES projection. Validate this standard outer envelope here;
        # semantic rendering restrictions are checked inside ENTITIES below.
        if not re.fullmatch(r"-?[0-9]{1,4}", raw_code) or len(value) > 1000:
            raise ValueError("DWG DXF has invalid group-code structure")
        code = int(raw_code)
        if not -5 <= code <= 1071:
            raise ValueError("DWG DXF group code is outside standard ranges")
        pairs.append((code, value))

    # Locate exactly one ENTITIES section; do not rely on native program
    # headers or mutate potentially attacker-controlled intermediate text.
    start = -1
    finish = -1
    idx = 0
    while idx < len(pairs) - 1:
        if pairs[idx] == (0, "SECTION"):
            if pairs[idx + 1] == (2, "ENTITIES"):
                if start >= 0:
                    raise ValueError("DWG DXF has multiple ENTITIES sections")
                start = idx + 2
                end = start
                while end < len(pairs) and pairs[end] != (0, "ENDSEC"):
                    end += 1
                if end == len(pairs):
                    raise ValueError("DWG DXF ENTITIES section has no end")
                finish = end
                idx = end
        idx += 1
    if start < 0 or finish < start:
        raise ValueError("DWG DXF has no drawable ENTITIES section")

    clean = [(0, "SECTION"), (2, "ENTITIES")]
    count = 0
    i = start
    while i < finish:
        code, kind = pairs[i]
        if code != 0 or kind not in {"LINE", "CIRCLE"}:
            raise ValueError("DWG uses unsupported non-LINE/CIRCLE CAD entity")
        clean.append((0, kind))
        count += 1
        if count > MAX_ENTITY_COUNT:
            raise ValueError("DWG geometry count exceeds supported limit")
        i += 1
        coords: set[int] = set()
        while i < finish and pairs[i][0] != 0:
            code, value = pairs[i]
            if code in ENTITY_COORD_CODES:
                if code in coords:
                    raise ValueError("DWG entity has ambiguous repeated coordinates")
                coords.add(code)
                clean.append((code, value))
            elif code in RESTRICTED_2D_NUMERIC_DEFAULTS:
                # Explicit +Z normal/zero thickness have no visible effect
                # on supported modelspace 2D geometry. Any nondefault tilt,
                # thickness or malformed number MUST fail closed.
                if (not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?", value)
                        or float(value) != RESTRICTED_2D_NUMERIC_DEFAULTS[code]):
                    raise ValueError("DWG uses nondefault 3D extrusion or thickness")
            elif code in RESTRICTED_ENTITY_DEFAULTS:
                # Preserve visual honesty. Our existing vector renderer
                # ignores styles, layers and print scale: only their exact
                # harmless default values can be safely projected.
                if value.upper() != RESTRICTED_ENTITY_DEFAULTS[code].upper():
                    raise ValueError("DWG entity requires unsupported styling or layout fidelity")
            elif code in IGNORED_ENTITY_HEADER_CODES:
                if code == 100 and value not in {"AcDbEntity", "AcDbLine", "AcDbCircle"}:
                    raise ValueError("DWG entity has unsupported AcDb subclass")
                # Identifiers/owner handles do not affect basic geometry.
            else:
                raise ValueError("DWG geometry has unsupported semantics")
            i += 1
    clean.extend([(0, "ENDSEC"), (0, "EOF")])
    if not count:
        raise ValueError("DWG contains no supported printable 2D entities")
    target.write_text("".join(f"{code}\n{value}\n" for code, value in clean), encoding="ascii")
    # Let the exact strict DXF parser perform final shape/radius/bounds checks.
    shapes = parse_dxf(target)
    if len(shapes) != count:
        raise ValueError("DWG shape projection count did not match source inventory")
    return count


def restricted_dwg_to_pdf(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("DWG source and PDF must differ")
    settings = get_settings()
    if not settings.to_pdf_tools_enabled or not settings.dwg_native_dev_enabled:
        raise RuntimeError("Native DWG bridge is disabled")
    _verify_dwg_source(source)
    with (TemporaryDirectory(prefix="pdfhub-dwg-native-") as folder,
          TemporaryDirectory(prefix="pdfhub-dwg-trusted-") as trusted):
        intermediate = Path(folder) / "drawing.dxf"
        verified = Path(trusted) / "native.dxf"
        canonical = Path(trusted) / "restricted.dxf"
        try:
            command = isolated_native_command(
                source, Path(folder),
                [
                    str(DWG_BINARY), "-O", "DXF", "-o",
                    "/output/drawing.dxf", SANDBOX_INPUT,
                ],
            )
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                start_new_session=True,
                close_fds=True,
                timeout=DWG_RUN_TIMEOUT,
                preexec_fn=_limits,
                env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Native DWG decoder failed or exceeded time limit") from exc
        if result.returncode != 0:
            raise ValueError("Native DWG reader rejected source")
        copy_native_regular_output(
            intermediate, verified,
            maximum_bytes=MAX_INTERMEDIATE_BYTES,
        )
        _normalize_dwg_dxf(verified, canonical)
        restricted_dxf_to_pdf(canonical, output)
