"""JPEG marker-segment metadata extraction.

Walks the APPn marker segments before the start-of-scan, pulling out the EXIF
(APP1 ``Exif\\x00\\x00``), XMP (APP1 Adobe id) and IPTC-IIM (APP13 Photoshop
IRB, resource ``0x0404``) blobs. Every length is bounds-checked against the
remaining bytes; anything inconsistent raises
:class:`~svk_img_metadata.errors.MalformedImageError`.
"""

from __future__ import annotations

import struct

from ..errors import MalformedImageError
from ._raw import RawMetadata

_SOI = b"\xff\xd8"
_EXIF_ID = b"Exif\x00\x00"
_XMP_ID = b"http://ns.adobe.com/xap/1.0/\x00"
_PS_ID = b"Photoshop 3.0\x00"
_IIM_RESOURCE = 0x0404


def extract(data: bytes) -> RawMetadata:
    """Extract raw EXIF/XMP/IPTC blobs from JPEG ``data``."""
    if data[:2] != _SOI:
        raise MalformedImageError("not a JPEG (missing SOI marker)")

    raw = RawMetadata()
    pos = 2
    n = len(data)
    while pos + 1 < n:
        if data[pos] != 0xFF:
            raise MalformedImageError(f"expected a marker at offset {pos}")
        # Skip fill bytes (0xFF padding before the marker code).
        while pos + 1 < n and data[pos + 1] == 0xFF:
            pos += 1
        if pos + 1 >= n:
            break
        marker = data[pos + 1]

        # Start of scan / end of image: metadata segments are all behind us.
        if marker in (0xDA, 0xD9):
            break
        # Standalone markers with no length field (RSTn, TEM).
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            pos += 2
            continue

        if pos + 4 > n:
            raise MalformedImageError("truncated marker segment header")
        seg_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
        if seg_len < 2:
            raise MalformedImageError("invalid marker segment length")
        seg_end = pos + 2 + seg_len
        if seg_end > n:
            raise MalformedImageError("marker segment length exceeds file size")
        payload = data[pos + 4 : seg_end]

        if marker == 0xE1:  # APP1: EXIF or XMP
            if payload.startswith(_EXIF_ID) and raw.exif is None:
                raw.exif = payload
            elif payload.startswith(_XMP_ID) and raw.xmp is None:
                raw.xmp = payload[len(_XMP_ID) :]
        elif marker == 0xED:  # APP13: Photoshop IRB (IPTC lives here)
            if payload.startswith(_PS_ID) and raw.iptc is None:
                iim = _iptc_from_irb(payload[len(_PS_ID) :])
                if iim is not None:
                    raw.iptc = iim

        pos = seg_end
    return raw


def _iptc_from_irb(data: bytes) -> bytes | None:
    """Find IPTC-IIM (resource 0x0404) inside a Photoshop Image Resource Block."""
    pos = 0
    n = len(data)
    while pos + 6 <= n:
        if data[pos : pos + 4] != b"8BIM":
            break
        resource_id = struct.unpack(">H", data[pos + 4 : pos + 6])[0]
        pos += 6
        # Pascal-string resource name, padded to an even total length.
        if pos >= n:
            raise MalformedImageError("truncated IRB resource name")
        name_len = data[pos]
        name_field = name_len + 1
        if name_field % 2:
            name_field += 1
        pos += name_field
        if pos + 4 > n:
            raise MalformedImageError("truncated IRB resource size")
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4
        if pos + size > n:
            raise MalformedImageError("IRB resource size exceeds block")
        block = data[pos : pos + size]
        pos += size + (size % 2)  # data is padded to even length
        if resource_id == _IIM_RESOURCE:
            return block
    return None
