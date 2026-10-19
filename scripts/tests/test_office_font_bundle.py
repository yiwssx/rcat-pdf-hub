"""Security and integrity tests, with no binary fonts committed to the repo."""
from __future__ import annotations

import hashlib
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from office_font_bundle import FontBundleError, fingerprint, install_fonts, load_verified_fonts  # noqa: E402


def make_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, payload in entries.items():
            z.writestr(name, payload)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = {
            "13Fonts/Example Regular.ttf": b"\x00\x01\x00\x00" + bytes(32),
            "13Fonts/Example Bold.ttf": b"\x00\x01\x00\x00" + bytes(64),
        }
        hashes = {Path(k).name: hashlib.sha256(v).hexdigest() for k, v in self.data.items()}
        self.manifest = {"font_count": len(hashes), "fingerprint_sha256": fingerprint(hashes)}
        self.zip = self.root / "fonts.zip"
        make_zip(self.zip, self.data)

    def test_verified_archive_and_atomic_install(self):
        fonts = load_verified_fonts(self.zip, self.manifest)
        root = self.root / "fonts"
        target = install_fonts(fonts, root)
        self.assertEqual(len(list(target.glob("*.ttf"))), 2)
        (target / "obsolete.ttf").write_bytes(b"old")
        target = install_fonts(fonts, root)
        self.assertFalse((target / "obsolete.ttf").exists())

    def test_reject_modified_font(self):
        changed = dict(self.data)
        changed["13Fonts/Example Bold.ttf"] += b"changed"
        make_zip(self.zip, changed)
        with self.assertRaisesRegex(FontBundleError, "fingerprint mismatch"):
            load_verified_fonts(self.zip, self.manifest)

    def test_reject_zip_path_traversal(self):
        make_zip(self.zip, {"13Fonts/../attack.ttf": next(iter(self.data.values()))})
        with self.assertRaisesRegex(FontBundleError, "Unsafe"):
            load_verified_fonts(self.zip, self.manifest)

    def test_reject_duplicate_names(self):
        make_zip(self.zip, {
            "13Fonts/Example.ttf": next(iter(self.data.values())),
            "Example.ttf": next(iter(self.data.values())),
        })
        with self.assertRaisesRegex(FontBundleError, "Duplicate"):
            load_verified_fonts(self.zip, self.manifest)

    def test_reject_unexpected_files(self):
        make_zip(self.zip, {"13Fonts/readme.sh": b"echo hi"})
        with self.assertRaisesRegex(FontBundleError, "non-font"):
            load_verified_fonts(self.zip, self.manifest)


if __name__ == "__main__":
    unittest.main()
