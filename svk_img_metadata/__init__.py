"""svk-img-metadata: read, write, and synchronise EXIF/IPTC/XMP image metadata.

Public API is re-exported here. See :func:`read` for the entry point and
:class:`ImageMetadata` for the model.
"""

from __future__ import annotations

import os

from .containers import SUPPORTED_FORMATS, detect_format, load as _load
from .errors import (
    MalformedImageError,
    MetadataError,
    UnsupportedFormatError,
    ValidationError,
)
from .fields import FIELDS, NAMESPACES, Standard, ValueKind
from .model import GPSCoord, ImageMetadata, LangAlt, MetaDate

__all__ = [
    "read",
    "ImageMetadata",
    "LangAlt",
    "MetaDate",
    "GPSCoord",
    "FIELDS",
    "NAMESPACES",
    "Standard",
    "ValueKind",
    "SUPPORTED_FORMATS",
    "detect_format",
    "MetadataError",
    "UnsupportedFormatError",
    "MalformedImageError",
    "ValidationError",
]


def read(path: str | os.PathLike[str]) -> ImageMetadata:
    """Read the metadata of the image at ``path`` into an :class:`ImageMetadata`.

    Raises :class:`~svk_img_metadata.errors.UnsupportedFormatError` for formats
    this library does not handle, and
    :class:`~svk_img_metadata.errors.MalformedImageError` for corrupt input.
    """
    return _load(path)
