#!/usr/bin/env python3
"""Install a verified locally supplied Office font ZIP into Gotenberg build context.

Does not publish font binaries to Git or download font binaries from the web.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "ops/gotenberg/13fonts-manifest.json"
DESTINATION_ROOT = REPO_ROOT / "ops/gotenberg/fonts"
MAX_FILE_SIZE = 2 * 1024 * 1024
MAX_TOTAL_SIZE = 32 * 1024 * 1024
SFNT_SIGNATURES = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")


class FontBundleError(ValueError):
    pass


def fingerprint(items: dict[str, str]) -> str:
    lines = "".join(f"{name}\t{items[name]}\n" for name in sorted(items))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def _safe_file_name(member: zipfile.ZipInfo) -> str | None:
    name = member.filename
    if member.is_dir():
        return None
    path = PurePosixPath(name)
    if (
        path.is_absolute()
        or "\\" in name
        or any(part in (".", "..", "") for part in name.split("/"))
        or len(path.parts) not in (1, 2)
        or (len(path.parts) == 2 and path.parts[0] != "13Fonts")
    ):
        raise FontBundleError(f"Unsafe archive member: {name!r}")
    filename = path.name
    if Path(filename).suffix.lower() not in (".ttf", ".otf"):
        raise FontBundleError(f"Unexpected non-font file in archive: {name!r}")
    if member.file_size > MAX_FILE_SIZE:
        raise FontBundleError(f"Font too large: {name!r}")
    if (member.external_attr >> 16) & 0o170000 == 0o120000:
        raise FontBundleError(f"Symbolic link prohibited: {name!r}")
    return filename


def load_verified_fonts(archive: Path, manifest: dict) -> dict[str, bytes]:
    fonts: dict[str, bytes] = {}
    seen_folded: set[str] = set()
    total_size = 0
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            filename = _safe_file_name(member)
            if filename is None:
                continue
            folded = filename.casefold()
            if folded in seen_folded:
                raise FontBundleError(f"Duplicate font filename: {filename}")
            seen_folded.add(folded)
            total_size += member.file_size
            if total_size > MAX_TOTAL_SIZE:
                raise FontBundleError("Uncompressed archive too large")
            with bundle.open(member) as stream:
                payload = stream.read(MAX_FILE_SIZE + 1)
            if len(payload) != member.file_size or payload[:4] not in SFNT_SIGNATURES:
                raise FontBundleError(f"Invalid or unreadable font: {filename}")
            fonts[filename] = payload
    hashes = {filename: hashlib.sha256(payload).hexdigest() for filename, payload in fonts.items()}
    if len(fonts) != manifest["font_count"]:
        raise FontBundleError(f"Expected {manifest['font_count']} fonts; found {len(fonts)}")
    if fingerprint(hashes) != manifest["fingerprint_sha256"]:
        raise FontBundleError("Font bundle fingerprint mismatch: contents differ from uploaded 13Fonts.zip")
    return fonts


def install_fonts(fonts: dict[str, bytes], root: Path, bundle_folder: str = "13fonts") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    destination = root / bundle_folder
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise FontBundleError("Refusing to replace a non-directory font bundle")
    with tempfile.TemporaryDirectory(prefix=".office-font-stage-", dir=root) as tmp:
        stage = Path(tmp) / "new"
        stage.mkdir()
        for name, data in fonts.items():
            (stage / name).write_bytes(data)
        backup = Path(tmp) / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            stage.rename(destination)
        except BaseException:
            if backup.exists():
                backup.rename(destination)
            raise
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate/install all 57 approved 13Fonts files without publishing font binaries")
    parser.add_argument("archive", type=Path, help="Local path to original 13Fonts.zip")
    parser.add_argument("--verify-only", action="store_true", help="Check archive integrity; do not install")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    try:
        fonts = load_verified_fonts(args.archive, manifest)
        if args.verify_only:
            print(f"PASS bundle: {len(fonts)} font files match uploaded archive fingerprint")
        else:
            destination = install_fonts(fonts, DESTINATION_ROOT)
            print(f"PASS installed: {len(fonts)} font files into {destination}")
            print("Next: rebuild only the Gotenberg service using your active Compose mode")
        return 0
    except (OSError, zipfile.BadZipFile, FontBundleError, KeyError) as exc:
        print(f"FAIL office font bundle: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
