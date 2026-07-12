"""Regression tests: type-confused EXIF tags must not crash the decoder.

A hostile TIFF can declare a text/date/GPS-ref tag with a numeric type, so
piexif returns an int/tuple where the codec expects bytes. These must be skipped
or raised as MalformedImageError — never a bare AttributeError.
"""

import pytest

from svk_img_metadata.codecs import exif
from svk_img_metadata.errors import MalformedImageError
from svk_img_metadata.fields import ValueKind


@pytest.mark.parametrize(
    "kind", [ValueKind.LANG_ALT, ValueKind.TEXT_SEQ, ValueKind.DATE, ValueKind.TEXT]
)
@pytest.mark.parametrize("value", [1234, (1, 2), ((1, 2), (3, 4))])
def test_convert_skips_non_text_values(kind, value):
    # Must return None (skip) rather than raising AttributeError on .rstrip.
    assert exif._convert(kind, value) is None


def test_decode_gps_rejects_type_confused_ref():
    gps = {
        1: 5,  # GPSLatitudeRef declared as an int instead of b"N"/b"S"
        2: ((59, 1), (0, 1), (0, 1)),
        3: b"E",
        4: ((18, 1), (0, 1), (0, 1)),
    }
    with pytest.raises(MalformedImageError):
        exif._decode_gps(gps)


def test_decode_rejects_non_bytes_blob():
    with pytest.raises(MalformedImageError):
        exif.decode("/etc/passwd")  # str would be a file path to piexif
