"""Top-level smoke tests for the public API surface."""

import pytest

import svk_img_metadata as svk


def test_public_api_exports():
    for name in ("read", "ImageMetadata", "LangAlt", "MetaDate", "GPSCoord"):
        assert hasattr(svk, name)


def test_read_rejects_unknown_format(tmp_path):
    junk = tmp_path / "not-an-image.bin"
    junk.write_bytes(b"this is definitely not an image header")
    with pytest.raises(svk.UnsupportedFormatError):
        svk.read(junk)
