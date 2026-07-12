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


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------
_UNSET = object()  # "leave this standard's segment untouched"


def rewrite(data: bytes, *, exif=_UNSET, xmp=_UNSET, iptc=_UNSET) -> bytes:
    """Return ``data`` with the managed metadata segments replaced.

    Each of ``exif`` / ``xmp`` / ``iptc`` may be:
    ``_UNSET`` (leave existing segment as-is), ``None``/empty (remove it), or
    ``bytes`` (set it). Non-metadata segments — and other Photoshop IRB
    resources — are preserved.
    """
    if data[:2] != _SOI:
        raise MalformedImageError("not a JPEG (missing SOI marker)")
    segments, tail = _split_segments(data)

    app0: list[bytes] = []
    others: list[bytes] = []
    existing_irb: bytes | None = None
    for marker, raw, payload in segments:
        if marker == 0xE1 and payload is not None and payload.startswith(_EXIF_ID):
            if exif is _UNSET:
                others.append(raw)
        elif marker == 0xE1 and payload is not None and payload.startswith(_XMP_ID):
            if xmp is _UNSET:
                others.append(raw)
        elif marker == 0xED and payload is not None and payload.startswith(_PS_ID):
            if iptc is _UNSET:
                others.append(raw)
            else:
                existing_irb = payload[len(_PS_ID) :]
        elif marker == 0xE0:
            app0.append(raw)
        else:
            others.append(raw)

    managed: list[bytes] = []
    if exif is not _UNSET and exif:
        managed.append(_app_segment(0xE1, exif))
    if xmp is not _UNSET and xmp:
        managed.append(_app_segment(0xE1, _XMP_ID + xmp))
    if iptc is not _UNSET:
        resources = [
            r for r in _parse_irb(existing_irb or b"") if r[0] != _IIM_RESOURCE
        ]
        if iptc:
            resources.append((_IIM_RESOURCE, b"\x00\x00", iptc))
        if resources:
            managed.append(_app_segment(0xED, _PS_ID + _build_irb(resources)))

    return _SOI + b"".join(app0) + b"".join(managed) + b"".join(others) + tail


def _split_segments(data: bytes) -> tuple[list[tuple[int, bytes, bytes | None]], bytes]:
    segments: list[tuple[int, bytes, bytes | None]] = []
    pos = 2
    n = len(data)
    while pos + 1 < n:
        if data[pos] != 0xFF:
            raise MalformedImageError(f"expected a marker at offset {pos}")
        while pos + 1 < n and data[pos + 1] == 0xFF:
            pos += 1
        if pos + 1 >= n:
            break
        marker = data[pos + 1]
        if marker in (0xDA, 0xD9):
            return segments, data[pos:]
        if 0xD0 <= marker <= 0xD7 or marker == 0x01:
            segments.append((marker, data[pos : pos + 2], None))
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
        segments.append((marker, data[pos:seg_end], data[pos + 4 : seg_end]))
        pos = seg_end
    return segments, b""


def _app_segment(marker: int, payload: bytes) -> bytes:
    if len(payload) + 2 > 0xFFFF:
        raise MalformedImageError(
            "metadata segment exceeds 64 KB (extended segments unsupported)"
        )
    return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload


def _parse_irb(data: bytes) -> list[tuple[int, bytes, bytes]]:
    """Parse a Photoshop IRB into ``(resource_id, raw_name_field, block)`` tuples."""
    resources: list[tuple[int, bytes, bytes]] = []
    pos = 0
    n = len(data)
    while pos + 6 <= n:
        if data[pos : pos + 4] != b"8BIM":
            break
        resource_id = struct.unpack(">H", data[pos + 4 : pos + 6])[0]
        pos += 6
        if pos >= n:
            raise MalformedImageError("truncated IRB resource name")
        name_field = data[pos] + 1
        if name_field % 2:
            name_field += 1
        name = data[pos : pos + name_field]
        pos += name_field
        if pos + 4 > n:
            raise MalformedImageError("truncated IRB resource size")
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4
        if pos + size > n:
            raise MalformedImageError("IRB resource size exceeds block")
        resources.append((resource_id, name, data[pos : pos + size]))
        pos += size + (size % 2)
    return resources


def _build_irb(resources: list[tuple[int, bytes, bytes]]) -> bytes:
    out = bytearray()
    for resource_id, name, block in resources:
        out += (
            b"8BIM"
            + struct.pack(">H", resource_id)
            + name
            + struct.pack(">I", len(block))
        )
        out += block
        if len(block) % 2:
            out += b"\x00"
    return bytes(out)
