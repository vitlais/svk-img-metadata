"""PNG chunk metadata extraction and rewriting.

EXIF lives in an ``eXIf`` chunk (a raw TIFF/EXIF blob); XMP lives in an
``iTXt`` chunk keyed ``XML:com.adobe.xmp``. PNG has no standard IPTC slot.
All chunk lengths are bounds-checked against the file.
"""

from __future__ import annotations

import struct
import zlib

from ..errors import MalformedImageError
from ._raw import RawMetadata

_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_XMP_KEYWORD = b"XML:com.adobe.xmp"
_MAX_DECOMPRESSED = 16 * 1024 * 1024  # cap inflate output (zip-bomb guard)

_UNSET = object()


def _iter_chunks(data: bytes):
    if data[:8] != _SIGNATURE:
        raise MalformedImageError("not a PNG (bad signature)")
    pos = 8
    n = len(data)
    while pos + 8 <= n:
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        body = pos + 8
        end = body + length
        if end + 4 > n:
            raise MalformedImageError("PNG chunk length exceeds file size")
        yield ctype, data[body:end], data[pos : end + 4]
        pos = end + 4
        if ctype == b"IEND":
            break


def extract(data: bytes) -> RawMetadata:
    raw = RawMetadata()
    for ctype, body, _ in _iter_chunks(data):
        if ctype == b"eXIf" and raw.exif is None:
            raw.exif = body
        elif ctype == b"iTXt" and raw.xmp is None:
            keyword, text = _parse_itxt(body)
            if keyword == _XMP_KEYWORD and text is not None:
                raw.xmp = text
    return raw


def _parse_itxt(body: bytes) -> tuple[bytes | None, bytes | None]:
    nul = body.find(b"\x00")
    if nul < 0 or nul + 2 >= len(body):
        return None, None
    keyword = body[:nul]
    compressed = body[nul + 1]
    pos = nul + 3  # skip compression flag + method
    lang_end = body.find(b"\x00", pos)
    if lang_end < 0:
        return None, None
    trans_end = body.find(b"\x00", lang_end + 1)
    if trans_end < 0:
        return None, None
    text = body[trans_end + 1 :]
    if compressed == 1:
        text = _inflate(text)
    return keyword, text


def _inflate(data: bytes) -> bytes:
    obj = zlib.decompressobj()
    try:
        out = obj.decompress(data, _MAX_DECOMPRESSED)
    except zlib.error as exc:
        raise MalformedImageError(f"corrupt compressed PNG text: {exc}") from exc
    if obj.unconsumed_tail:
        raise MalformedImageError("compressed PNG text exceeds size limit")
    return out


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------
def rewrite(data: bytes, *, exif=_UNSET, xmp=_UNSET) -> bytes:
    """Return ``data`` with the ``eXIf`` / XMP ``iTXt`` chunks replaced."""
    ihdr: bytes | None = None
    iend: bytes | None = None
    others: list[bytes] = []
    for ctype, body, raw in _iter_chunks(data):
        if ctype == b"IHDR":
            ihdr = raw
        elif ctype == b"IEND":
            iend = raw
        elif ctype == b"eXIf" and exif is not _UNSET:
            continue  # managed: dropped, re-added below
        elif (
            ctype == b"iTXt"
            and xmp is not _UNSET
            and _parse_itxt(body)[0] == _XMP_KEYWORD
        ):
            continue
        else:
            others.append(raw)
    if ihdr is None:
        raise MalformedImageError("PNG missing IHDR chunk")

    managed: list[bytes] = []
    if exif is not _UNSET and exif:
        managed.append(_chunk(b"eXIf", exif))
    if xmp is not _UNSET and xmp:
        managed.append(_chunk(b"iTXt", _build_itxt(_XMP_KEYWORD, xmp)))

    tail = iend if iend is not None else _chunk(b"IEND", b"")
    return _SIGNATURE + ihdr + b"".join(managed) + b"".join(others) + tail


def _chunk(ctype: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + ctype
        + body
        + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
    )


def _build_itxt(keyword: bytes, text: bytes) -> bytes:
    # keyword \0 compflag compmethod langtag \0 transkeyword \0 text (uncompressed)
    return keyword + b"\x00" + b"\x00\x00" + b"\x00" + b"\x00" + text
