"""Malformed / hostile input must raise a clean MetadataError, never a crash."""

import struct

import pytest

import svk_img_metadata as svk
from svk_img_metadata.errors import MalformedImageError

from _helpers import app1_xmp, app13_iptc, base_jpeg, splice


def _write(tmp_path, data: bytes):
    p = tmp_path / "bad.jpg"
    p.write_bytes(data)
    return p


def test_truncated_marker_segment(tmp_path):
    # APP1 claims a 16 KB length but the file ends immediately after.
    bad = b"\xff\xe1" + struct.pack(">H", 0x4000) + b"Exif\x00\x00\x00\x00"
    with pytest.raises(MalformedImageError):
        svk.read(_write(tmp_path, splice(base_jpeg(), bad)))


def test_iptc_length_exceeds_data(tmp_path):
    # Dataset declares 500 bytes but supplies one.
    bogus = b"\x1c" + bytes([2, 120]) + struct.pack(">H", 500) + b"x"
    with pytest.raises(MalformedImageError):
        svk.read(_write(tmp_path, splice(base_jpeg(), app13_iptc(bogus))))


def test_garbage_exif_blob(tmp_path):
    payload = b"Exif\x00\x00" + b"\xff\xff\xff\xff not a tiff header"
    seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    with pytest.raises(MalformedImageError):
        svk.read(_write(tmp_path, splice(base_jpeg(), seg)))


def test_xmp_billion_laughs_rejected(tmp_path):
    # Internal entity expansion — defusedxml must refuse it.
    packet = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="">&lol2;</rdf:Description>'
        b"</rdf:RDF></x:xmpmeta>"
    )
    with pytest.raises(MalformedImageError):
        svk.read(_write(tmp_path, splice(base_jpeg(), app1_xmp(packet))))


def test_xmp_external_entity_rejected(tmp_path):
    packet = (
        b'<?xml version="1.0"?>'
        b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="">&xxe;</rdf:Description>'
        b"</rdf:RDF></x:xmpmeta>"
    )
    with pytest.raises(MalformedImageError):
        svk.read(_write(tmp_path, splice(base_jpeg(), app1_xmp(packet))))


def test_non_jpeg_extension_rejected(tmp_path):
    with pytest.raises(svk.UnsupportedFormatError):
        svk.read(_write(tmp_path, b"\x00\x01\x02\x03 not an image"))
