"""Format-detection tests."""

import pytest

from svk_img_metadata.containers import detect_format
from svk_img_metadata.errors import UnsupportedFormatError

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 4
_TIFF_LE = b"II\x2a\x00" + b"\x00" * 4
_TIFF_BE = b"MM\x00\x2a" + b"\x00" * 4


@pytest.mark.parametrize(
    "header,expected",
    [(_JPEG, "jpeg"), (_PNG, "png"), (_TIFF_LE, "tiff"), (_TIFF_BE, "tiff")],
)
def test_detect_known_formats(header, expected):
    assert detect_format(header) == expected


@pytest.mark.parametrize("header", [b"", b"GIF89a", b"\x00\x01\x02\x03", b"%PDF-1.7"])
def test_detect_rejects_unknown(header):
    with pytest.raises(UnsupportedFormatError):
        detect_format(header)
