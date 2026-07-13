"""M3: TIFF read (EXIF via piexif, XMP tag 700, IPTC tag 33723). Write deferred."""

import io
import struct

import pytest
from PIL import Image, TiffImagePlugin

import svk_img_metadata as svk
from svk_img_metadata.errors import MalformedImageError

_XMP = (
    '<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">'
    "<xmp:Rating>5</xmp:Rating></rdf:Description></rdf:RDF></x:xmpmeta>"
)


def _tiff(tmp_path, with_xmp=True, with_iptc=True, with_exif=True):
    buf = io.BytesIO()
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    if with_exif:
        ifd[315] = "Ansel"  # Artist
    if with_xmp:
        ifd[700] = _XMP.encode()
        ifd.tagtype[700] = 7
    if with_iptc:
        iim = b"\x1c" + bytes([2, 120]) + struct.pack(">H", 3) + b"cap"
        ifd[33723] = iim
        ifd.tagtype[33723] = 7
    Image.new("RGB", (5, 5), "orange").save(buf, "TIFF", tiffinfo=ifd)
    p = tmp_path / "img.tiff"
    p.write_bytes(buf.getvalue())
    return p


def test_tiff_reads_all_standards(tmp_path):
    m = svk.read(_tiff(tmp_path))
    assert m.source_format == "tiff"
    assert m.creator == ["Ansel"]  # EXIF Artist
    assert m.rating == 5  # XMP tag 700
    assert str(m.description) == "cap"  # IPTC tag 33723


def test_tiff_without_extra_tags(tmp_path):
    m = svk.read(_tiff(tmp_path, with_xmp=False, with_iptc=False))
    assert m.creator == ["Ansel"]
    assert m.rating is None
    assert m.description is None


def test_tiff_write_not_yet_supported(tmp_path):
    m = svk.read(_tiff(tmp_path))
    m.rating = 3
    with pytest.raises(NotImplementedError):
        m.save(tmp_path / "out.tiff")


def test_malformed_tiff(tmp_path):
    p = tmp_path / "bad.tiff"
    p.write_bytes(b"II\x2a\x00" + b"\xff" * 8)  # valid magic, garbage IFD
    with pytest.raises(MalformedImageError):
        svk.read(p)


def test_tiff_pillow_errors_funneled(monkeypatch):
    # Any Pillow exception (incl. DecompressionBombError, struct.error) while
    # reading tags must surface as a clean MalformedImageError.
    from svk_img_metadata.containers import tiff

    def boom(*args, **kwargs):
        raise Image.DecompressionBombError("image exceeds pixel limit")

    monkeypatch.setattr(tiff.Image, "open", boom)
    with pytest.raises(MalformedImageError):
        tiff.extract(b"II\x2a\x00\x08\x00\x00\x00")
