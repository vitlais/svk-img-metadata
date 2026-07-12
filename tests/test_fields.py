"""Integrity tests for the canonical field registry / mapping table."""

from svk_img_metadata.fields import FIELDS, NAMESPACES, Standard, ValueKind, fields_for


def test_every_xmp_prefix_is_registered():
    for spec in FIELDS.values():
        if spec.xmp is not None:
            assert spec.xmp.prefix in NAMESPACES
            assert spec.xmp.uri == NAMESPACES[spec.xmp.prefix]


def test_field_names_match_keys():
    for name, spec in FIELDS.items():
        assert spec.name == name


def test_every_field_maps_somewhere():
    # No field should be defined without at least one physical location
    # (gps is composite via the EXIF GPS IFD).
    for spec in FIELDS.values():
        assert (
            spec.exif is not None or spec.iptc or spec.xmp is not None or spec.composite
        )


def test_fields_for_standard():
    xmp_fields = {s.name for s in fields_for(Standard.XMP)}
    assert {"description", "creator", "keywords", "rating"} <= xmp_fields
    iptc_fields = {s.name for s in fields_for(Standard.IPTC)}
    assert "rating" not in iptc_fields  # rating is XMP-only
    assert "keywords" in iptc_fields


def test_date_created_spans_two_iptc_datasets():
    assert FIELDS["date_created"].iptc == ((2, 55), (2, 60))
    assert FIELDS["date_created"].kind is ValueKind.DATE
