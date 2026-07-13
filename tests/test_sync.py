"""M4: directional sync between standards."""

import piexif
import pytest

import svk_img_metadata as svk
from svk_img_metadata.errors import MetadataError

from _helpers import app1_xmp, app13_iptc, base_jpeg, iim, splice, xmp_packet


def _jpeg_with(tmp_path, exif=None, iptc=None, xmp_body=None):
    segments = []
    if xmp_body is not None:
        segments.append(app1_xmp(xmp_packet(xmp_body)))
    if iptc is not None:
        segments.append(app13_iptc(iim(iptc)))
    data = splice(base_jpeg(exif), *segments)
    p = tmp_path / "s.jpg"
    p.write_bytes(data)
    return p


def _exif_desc(text):
    return piexif.dump(
        {
            "0th": {piexif.ImageIFD.ImageDescription: text},
            "Exif": {},
            "GPS": {},
            "1st": {},
            "thumbnail": None,
        }
    )


def test_sync_no_overwrite_keeps_existing(tmp_path):
    p = _jpeg_with(
        tmp_path,
        exif=_exif_desc(b"exif cap"),
        xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">xmp cap</rdf:li></rdf:Alt></dc:description>',
    )
    m = svk.read(p)
    assert str(m.description) == "xmp cap"  # XMP won on read
    changed = m.sync("exif", overwrite=False)
    assert "description" not in changed
    assert str(m.description) == "xmp cap"


def test_sync_overwrite_forces_source(tmp_path):
    p = _jpeg_with(
        tmp_path,
        exif=_exif_desc(b"exif cap"),
        xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">xmp cap</rdf:li></rdf:Alt></dc:description>',
    )
    m = svk.read(p)
    changed = m.sync("exif", overwrite=True)
    assert "description" in changed
    assert str(m.description) == "exif cap"


def test_sync_field_filter(tmp_path):
    p = _jpeg_with(tmp_path, iptc=[(2, 120, b"iptc cap"), (2, 105, b"iptc headline")])
    m = svk.read(p)
    # Wipe canonical, then sync only headline from IPTC.
    m.description = None
    m.headline = None
    changed = m.sync("iptc", fields=["headline"], overwrite=True)
    assert changed == ["headline"]
    assert m.headline == "iptc headline"
    assert m.description is None


def test_sync_targets_filter_skips_uncarried_fields(tmp_path):
    p = _jpeg_with(
        tmp_path,
        xmp_body="<xmp:Rating>5</xmp:Rating><photoshop:City>Sthlm</photoshop:City>",
    )
    m = svk.read(p)
    changed = m.sync("xmp", targets=["iptc"], overwrite=True)
    assert "rating" not in changed  # IPTC has no rating slot
    assert "city" in changed  # IPTC carries city


def test_sync_unknown_standard_raises(tmp_path):
    m = svk.read(_jpeg_with(tmp_path, exif=_exif_desc(b"x")))
    with pytest.raises(MetadataError):
        m.sync("bogus")
    with pytest.raises(MetadataError):
        m.sync("exif", targets=["nope"])


def test_sync_then_save_propagates(tmp_path):
    p = _jpeg_with(
        tmp_path,
        exif=_exif_desc(b"exif cap"),
        xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">xmp cap</rdf:li></rdf:Alt></dc:description>',
    )
    m = svk.read(p)
    m.sync("exif", overwrite=True)
    out = tmp_path / "out.jpg"
    m.save(out)
    r = svk.read(out)
    assert str(r.description) == "exif cap"  # now consistent across standards
    assert (2, 120) in r.iptc  # written into IPTC too
