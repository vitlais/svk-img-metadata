"""Container-format detection and dispatch.

Each supported format has a module here that knows how to pull the three raw
metadata blobs (EXIF / IPTC / XMP) out of the file and put them back. This
package sniffs the format and routes to the right one.
"""

from __future__ import annotations

from ..errors import UnsupportedFormatError

__all__ = ["detect_format", "SUPPORTED_FORMATS"]

#: Formats with (eventual) read/write support. HEIC is deferred.
SUPPORTED_FORMATS = ("jpeg", "tiff", "png")

# Magic-byte signatures, checked against the file header.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TIFF_LE = b"II\x2a\x00"
_TIFF_BE = b"MM\x00\x2a"


def detect_format(header: bytes) -> str:
    """Identify the container format from the leading bytes of a file.

    Returns one of :data:`SUPPORTED_FORMATS`. Raises
    :class:`~svk_img_metadata.errors.UnsupportedFormatError` for anything else
    (including HEIC, which is not yet supported).
    """
    if header[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if header[:8] == _PNG_SIGNATURE:
        return "png"
    if header[:4] in (_TIFF_LE, _TIFF_BE):
        return "tiff"
    raise UnsupportedFormatError("unrecognised or unsupported image format")
