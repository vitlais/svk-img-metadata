"""XMP decoding: an RDF/XML packet -> canonical model values.

The packet is attacker-controlled XML, so it is parsed exclusively with
``defusedxml`` (DTDs, external entities and entity-expansion bombs are rejected).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from defusedxml import ElementTree as DefusedET

from ..errors import MalformedImageError
from ..fields import FIELDS, ValueKind

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XML_NS = "http://www.w3.org/XML/1998/namespace"

_XPACKET_RE = re.compile(rb"<\?xpacket[^>]*\?>")


def decode(packet: bytes | str) -> tuple[str, dict[str, Any]]:
    """Decode an XMP packet into (packet text, canonical field values)."""
    if isinstance(packet, str):
        packet = packet.encode("utf-8")
    # Strip the xpacket processing instructions; the trailing one sits after the
    # root element and would otherwise be "junk after document element".
    cleaned = _XPACKET_RE.sub(b"", packet).strip()
    try:
        root = DefusedET.fromstring(cleaned)
    except Exception as exc:  # ParseError, EntitiesForbidden, etc.
        raise MalformedImageError(f"invalid XMP packet: {exc}") from exc

    descriptions = root.findall(f".//{{{RDF_NS}}}Description")
    canonical: dict[str, Any] = {}
    for spec in FIELDS.values():
        if spec.xmp is None:
            continue
        qname = f"{{{spec.xmp.uri}}}{spec.xmp.local}"
        value = _extract(descriptions, qname, spec.kind)
        if value is not None:
            canonical[spec.name] = value
    return packet.decode("utf-8", "replace"), canonical


def _extract(descriptions: list, qname: str, kind: ValueKind) -> Any:
    for desc in descriptions:
        # Attribute form (simple values serialised on rdf:Description).
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

    alt = element.find(f"{{{RDF_NS}}}Alt")
    if alt is None:
        text = (element.text or "").strip()
        return LangAlt(text) if text else None
    values: dict[str, str] = {}
    for li in alt.findall(f"{{{RDF_NS}}}li"):
        lang = li.get(f"{{{XML_NS}}}lang", "x-default")
        values[lang] = (li.text or "").strip()
    return LangAlt(values=values) if values else None


def _array(element) -> list[str] | None:
    for container in (f"{{{RDF_NS}}}Seq", f"{{{RDF_NS}}}Bag"):
        node = element.find(container)
        if node is not None:
            items = [(li.text or "").strip() for li in node.findall(f"{{{RDF_NS}}}li")]
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
