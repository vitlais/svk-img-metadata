"""M6: validation, strip, and diff."""

import piexif
import pytest

import svk_img_metadata as svk
from svk_img_metadata.model import LangAlt

from _helpers import app1_xmp, base_jpeg, splice, xmp_packet


def _jpeg(tmp_path, exif=None, xmp_body=None):
    segs = [app1_xmp(xmp_packet(xmp_body))] if xmp_body else []
    p = tmp_path / "m.jpg"
    p.write_bytes(splice(base_jpeg(exif), *segs))
    return p


def _exif(**tags):
    zeroth = {}
    if "description" in tags:
        zeroth[piexif.ImageIFD.ImageDescription] = tags["description"]
    return piexif.dump(
        {"0th": zeroth, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    )


# ---------------- validation ----------------
def test_validate_pass_and_fail(tmp_path):
    m = svk.read(_jpeg(tmp_path, exif=_exif(description=b"cap")))
    assert m.validate(svk.RequiredFields(["description"])).ok
    result = m.validate(svk.RequiredFields(["description", "creator"]))
    assert not result.ok
    assert result.missing == ["creator"]
    assert bool(result) is False


def test_validate_per_standard(tmp_path):
    m = svk.read(
        _jpeg(
            tmp_path,
            xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">c</rdf:li></rdf:Alt></dc:description>',
        )
    )
    # description present in XMP, absent in EXIF/IPTC.
    assert m.validate(svk.RequiredFields([("description", "xmp")])).ok
    assert m.validate(svk.RequiredFields([("description", "iptc")])).missing == [
        "description@iptc"
    ]


def test_validate_strict_raises(tmp_path):
    m = svk.read(_jpeg(tmp_path))
    with pytest.raises(svk.ValidationError):
        m.validate(svk.RequiredFields(["copyright"]), strict=True)


def test_validate_unknown_field_rejected():
    with pytest.raises(svk.MetadataError):
        svk.RequiredFields(["not_a_field"])


def test_empty_value_counts_as_missing(tmp_path):
    m = svk.read(_jpeg(tmp_path))
    m.description = LangAlt()  # empty
    assert m.validate(svk.RequiredFields(["description"])).missing == ["description"]


# ---------------- strip ----------------
def test_strip_specific_field(tmp_path):
    m = svk.read(_jpeg(tmp_path, exif=_exif(description=b"cap")))
    m.city = "Stockholm"
    cleared = m.strip(fields=["city"])
    assert cleared == ["city"]
    assert m.city is None
    assert str(m.description) == "cap"  # untouched


def test_strip_all_and_save(tmp_path):
    m = svk.read(_jpeg(tmp_path, exif=_exif(description=b"cap")))
    m.keywords = ["k"]
    m.strip()
    assert m.present_fields() == []
    out = tmp_path / "out.jpg"
    m.save(out)
    r = svk.read(out)
    assert r.present_fields() == []


# ---------------- diff ----------------
def test_diff_reports_disagreement(tmp_path):
    m = svk.read(
        _jpeg(
            tmp_path,
            exif=_exif(description=b"exif cap"),
            xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">xmp cap</rdf:li></rdf:Alt></dc:description>',
        )
    )
    diff = m.diff_standards()
    assert "description" in diff
    assert str(diff["description"]["exif"]) == "exif cap"
    assert str(diff["description"]["xmp"]) == "xmp cap"


def test_diff_empty_when_consistent(tmp_path):
    # After sync, standards agree -> no diff.
    m = svk.read(
        _jpeg(
            tmp_path,
            exif=_exif(description=b"exif cap"),
            xmp_body='<dc:description><rdf:Alt><rdf:li xml:lang="x-default">xmp cap</rdf:li></rdf:Alt></dc:description>',
        )
    )
    m.sync("exif", overwrite=True)
    m.save(tmp_path / "out.jpg")
    assert svk.read(tmp_path / "out.jpg").diff_standards() == {}
