"""TIFF metadata extraction (read-only in this milestone).

EXIF is the TIFF IFD itself (read via piexif downstream); XMP is tag 700 and
IPTC-IIM is tag 33723, both in IFD0 — read here via Pillow's hardened TIFF tag
reader. Writing TIFF (rewriting the IFD/offsets while preserving pixels) is a
later, dedicated milestone.
"""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

from ..errors import MalformedImageError
from ._raw import RawMetadata

_TAG_XMP = 700
_TAG_IPTC = 33723


def extract(data: bytes) -> RawMetadata:
    # The whole TIFF is a valid EXIF/TIFF blob for piexif (used by the EXIF
    # codec downstream); XMP/IPTC tags are read via Pillow.
    raw = RawMetadata(exif=data)
    try:
        tags = Image.open(io.BytesIO(data)).tag_v2
    except Exception as exc:
        # Pillow can raise many types on hostile TIFFs (UnidentifiedImageError,
        # OSError, SyntaxError, ValueError, struct.error, DecompressionBombError,
        # …). Funnel them all to a clean library error.
        raise MalformedImageError(f"invalid TIFF: {exc}") from exc
    xmp = _tag_bytes(tags.get(_TAG_XMP))
    iptc = _tag_bytes(tags.get(_TAG_IPTC))
    if xmp:
        raw.xmp = xmp
    if iptc:
        raw.iptc = iptc
    return raw


def _tag_bytes(value: Any) -> bytes | None:
    """Normalise a Pillow tag value to raw bytes (Pillow's typing varies)."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, tuple):
        if len(value) == 1 and isinstance(value[0], (bytes, bytearray)):
            return bytes(value[0])
        if all(isinstance(x, int) and 0 <= x <= 255 for x in value):
            return bytes(value)
    return None
