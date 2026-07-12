"""M2: JPEG write path — round-trip and preservation of unmodelled data."""

import struct
from datetime import datetime, timezone

import piexif
import pytest

import svk_img_metadata as svk
from svk_img_metadata.errors import MetadataError
from svk_img_metadata.model import GPSCoord, LangAlt, MetaDate

from _helpers import app1_xmp, base_jpeg, iim, splice, xmp_packet


def _src(tmp_path, data: bytes):
    p = tmp_path / "src.jpg"
    p.write_bytes(data)
    return p


def test_round_trip_all_standards(tmp_path):
    m = svk.read(_src(tmp_path, base_jpeg()))
    m.description = LangAlt("Hello")
    m.creator = ["Jane Doe"]
    m.keywords = ["sky", "sea"]
    m.city = "Stockholm"
    m.rating = 5
    m.date_created = MetaDate(datetime(2026, 7, 12, 14, 30, 0, tzinfo=timezone.utc))
    m.gps = GPSCoord(59.0, 18.0)
    out = tmp_path / "out.jpg"
    m.save(out)

    r = svk.read(out)
    assert str(r.description) == "Hello"
    assert r.creator == ["Jane Doe"]
    assert r.keywords == ["sky", "sea"]
    assert r.city == "Stockholm"
    assert r.rating == 5
    assert r.date_created.value.hour == 14
    assert r.gps == GPSCoord(59.0, 18.0)


def test_written_to_each_standard(tmp_path):
    m = svk.read(_src(tmp_path, base_jpeg()))
    m.description = "cap"
    m.keywords = ["k"]
    out = tmp_path / "out.jpg"
    m.save(out)

    r = svk.read(out)
    # description maps to all three; keywords to IPTC+XMP (not EXIF).
    assert 270 in r.exif["0th"]  # EXIF ImageDescription
    assert (2, 120) in r.iptc  # IPTC caption
    assert (2, 25) in r.iptc  # IPTC keywords
    assert "cap" in r.xmp.to_string()


def test_preserves_unmodelled_exif_tag(tmp_path):
    blob = piexif.dump(
        {
            "0th": {piexif.ImageIFD.Make: b"ACME"},
            "Exif": {},
            "GPS": {},
            "1st": {},
            "thumbnail": None,
        }
    )
    m = svk.read(_src(tmp_path, base_jpeg(blob)))
    m.city = "Stockholm"
    out = tmp_path / "out.jpg"
    m.save(out)
    assert svk.read(out).exif["0th"][piexif.ImageIFD.Make] == b"ACME"


def test_preserves_custom_xmp_namespace(tmp_path):
    body = (
        '<acme:Status xmlns:acme="https://acme.example/ns/1.0/">approved</acme:Status>'
    )
    data = splice(base_jpeg(), app1_xmp(xmp_packet(body)))
    m = svk.read(_src(tmp_path, data))
    m.rating = 3
    out = tmp_path / "out.jpg"
    m.save(out)
    assert "approved" in svk.read(out).xmp.to_string()


def test_preserves_other_irb_resources(tmp_path):
    extra = (
        b"8BIM"
        + struct.pack(">H", 0x03E8)
        + b"\x00\x00"
        + struct.pack(">I", 4)
        + b"DATA"
    )
    stream = iim([(2, 25, b"k1")])
    block = (
        b"8BIM"
        + struct.pack(">H", 0x0404)
        + b"\x00\x00"
        + struct.pack(">I", len(stream))
        + stream
    )
    payload = b"Photoshop 3.0\x00" + extra + block
    app13 = b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload
    m = svk.read(_src(tmp_path, splice(base_jpeg(), app13)))
    m.city = "Oslo"
    out = tmp_path / "out.jpg"
    m.save(out)
    raw = out.read_bytes()
    assert struct.pack(">H", 0x03E8) in raw and b"DATA" in raw


def test_clearing_a_field_removes_it_everywhere(tmp_path):
    m = svk.read(_src(tmp_path, base_jpeg()))
    m.city = "Stockholm"
    out = tmp_path / "out.jpg"
    m.save(out)

    m2 = svk.read(out)
    m2.city = None
    m2.save(out)

    r = svk.read(out)
    assert r.city is None
    assert (2, 90) not in r.iptc
    assert "Stockholm" not in (r.xmp.to_string() if r.xmp else "")


def test_selective_standards(tmp_path):
    m = svk.read(_src(tmp_path, base_jpeg()))
    m.description = "only xmp"
    out = tmp_path / "out.jpg"
    m.save(out, standards=("xmp",))
    r = svk.read(out)
    assert "only xmp" in r.xmp.to_string()
    assert r.exif.get("0th", {}).get(270) is None  # not written to EXIF


def test_save_in_place(tmp_path):
    src = _src(tmp_path, base_jpeg())
    m = svk.read(src)
    m.headline = "in place"
    m.save()  # no path -> overwrite source
    assert svk.read(src).headline == "in place"


def test_save_without_source_raises():
    m = svk.ImageMetadata()
    m.city = "Nowhere"
    with pytest.raises(MetadataError):
        m.save("/tmp/should-not-write.jpg")
