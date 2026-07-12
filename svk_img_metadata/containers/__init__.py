"""Container-format detection and dispatch.

Each supported format has a module here that knows how to pull the three raw
metadata blobs (EXIF / IPTC / XMP) out of the file and put them back. This
package sniffs the format and routes to the right one.
"""

from __future__ import annotations

import os
from typing import Any

from ..codecs import exif as exif_codec
from ..codecs import iptc as iptc_codec
from ..codecs import xmp as xmp_codec
from ..codecs.xmp import XmpDocument
from ..errors import MetadataError, UnsupportedFormatError
from ..model import ImageMetadata
from . import jpeg
from ._raw import RawMetadata

__all__ = ["detect_format", "load", "save_image", "SUPPORTED_FORMATS"]

#: Formats with (eventual) read/write support. HEIC is deferred.
SUPPORTED_FORMATS = ("jpeg", "tiff", "png")

# When a field is carried by several standards, the last-applied value wins.
# Order is lowest to highest priority: EXIF < IPTC < XMP.
_MERGE_ORDER = ("exif", "iptc", "xmp")

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


def _extract(fmt: str, data: bytes) -> RawMetadata:
    if fmt == "jpeg":
        return jpeg.extract(data)
    # TIFF and PNG extraction land in M3.
    raise NotImplementedError(f"reading {fmt!r} metadata is not implemented yet")


def load(path: str | os.PathLike[str]) -> ImageMetadata:
    """Read ``path`` into an :class:`~svk_img_metadata.model.ImageMetadata`.

    Decodes each present standard, exposes the raw per-standard views, and
    merges shared fields into the canonical accessors with EXIF < IPTC < XMP
    precedence.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    fmt = detect_format(data[:12])
    raw = _extract(fmt, data)

    meta = ImageMetadata(source_format=fmt)
    meta._source = data
    meta._source_path = path
    per_standard: dict[str, dict] = {"exif": {}, "iptc": {}, "xmp": {}}
    if raw.exif is not None:
        meta.exif, per_standard["exif"] = exif_codec.decode(raw.exif)
    if raw.iptc is not None:
        meta.iptc, per_standard["iptc"] = iptc_codec.decode(raw.iptc)
    if raw.xmp is not None:
        meta.xmp, per_standard["xmp"] = xmp_codec.decode(raw.xmp)

    for standard in _MERGE_ORDER:
        for field_name, value in per_standard[standard].items():
            meta.set(field_name, value)
    return meta


def save_image(meta: ImageMetadata, path, standards: tuple[str, ...]) -> None:
    """Rewrite ``meta`` back into its source container (see ImageMetadata.save)."""
    if meta._source is None:
        raise MetadataError("save() requires metadata read from a source image")
    if meta.source_format != "jpeg":
        # TIFF and PNG writing land in M3.
        raise NotImplementedError(
            f"writing {meta.source_format!r} is not implemented yet"
        )

    canonical = meta.to_dict()
    kwargs: dict[str, Any] = {}
    if "exif" in standards:
        kwargs["exif"] = exif_codec.encode(canonical, meta.exif or None)
    if "iptc" in standards:
        kwargs["iptc"] = iptc_codec.encode(canonical, meta.iptc or None)
    if "xmp" in standards:
        base_doc = meta.xmp if isinstance(meta.xmp, XmpDocument) else None
        kwargs["xmp"] = xmp_codec.encode(canonical, base_doc)

    new_bytes = jpeg.rewrite(meta._source, **kwargs)
    target = path if path is not None else meta._source_path
    if target is None:
        raise MetadataError("no destination path for save()")
    with open(target, "wb") as fh:
        fh.write(new_bytes)
