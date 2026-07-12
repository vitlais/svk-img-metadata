"""Unified-model and typed-value tests."""

import pytest

from svk_img_metadata import GPSCoord, ImageMetadata, LangAlt


def test_canonical_attribute_roundtrip():
    m = ImageMetadata()
    assert m.description is None
    m.description = "a caption"
    assert m.description == "a caption"
    assert m.get("description") == "a caption"
    assert "description" in m.present_fields()


def test_set_none_clears_field():
    m = ImageMetadata()
    m.city = "Stockholm"
    m.city = None
    assert m.city is None
    assert "city" not in m.present_fields()


def test_unknown_field_rejected():
    m = ImageMetadata()
    with pytest.raises(KeyError):
        m.set("iso_speed", 400)
    with pytest.raises(KeyError):
        m.get("iso_speed")


def test_to_dict_only_present():
    m = ImageMetadata()
    m.creator = ["Jane Doe"]
    m.gps = GPSCoord(59.33, 18.06)
    assert set(m.to_dict()) == {"creator", "gps"}


def test_lang_alt_default_and_str():
    la = LangAlt("Sunset")
    assert str(la) == "Sunset"
    assert la == "Sunset"
    la.set("sv", "Solnedgång")
    assert la.get("sv") == "Solnedgång"
    assert la.default == "Sunset"
    assert la.to_dict() == {"x-default": "Sunset", "sv": "Solnedgång"}


def test_lang_alt_falls_back_to_first_when_no_default():
    la = LangAlt(values={"sv": "Solnedgång"})
    assert la.default == "Solnedgång"
