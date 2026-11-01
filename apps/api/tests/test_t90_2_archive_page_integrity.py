"""Real ZIP/CBZ page fidelity: mixed filenames, aliases and animated pages.

A structurally valid PDF is insufficient when page ordering is wrong or an
archive image silently loses animation frames. No Gotenberg or transport mocks.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile
import warnings

import pytest
from PIL import Image
from pypdf import PdfReader

from app.services.to_pdf_engine import archive_images_to_pdf


def _png(rgb: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (90, 60), rgb)
    try:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        image.close()


@pytest.mark.parametrize("kind", ["zip", "cbz"])
def test_mixed_numeric_and_text_names_keep_deterministic_image_page_order(tmp_path, kind):
    source = tmp_path / ("comic." + kind)
    # Reverse of expected: archive insertion order must not control pagination.
    pages = [
        ("cover.png", (255, 0, 255)),
        ("10.png", (0, 0, 255)),
        ("2.png", (0, 255, 0)),
        ("01.png", (255, 0, 0)),
    ]
    with ZipFile(source, "w", compression=ZIP_STORED) as archive:
        for name, color in pages:
            archive.writestr(name, _png(color))
    before = source.read_bytes()
    result = tmp_path / "output.pdf"
    archive_images_to_pdf(source, result, kind=kind)
    assert source.read_bytes() == before

    document = PdfReader(str(result), strict=True)
    assert len(document.pages) == 4
    expected_colors = [
        (255, 0, 0),    # 01
        (0, 255, 0),    # 2
        (0, 0, 255),    # 10
        (255, 0, 255),  # cover
    ]
    for page, color in zip(document.pages, expected_colors):
        assert page.images, "Every comic page must contain its source raster"
        image = Image.open(BytesIO(page.images[0].data))
        try:
            actual = image.convert("RGB").getpixel((45, 30))
            assert all(abs(actual[i] - color[i]) <= 12 for i in range(3))
        finally:
            image.close()


@pytest.mark.parametrize("kind", ["zip", "cbz"])
@pytest.mark.parametrize("names", [
    ("cover.png", "cover.png"),
    ("Folder/Cover.PNG", "folder/cover.png"),
])
def test_duplicate_or_casefold_colliding_pages_fail_closed(tmp_path, kind, names):
    source = tmp_path / ("duplicate." + kind)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with ZipFile(source, "w", compression=ZIP_STORED) as archive:
            archive.writestr(names[0], _png((255, 0, 0)))
            archive.writestr(names[1], _png((0, 0, 255)))
    out = tmp_path / "output.pdf"
    with pytest.raises(ValueError, match="Duplicate archive"):
        archive_images_to_pdf(source, out, kind=kind)
    assert not out.exists()


@pytest.mark.parametrize("kind", ["zip", "cbz"])
def test_animated_webp_pages_are_not_silently_truncated(tmp_path, kind):
    first = Image.new("RGB", (90, 60), "red")
    last = Image.new("RGB", (90, 60), "blue")
    try:
        buffer = BytesIO()
        first.save(
            buffer, "WEBP", save_all=True, append_images=[last],
            duration=250, loop=0, lossless=True,
        )
        animated = buffer.getvalue()
    finally:
        first.close()
        last.close()
    with Image.open(BytesIO(animated)) as reader:
        assert reader.n_frames == 2, "Test fixture must really be animated"
    source = tmp_path / ("animated." + kind)
    with ZipFile(source, "w") as archive:
        archive.writestr("001.webp", animated)
    output = tmp_path / "output.pdf"
    with pytest.raises(ValueError, match="Animated archive images"):
        archive_images_to_pdf(source, output, kind=kind)
    assert not output.exists()


def test_existing_comicinfo_metadata_remains_non_rendered(tmp_path):
    source = tmp_path / "metadata.cbz"
    with ZipFile(source, "w") as archive:
        archive.writestr("ComicInfo.xml", "<ComicInfo><Title>RCAT</Title></ComicInfo>")
        archive.writestr("1.png", _png((120, 50, 200)))
    out = tmp_path / "result.pdf"
    archive_images_to_pdf(source, out, kind="cbz")
    assert len(PdfReader(str(out), strict=True).pages) == 1
