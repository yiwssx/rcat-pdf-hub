"""T90-2 HEIC/HEIF native decoder prototype; NOT PUBLICLY ROUTED.

Requires a separately supplied libheif >= 1.23.7 runtime and matching
heif-dec binary, independently audited native codec plugins, network-denied
process sandbox and real HEIC/HEIF sample validation before any rollout.

No unsafe/old libheif wheel or apt build is installed by this module.
"""
from __future__ import annotations

from pathlib import Path
import re
import resource
import sys
from tempfile import TemporaryFile
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.services import pdf_tools
from app.services.native_sandbox import SANDBOX_INPUT, isolated_native_command
from app.services.native_output_guard import copy_native_regular_output

MAX_SOURCE_BYTES = 24 * 1024 * 1024
MAX_PAGES = 64
MAX_SINGLE_PIXELS = 20_000_000
MAX_TOTAL_PIXELS = 50_000_000
MAX_SINGLE_PNG_BYTES = 12 * 1024 * 1024
MAX_TOTAL_DECODED_PNG_BYTES = 96 * 1024 * 1024
MAX_CONVERTER_PDF_BYTES = 40 * 1024 * 1024
MINIMUM_LIBHEIF_VERSION = (1, 23, 7)
# This must be a separately managed, version-pinned executable, not the
# outdated Bookworm system package or an embedded vulnerable Python wheel.
HEIF_BINARY = Path("/opt/pdfhub/heif/bin/heif-dec")
HEIF_SHARED_LIBRARY = Path("/opt/pdfhub/heif/lib/libheif.so.1")


def _checked_heif_container(source: Path, *, suffix: str) -> None:
    if suffix not in {".heic", ".heif"}:
        raise ValueError("Only HEIC or HEIF file extensions accepted")
    size = source.stat().st_size
    if not 16 <= size <= MAX_SOURCE_BYTES:
        raise ValueError("HEIF input outside supported file-size limits")
    with source.open("rb") as stream:
        first = stream.read(144)
    if len(first) < 16 or first[4:8] != b"ftyp":
        raise ValueError("HEIF file-type box missing")
    box_bytes = int.from_bytes(first[:4], "big")
    if not 16 <= box_bytes <= 144 or box_bytes % 4 or box_bytes > size:
        raise ValueError("HEIF brands box is malformed or oversized")
    # ISO BMFF ftyp: major_brand (offset 8), minor_version (12), then
    # compatible_brands (16+). The minor_version is NOT itself a brand.
    # Constructing a set first and then discarding the minor-version bytes
    # incorrectly removed the major brand if those four bytes matched.
    brands = {first[8:12]}
    brands.update(first[offset:offset+4] for offset in range(16, box_bytes, 4))
    if not brands.intersection({
        b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1",
    }):
        raise ValueError("HEIF container is not an allowed HEIC/HEIF brand")
    if suffix == ".heic" and not brands.intersection({b"heic", b"heix", b"hevc", b"hevx"}):
        raise ValueError("HEIC file does not declare an HEVC image brand")


def _checked_patched_heif_runtime(source: Path) -> None:
    """Probe the native libheif ABI ONLY inside the no-network sandbox.

    ctypes.CDLL() in the privileged RQ worker would execute the library's
    constructors before any isolation. The helper subprocess performs the
    actual version lookup under resource/timeout and read-only constraints.
    """
    if not HEIF_SHARED_LIBRARY.is_file() or not HEIF_BINARY.is_file():
        raise ValueError("Pinned patched HEIF decoder runtime is not provisioned")

    def _probe_limits() -> None:
        resource.setrlimit(resource.RLIMIT_CPU, (4, 5))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))

    command = isolated_native_command(
        source, None,
        [sys.executable, "-m", "app.services.to_pdf_heif_version_worker", SANDBOX_INPUT],
        env={"LD_LIBRARY_PATH": "/opt/pdfhub/heif/lib"},
    )
    with TemporaryFile(mode="w+b") as captured:
        try:
            result = subprocess.run(
                command,
                stdout=captured,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=8,
                close_fds=True,
                start_new_session=True,
                preexec_fn=_probe_limits,
                env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("Isolated HEIF library version check could not complete") from exc
        if result.returncode != 0 or captured.tell() > 128:
            raise ValueError("Native HEIF library version probe failed")
        captured.seek(0)
        raw = captured.read(129).strip()
    match = re.fullmatch(rb"(\d+)\.(\d+)\.(\d+)(?:[-+][A-Za-z0-9._-]+)?", raw)
    if not match:
        raise ValueError("Native HEIF runtime version is ambiguous")
    version = tuple(int(part) for part in match.groups())
    if version < MINIMUM_LIBHEIF_VERSION:
        raise ValueError("Native libheif below patched security minimum 1.23.7")


def _native_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (25, 26))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (48, 48))


