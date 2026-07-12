"""The raw, undecoded metadata blobs a container yields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawMetadata:
    """Undecoded metadata blobs extracted from a container.

    Attributes:
        exif: EXIF blob including the ``Exif\\x00\\x00`` prefix (as accepted by
            ``piexif.load``), or ``None``.
        xmp: XMP packet bytes (RDF/XML), with any container-specific identifier
            prefix already stripped, or ``None``.
        iptc: IPTC-IIM datastream (the payload of Photoshop IRB resource
            ``0x0404``), or ``None``.
    """

    exif: bytes | None = None
    xmp: bytes | None = None
    iptc: bytes | None = None
