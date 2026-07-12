"""Builders for JPEG test fixtures with embedded EXIF / IPTC / XMP.

Lets M1 (read) be tested before M2 (write) exists: we assemble the marker
segments by hand and splice them in right after the SOI, which is valid JPEG.
"""

from __future__ import annotations

import io
import struct

import piexif
from PIL import Image

XMP_APP1_ID = b"http://ns.adobe.com/xap/1.0/\x00"


def base_jpeg(exif_bytes: bytes | None = None) -> bytes:
    """A tiny red JPEG, optionally carrying an EXIF blob from ``piexif.dump``."""
    buf = io.BytesIO()
    img = Image.new("RGB", (4, 4), "red")
    if exif_bytes is not None:
        img.save(buf, "JPEG", exif=exif_bytes)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def exif_blob(zeroth=None, exif=None, gps=None) -> bytes:
    return piexif.dump(
        {
            "0th": zeroth or {},
            "Exif": exif or {},
            "GPS": gps or {},
            "1st": {},
            "thumbnail": None,
        }
    )


def iim(datasets: list[tuple[int, int, bytes]]) -> bytes:
    """Build an IPTC-IIM datastream from ``(record, dataset, value)`` triples."""
    out = b""
    for record, dataset, value in datasets:
        out += (
            b"\x1c" + bytes([record, dataset]) + struct.pack(">H", len(value)) + value
        )
    return out


def app13_iptc(iim_bytes: bytes) -> bytes:
    """Wrap an IIM stream in a Photoshop IRB inside an APP13 segment."""
    irb = (
        b"8BIM"
        + struct.pack(">H", 0x0404)
        + b"\x00\x00"
        + struct.pack(">I", len(iim_bytes))
    )
    irb += iim_bytes + (b"\x00" if len(iim_bytes) % 2 else b"")
    payload = b"Photoshop 3.0\x00" + irb
    return b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload


def app1_xmp(xmp_bytes: bytes) -> bytes:
    payload = XMP_APP1_ID + xmp_bytes
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def splice(jpeg: bytes, *segments: bytes) -> bytes:
    """Insert ``segments`` immediately after the SOI marker."""
    return jpeg[:2] + b"".join(segments) + jpeg[2:]


def xmp_packet(body: str) -> bytes:
    """Wrap RDF ``body`` (rdf:Description children) in a full XMP packet."""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about=""'
        ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:xmp="http://ns.adobe.com/xap/1.0/"'
        ' xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/">'
        f"{body}"
        "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    ).encode("utf-8")