def _page_sequence(folder: Path) -> list[Path]:
    # Upstream heif-dec may name multiple outputs page-1.png, page-2.png;
    # reject irregular/unexpected names instead of omitting decoded frames.
    outputs = list(folder.iterdir())
    if not outputs or len(outputs) > MAX_PAGES:
        raise ValueError("HEIF decoder produced no frames or too many frames")
    pages = []
    seen = set()
    total_bytes = 0
    for file in outputs:
        if not file.is_file() or file.is_symlink():
            raise ValueError("HEIF decoder produced an unsafe artifact")
        size = file.stat().st_size
        total_bytes += size
        if (not 0 < size <= MAX_SINGLE_PNG_BYTES
                or total_bytes > MAX_TOTAL_DECODED_PNG_BYTES):
            raise ValueError("HEIF decoded frame output exceeds disk budget")
        match = re.fullmatch(r"page(?:-([1-9]\d*))?\.png", file.name)
        if not match:
            raise ValueError("HEIF decoder output filename is unsupported")
        number = int(match.group(1)) if match.group(1) else 1
        if number in seen:
            raise ValueError("HEIF output frame numbers overlap")
        seen.add(number)
        pages.append((number, file))
    pages.sort(key=lambda item: item[0])
    if [number for number, _ in pages] != list(range(1, len(pages)+1)):
        raise ValueError("HEIF output frames are incomplete")
    return [path for _, path in pages]


def heif_to_pdf(source: Path, output: Path, *, suffix: str) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("HEIF source and output must differ")
    settings = get_settings()
    if not settings.to_pdf_tools_enabled or not settings.heif_native_dev_enabled:
        raise RuntimeError("HEIC/HEIF development decoder is disabled")
    _checked_heif_container(source, suffix=suffix)
    _checked_patched_heif_runtime(source)

    with (TemporaryDirectory(prefix="pdfhub-heif-native-") as directory,
          TemporaryDirectory(prefix="pdfhub-heif-trusted-") as trusted):
        folder = Path(directory)
        trusted_folder = Path(trusted)
        # Explicit no-shell argv. Native decoder resources are bounded; its
        # surrounding container still needs a network-denied seccomp profile.
        try:
            command = isolated_native_command(
                source, folder,
                [str(HEIF_BINARY), SANDBOX_INPUT, "/output/page.png"],
                env={
                    "LD_LIBRARY_PATH": "/opt/pdfhub/heif/lib",
                    "LIBHEIF_PLUGIN_PATHS": "/opt/pdfhub/heif/lib/libheif",
                },
            )
            result = subprocess.run(
                command,
                timeout=35,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                start_new_session=True,
                close_fds=True,
                preexec_fn=_native_limits,
                env={"PATH": "/usr/bin:/bin"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError("HEIF native decoder timed out or is unavailable") from exc
        if result.returncode != 0:
            raise ValueError("HEIF decoder could not decode source images")
        pages = _page_sequence(folder)
        normalized = []
        pixels = 0
        for index, page in enumerate(pages):
            # Native decoder must not be able to mutate the pages that Pillow
            # and ReportLab subsequently parse in the trusted worker.
            verified_page = trusted_folder / page.name
            copy_native_regular_output(
                page, verified_page, maximum_bytes=MAX_SINGLE_PNG_BYTES,
            )
            try:
                with Image.open(verified_page) as bitmap:
                    count = bitmap.width * bitmap.height
                    pixels += count
                    if (bitmap.format != "PNG" or
                            getattr(bitmap, "n_frames", 1) != 1 or
                            not 0 < count <= MAX_SINGLE_PIXELS or
                            pixels > MAX_TOTAL_PIXELS):
                        raise ValueError("HEIF output pixel or frame limits exceeded")
                    # Preserve visual compositing semantics for alpha frames.
                    # A straight RGBA -> RGB conversion would replace fully
                    # transparent pixels with potentially black RGB values.
                    oriented = ImageOps.exif_transpose(bitmap)
                    try:
                        rgba = oriented.convert("RGBA")
                        try:
                            normalized_frame = Image.new("RGB", rgba.size, "white")
                            try:
                                normalized_frame.paste(rgba, mask=rgba.getchannel("A"))
                                target = trusted_folder / f"normalized-{index:04d}.png"
                                normalized_frame.save(target, "PNG")
                                normalized.append(target)
                            finally:
                                normalized_frame.close()
                        finally:
                            rgba.close()
                    finally:
                        oriented.close()
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError("Native HEIF output is corrupt or excessive") from exc

        # Never persist an unvalidated candidate to the final output path.
        # Common PDF checking enforces exact page count, strict PDF parsing,
        # size and visible raster content before publishing artifact bytes.
        candidate = trusted_folder / "candidate.pdf"
        pdf_tools.images_to_pdf(normalized, candidate, page_size="a4",
                                fit="contain", margin=18, dpi=150)
        if not 0 < candidate.stat().st_size <= MAX_CONVERTER_PDF_BYTES:
            raise ValueError("Decoded HEIF PDF is invalid or oversized")
        from app.services.to_pdf_engine import _checked_pdf
        _checked_pdf(candidate.read_bytes(), output, expected_pages=len(pages))
