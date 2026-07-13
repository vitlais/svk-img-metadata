"""XMP: parse/edit/serialise an RDF/XML packet <-> canonical model values.

Untrusted packets are parsed exclusively with ``defusedxml`` (DTDs, external
entities and entity-expansion bombs are rejected). Serialisation of an
already-parsed or freshly-built tree uses stdlib ElementTree, which is safe.

:class:`XmpDocument` owns the parsed tree so edits preserve properties and
namespaces this library does not model (round-trip preservation).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

from defusedxml import ElementTree as DefusedET

from ..errors import MalformedImageError, MetadataError
from ..fields import FIELDS, NAMESPACES, ValueKind

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML_NS = "http://www.w3.org/XML/1998/namespace"
X_NS = "adobe:ns:meta/"

_XPACKET_RE = re.compile(rb"<\?xpacket[^>]*\?>")

# User-registered custom namespaces (prefix -> uri). Populated only via the
# explicit, trusted register_namespace() API — never from untrusted packets.
_CUSTOM_NS: dict[str, str] = {}

# Keep our own (trusted, static) prefixes stable on serialisation. Namespaces we
# do not model are round-tripped by ElementTree as ns0/ns1/… — their URIs and
# values are preserved (XMP identity is by URI), which is all we promise. We
# deliberately do NOT register prefixes parsed from untrusted packets: that
# would let a hostile file mutate process-global ElementTree state.
ET.register_namespace("rdf", RDF_NS)
ET.register_namespace("x", X_NS)
for _prefix, _uri in NAMESPACES.items():
    ET.register_namespace(_prefix, _uri)


def register_namespace(uri: str, prefix: str) -> None:
    """Register a custom XMP namespace so ``prefix:local`` names resolve and
    serialise with a stable prefix. Trusted, caller-driven only."""
    _CUSTOM_NS[prefix] = uri
    ET.register_namespace(prefix, uri)


def _resolve(name: str) -> tuple[str, str]:
    """Resolve ``'{uri}local'`` or ``'prefix:local'`` to ``(uri, local)``."""
    if name.startswith("{") and "}" in name:
        uri, local = name[1:].split("}", 1)
        return uri, local
    if ":" in name:
        prefix, local = name.split(":", 1)
        uri = NAMESPACES.get(prefix) or _CUSTOM_NS.get(prefix)
        if uri is None:
            raise MetadataError(
                f"unknown XMP namespace prefix {prefix!r}; register_namespace() first"
            )
        return uri, local
    raise MetadataError(
        f"XMP name must be 'prefix:local' or '{{uri}}local', got {name!r}"
    )


def _q(uri: str, local: str) -> str:
    return f"{{{uri}}}{local}"


class XmpDocument:
    """An editable XMP packet backed by an ElementTree."""

    def __init__(self, root: ET.Element) -> None:
        self._root = root

    # -- construction -------------------------------------------------------
    @classmethod
    def parse(cls, packet: bytes | str) -> XmpDocument:
        if isinstance(packet, str):
            packet = packet.encode("utf-8")
        cleaned = _XPACKET_RE.sub(b"", packet).strip()
        try:
            root = DefusedET.fromstring(cleaned)
        except Exception as exc:  # ParseError, EntitiesForbidden, etc.
            raise MalformedImageError(f"invalid XMP packet: {exc}") from exc
        return cls(root)

    @classmethod
    def empty(cls) -> XmpDocument:
        root = ET.Element(_q(X_NS, "xmpmeta"))
        rdf = ET.SubElement(root, _q(RDF_NS, "RDF"))
        desc = ET.SubElement(rdf, _q(RDF_NS, "Description"))
        desc.set(_q(RDF_NS, "about"), "")
        return cls(root)

    # -- structure ----------------------------------------------------------
    def _descriptions(self) -> list[ET.Element]:
        return self._root.findall(f".//{_q(RDF_NS, 'Description')}")

    def _primary_description(self) -> ET.Element:
        descriptions = self._descriptions()
        if descriptions:
            return descriptions[0]
        rdf = self._root.find(_q(RDF_NS, "RDF"))
        if rdf is None:
            rdf = ET.SubElement(self._root, _q(RDF_NS, "RDF"))
        desc = ET.SubElement(rdf, _q(RDF_NS, "Description"))
        desc.set(_q(RDF_NS, "about"), "")
        return desc

    # -- reading ------------------------------------------------------------
    def canonical(self) -> dict[str, Any]:
        descriptions = self._descriptions()
        out: dict[str, Any] = {}
        for spec in FIELDS.values():
            if spec.xmp is None:
                continue
            value = _extract(descriptions, _q(spec.xmp.uri, spec.xmp.local), spec.kind)
            if value is not None:
                out[spec.name] = value
        return out

    # -- writing ------------------------------------------------------------
    def set_field(self, spec, value: Any) -> None:
        """Set (or, if ``value`` is None, remove) a mapped canonical field."""
        qname = _q(spec.xmp.uri, spec.xmp.local)
        # Remove any existing representation (element or attribute form).
        for desc in self._descriptions():
            for existing in desc.findall(qname):
                desc.remove(existing)
            desc.attrib.pop(qname, None)
        if value is None:
            return
        desc = self._primary_description()
        element = ET.SubElement(desc, qname)
        _serialise_value(element, spec.kind, value)

    # -- arbitrary / custom properties -------------------------------------
    def get(self, name: str) -> str | None:
        """Get a simple text property by ``'prefix:local'`` or ``'{uri}local'``."""
        uri, local = _resolve(name)
        qname = _q(uri, local)
        for desc in self._descriptions():
            if qname in desc.attrib:
                return desc.attrib[qname]
            element = desc.find(qname)
            if element is not None:
                return (element.text or "").strip()
        return None

    def set(self, name: str, value: Any) -> None:
        """Set (or remove, if ``value`` is None) a simple text property.

        Works for custom namespaces registered via ``register_namespace``.
        """
        uri, local = _resolve(name)
        qname = _q(uri, local)
        for desc in self._descriptions():
            for existing in desc.findall(qname):
                desc.remove(existing)
            desc.attrib.pop(qname, None)
        if value is None:
            return
        element = ET.SubElement(self._primary_description(), qname)
        element.text = str(value)

    def to_bytes(self) -> bytes:
        body = ET.tostring(self._root, encoding="utf-8")
        return (
            b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            + body
            + b'\n<?xpacket end="w"?>'
        )

    def to_string(self) -> str:
        return self.to_bytes().decode("utf-8")


def decode(packet: bytes | str) -> tuple[XmpDocument, dict[str, Any]]:
    """Decode an XMP packet into (document, canonical field values)."""
    doc = XmpDocument.parse(packet)
    return doc, doc.canonical()


def encode(canonical: dict[str, Any], base: XmpDocument | None) -> bytes:
    """Serialise ``canonical`` into an XMP packet, preserving unknown data.

    Every XMP-mapped field is made to reflect ``canonical`` exactly (present
    fields set, absent fields removed); properties this library does not model
    are left untouched.
    """
    doc = base if base is not None else XmpDocument.empty()
    for spec in FIELDS.values():
        if spec.xmp is None:
            continue
        doc.set_field(spec, canonical.get(spec.name))
    return doc.to_bytes()


# --------------------------------------------------------------------------
# value <-> element helpers
# --------------------------------------------------------------------------
def _serialise_value(element: ET.Element, kind: ValueKind, value: Any) -> None:
    from ..model import GPSCoord, LangAlt, MetaDate

    if kind is ValueKind.LANG_ALT:
        alt = ET.SubElement(element, _q(RDF_NS, "Alt"))
        items = (
            value.to_dict() if isinstance(value, LangAlt) else {"x-default": str(value)}
        )
        for lang, text in items.items():
            li = ET.SubElement(alt, _q(RDF_NS, "li"))
            li.set(_q(XML_NS, "lang"), lang)
            li.text = text
    elif kind in (ValueKind.TEXT_SEQ, ValueKind.TEXT_BAG):
        container = "Seq" if kind is ValueKind.TEXT_SEQ else "Bag"
        node = ET.SubElement(element, _q(RDF_NS, container))
        for item in value:
            li = ET.SubElement(node, _q(RDF_NS, "li"))
            li.text = str(item)
    elif kind is ValueKind.DATE:
        element.text = (
            value.value.isoformat() if isinstance(value, MetaDate) else str(value)
        )
    elif kind is ValueKind.GPS:
        # No XMP mapping for gps in v1; guard so nothing silently misfires.
        if isinstance(value, GPSCoord):
            element.text = f"{value.latitude},{value.longitude}"
    else:
        element.text = str(value)


def _extract(descriptions: list, qname: str, kind: ValueKind) -> Any:
    for desc in descriptions:
        if qname in desc.attrib:
            simple = _simple(kind, desc.attrib[qname])
            if simple is not None:
                return simple
        element = desc.find(qname)
        if element is None:
            continue
        if kind is ValueKind.LANG_ALT:
            return _lang_alt(element)
        if kind in (ValueKind.TEXT_SEQ, ValueKind.TEXT_BAG):
            return _array(element)
        text = (element.text or "").strip()
        return _simple(kind, text) if text else None
    return None


def _lang_alt(element) -> Any:
    from ..model import LangAlt

    alt = element.find(_q(RDF_NS, "Alt"))
    if alt is None:
        text = (element.text or "").strip()
        return LangAlt(text) if text else None
    values: dict[str, str] = {}
    for li in alt.findall(_q(RDF_NS, "li")):
        lang = li.get(_q(XML_NS, "lang"), "x-default")
        values[lang] = (li.text or "").strip()
    return LangAlt(values=values) if values else None


def _array(element) -> list[str] | None:
    for container in ("Seq", "Bag"):
        node = element.find(_q(RDF_NS, container))
        if node is not None:
            items = [(li.text or "").strip() for li in node.findall(_q(RDF_NS, "li"))]
            items = [i for i in items if i]
            return items or None
    text = (element.text or "").strip()
    return [text] if text else None


def _simple(kind: ValueKind, text: str) -> Any:
    from ..model import LangAlt

    text = text.strip()
    if not text:
        return None
    if kind is ValueKind.INTEGER:
        try:
            return int(text)
        except ValueError:
            return None
    if kind is ValueKind.DATE:
        return _decode_date(text)
    if kind is ValueKind.LANG_ALT:
        return LangAlt(text)
    return text


def _decode_date(text: str):
    from ..model import MetaDate

    normalised = text.strip().replace("Z", "+00:00")
    try:
        return MetaDate(datetime.fromisoformat(normalised), has_time="T" in text)
    except ValueError:
        for fmt, has_time in (("%Y-%m-%d", False), ("%Y", False)):
            try:
                return MetaDate(datetime.strptime(text.strip(), fmt), has_time)
            except ValueError:
                continue
    return None
