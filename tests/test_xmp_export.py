"""M5: XMP export (string + sidecar) and custom namespaces."""

import pytest
from PIL import Image

import svk_img_metadata as svk
from svk_img_metadata.model import LangAlt

_ACME = "https://acme.example/ns/1.0/"


def _jpeg(tmp_path, name="src.jpg"):
    p = tmp_path / name
    Image.new("RGB", (4, 4), "teal").save(p, "JPEG")
    return p


def test_to_xmp_reflects_canonical(tmp_path):
    m = svk.read(_jpeg(tmp_path))
    m.description = LangAlt("Export me")
    m.keywords = ["x", "y"]
    xs = m.to_xmp()
    assert "Export me" in xs
    assert "x" in xs and "y" in xs
    assert xs.startswith("<?xpacket")


def test_custom_namespace_set_get_and_export(tmp_path):
    svk.register_namespace(_ACME, "acme")
    m = svk.read(_jpeg(tmp_path))
    m.xmp.set("acme:ReviewStatus", "approved")
    assert m.xmp.get("acme:ReviewStatus") == "approved"
    assert "approved" in m.to_xmp()
    # Resolvable by full URI form too.
    assert m.xmp.get(f"{{{_ACME}}}ReviewStatus") == "approved"


def test_custom_namespace_survives_save(tmp_path):
    svk.register_namespace(_ACME, "acme")
    m = svk.read(_jpeg(tmp_path))
    m.xmp.set("acme:ReviewStatus", "approved")
    m.description = "cap"
    out = tmp_path / "out.jpg"
    m.save(out)
    r = svk.read(out)
    assert r.xmp.get("acme:ReviewStatus") == "approved"
    assert str(r.description) == "cap"


def test_unknown_prefix_raises(tmp_path):
    m = svk.read(_jpeg(tmp_path))
    with pytest.raises(svk.MetadataError):
        m.xmp.set("nope:Foo", "bar")


def test_sidecar_naming_conventions(tmp_path):
    m = svk.read(_jpeg(tmp_path))
    m.description = "cap"
    base = m.write_xmp_sidecar()
    full = m.write_xmp_sidecar(naming="fullname")
    assert base.name == "src.xmp"
    assert full.name == "src.jpg.xmp"
    assert base.read_text().count("cap") >= 1


def test_read_sidecar_round_trip(tmp_path):
    svk.register_namespace(_ACME, "acme")
    m = svk.read(_jpeg(tmp_path))
    m.description = LangAlt("Sidecar cap")
    m.keywords = ["a", "b"]
    m.xmp.set("acme:ReviewStatus", "approved")
    sidecar = m.write_xmp_sidecar()

    back = svk.read_sidecar(sidecar)
    assert str(back.description) == "Sidecar cap"
    assert back.keywords == ["a", "b"]
    assert back.xmp.get("acme:ReviewStatus") == "approved"
    assert back.source_format is None


def test_sidecar_without_path_raises():
    m = svk.ImageMetadata()
    with pytest.raises(svk.MetadataError):
        m.write_xmp_sidecar()
