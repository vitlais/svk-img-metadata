"""M1: JPEG read path — per-standard decode and precedence merge."""

import piexif

import svk_img_metadata as svk
from svk_img_metadata.model import GPSCoord, LangAlt, MetaDate

from _helpers import app1_xmp, app13_iptc, base_jpeg, exif_blob, iim, splice, xmp_packet


def _write(tmp_path, data: bytes):
    p = tmp_path / "img.jpg"
    p.write_bytes(data)
    return p


def test_reads_exif(tmp_path):
    blob = exif_blob(
        zeroth={
            piexif.ImageIFD.Artist: b"Jane Doe",
            piexif.ImageIFD.ImageDescription: b"cap",
        },
        exif={piexif.ExifIFD.DateTimeOriginal: b"2026:07:12 14:30:00"},
        gps={
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: ((59, 1), (0, 1), (0, 1)),
            piexif.GPSIFD.GPSLongitudeRef: b"W",
            piexif.GPSIFD.GPSLongitude: ((18, 1), (0, 1), (0, 1)),
        },
    )
    m = svk.read(_write(tmp_path, base_jpeg(blob)))
    assert m.creator == ["Jane Doe"]
    assert str(m.description) == "cap"
    assert isinstance(m.date_created, MetaDate)
    assert m.date_created.value.year == 2026
    assert m.gps == GPSCoord(59.0, -18.0, None)


def test_reads_iptc(tmp_path):
    stream = iim(
        [
            (2, 120, b"A caption"),
            (2, 25, b"sky"),
            (2, 25, b"sea"),
            (2, 90, "Göteborg".encode()),  # UTF-8 round-trip
            (2, 55, b"20260712"),
            (2, 60, b"143000+0000"),
        ]
    )
    m = svk.read(_write(tmp_path, splice(base_jpeg(), app13_iptc(stream))))
    assert str(m.description) == "A caption"
    assert m.keywords == ["sky", "sea"]
    assert m.city == "Göteborg"
    assert m.date_created.value.hour == 14


def test_reads_xmp(tmp_path):
    body = (
        "<dc:description><rdf:Alt>"
        '<rdf:li xml:lang="x-default">XMP cap</rdf:li>'
        '<rdf:li xml:lang="sv">bildtext</rdf:li>'
        "</rdf:Alt></dc:description>"
        "<dc:subject><rdf:Bag><rdf:li>a</rdf:li><rdf:li>b</rdf:li></rdf:Bag></dc:subject>"
        "<xmp:Rating>4</xmp:Rating>"
        "<photoshop:City>Stockholm</photoshop:City>"
    )
    m = svk.read(_write(tmp_path, splice(base_jpeg(), app1_xmp(xmp_packet(body)))))
    assert isinstance(m.description, LangAlt)
    assert m.description.get("sv") == "bildtext"
    assert str(m.description) == "XMP cap"
    assert m.keywords == ["a", "b"]
    assert m.rating == 4
    assert m.city == "Stockholm"


def test_precedence_xmp_over_iptc_over_exif(tmp_path):
    blob = exif_blob(zeroth={piexif.ImageIFD.ImageDescription: b"exif cap"})
    stream = iim([(2, 120, b"iptc cap"), (2, 105, b"iptc headline")])
    xmp = app1_xmp(
        xmp_packet(
            "<dc:description><rdf:Alt>"
            '<rdf:li xml:lang="x-default">xmp cap</rdf:li>'
            "</rdf:Alt></dc:description>"
        )
    )
    data = splice(base_jpeg(blob), xmp, app13_iptc(stream))
    m = svk.read(_write(tmp_path, data))
    assert str(m.description) == "xmp cap"  # XMP wins
    assert m.headline == "iptc headline"  # only IPTC has it


def test_no_metadata_is_empty(tmp_path):
    m = svk.read(_write(tmp_path, base_jpeg()))
    assert m.present_fields() == []
    assert m.source_format == "jpeg"
