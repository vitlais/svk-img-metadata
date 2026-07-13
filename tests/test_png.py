"""M3: PNG read/write (EXIF via eXIf, XMP via iTXt; no IPTC)."""

import struct
import zlib

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import svk_img_metadata as svk
from svk_img_metadata.errors import MalformedImageError
from svk_img_metadata.model import GPSCoord, LangAlt


def _png_chunk(ctype: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + ctype
        + body
        + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
    )


def _png(tmp_path, name="src.png", pnginfo=None):
    p = tmp_path / name
    Image.new("RGB", (6, 6), "purple").save(p, "PNG", pnginfo=pnginfo)
    return p


def test_png_round_trip(tmp_path):
    m = svk.read(_png(tmp_path))
    m.description = LangAlt("PNG caption")
    m.keywords = ["a", "b"]
    m.gps = GPSCoord(59.0, 18.0)
    out = tmp_path / "out.png"
    m.save(out)

    r = svk.read(out)
    assert str(r.description) == "PNG caption"
    assert r.keywords == ["a", "b"]
    assert r.gps == GPSCoord(59.0, 18.0)
    assert Image.open(out).size == (6, 6)  # pixels intact


def test_png_has_no_iptc(tmp_path):
    m = svk.read(_png(tmp_path))
    m.keywords = ["k"]
    out = tmp_path / "out.png"
    m.save(out)
    r = svk.read(out)
    assert r.keywords == ["k"]  # via XMP
    assert r.iptc == {}  # nothing written to a (nonexistent) IPTC slot


def test_png_preserves_other_chunks(tmp_path):
    info = PngInfo()
    info.add_text("Comment", "keep me")
    m = svk.read(_png(tmp_path, pnginfo=info))
    m.rating = 4
    out = tmp_path / "out.png"
    m.save(out)
    # The unrelated tEXt chunk must survive the rewrite.
    assert b"keep me" in out.read_bytes()
    assert svk.read(out).rating == 4


def test_png_clear_field(tmp_path):
    m = svk.read(_png(tmp_path))
    m.description = "cap"
    out = tmp_path / "out.png"
    m.save(out)
    m2 = svk.read(out)
    m2.description = None
    m2.save(out)
    assert svk.read(out).description is None


def test_png_corrupt_compressed_itxt_raises_clean(tmp_path):
    # iTXt with compression flag = 1 but a non-zlib payload must map to a
    # MetadataError, not a bare zlib.error.
    body = b"XML:com.adobe.xmp\x00\x01\x00\x00\x00not-valid-zlib"
    base = _png(tmp_path).read_bytes()
    # Insert the hostile iTXt right after the 8-byte signature + IHDR chunk.
    ihdr_end = 8 + 8 + struct.unpack(">I", base[8:12])[0] + 4
    data = base[:ihdr_end] + _png_chunk(b"iTXt", body) + base[ihdr_end:]
    p = tmp_path / "bad.png"
    p.write_bytes(data)
    with pytest.raises(MalformedImageError):
        svk.read(p)
