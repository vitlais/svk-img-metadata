"""Canonical field registry and the EXIF/IPTC/XMP mapping table.

This module is the **single source of truth** for how each logical metadata
field maps to its physical location in each standard. The read-merge,
write-fanout, and sync layers all consult :data:`FIELDS` — the mapping is never
duplicated elsewhere.

Only descriptive / rights / location fields are modelled; camera-technical tags
(exposure, lens, ISO…) are intentionally omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Standard(str, Enum):
    """A metadata standard / physical carrier."""

    EXIF = "exif"
    IPTC = "iptc"
    XMP = "xmp"


class ValueKind(str, Enum):
    """The logical shape of a field's value.

    Determines the Python type used in the model and the XMP RDF container used
    on serialisation:

    - ``TEXT`` -> plain string, XMP simple property
    - ``LANG_ALT`` -> :class:`~svk_img_metadata.model.LangAlt`, XMP ``rdf:Alt``
    - ``TEXT_SEQ`` -> ordered ``list[str]``, XMP ``rdf:Seq``
    - ``TEXT_BAG`` -> unordered ``list[str]``, XMP ``rdf:Bag``
    - ``DATE`` -> :class:`~svk_img_metadata.model.MetaDate`
    - ``INTEGER`` -> ``int``
    - ``GPS`` -> :class:`~svk_img_metadata.model.GPSCoord` (composite; handled
      specially by the EXIF codec via the GPS IFD)
    """

    TEXT = "text"
    LANG_ALT = "lang_alt"
    TEXT_SEQ = "text_seq"
    TEXT_BAG = "text_bag"
    DATE = "date"
    INTEGER = "integer"
    GPS = "gps"


# XMP namespace URIs. Identity is the URI; prefixes are only hints.
NAMESPACES: dict[str, str] = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "xmpRights": "http://ns.adobe.com/xap/1.0/rights/",
    "Iptc4xmpCore": "http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/",
    "Iptc4xmpExt": "http://iptc.org/std/Iptc4xmpExt/2008-02-29/",
}


@dataclass(frozen=True)
class XmpProp:
    """An XMP property location: a namespace prefix hint, local name, and URI."""

    prefix: str
    local: str

    @property
    def uri(self) -> str:
        return NAMESPACES[self.prefix]


@dataclass(frozen=True)
class FieldSpec:
    """How one canonical field maps into each standard.

    Attributes:
        name: canonical snake_case field name (the key in :data:`FIELDS`).
        kind: value shape (see :class:`ValueKind`).
        exif: ``(ifd, tag)`` where ``ifd`` is one of ``"0th"``, ``"Exif"``,
            ``"GPS"`` (piexif IFD groups), or ``None`` if EXIF has no slot.
        iptc: tuple of ``(record, dataset)`` IIM locations — usually one, but
            e.g. ``date_created`` spans the date and time datasets. Empty if
            IPTC-IIM has no slot.
        xmp: XMP property location, or ``None``.
        composite: True for fields the codecs assemble from several physical
            tags (currently only ``gps`` via the EXIF GPS IFD).
    """

    name: str
    kind: ValueKind
    exif: tuple[str, int] | None = None
    iptc: tuple[tuple[int, int], ...] = ()
    xmp: XmpProp | None = None
    composite: bool = False


def _p(prefix: str, local: str) -> XmpProp:
    return XmpProp(prefix, local)


# EXIF tag ids (kept inline for readability; piexif exposes the same ids).
_IMAGE_DESCRIPTION = 270  # 0x010E, 0th IFD
_ARTIST = 315  # 0x013B, 0th IFD
_COPYRIGHT = 33432  # 0x8298, 0th IFD
_DATE_TIME_ORIGINAL = 36867  # 0x9003, Exif IFD


#: Canonical field registry. See module docstring.
FIELDS: dict[str, FieldSpec] = {
    "title": FieldSpec(
        "title", ValueKind.LANG_ALT, iptc=((2, 5),), xmp=_p("dc", "title")
    ),
    "headline": FieldSpec(
        "headline", ValueKind.TEXT, iptc=((2, 105),), xmp=_p("photoshop", "Headline")
    ),
    "description": FieldSpec(
        "description",
        ValueKind.LANG_ALT,
        exif=("0th", _IMAGE_DESCRIPTION),
        iptc=((2, 120),),
        xmp=_p("dc", "description"),
    ),
    "creator": FieldSpec(
        "creator",
        ValueKind.TEXT_SEQ,
        exif=("0th", _ARTIST),
        iptc=((2, 80),),
        xmp=_p("dc", "creator"),
    ),
    "creator_title": FieldSpec(
        "creator_title",
        ValueKind.TEXT,
        iptc=((2, 85),),
        xmp=_p("photoshop", "AuthorsPosition"),
    ),
    "copyright": FieldSpec(
        "copyright",
        ValueKind.LANG_ALT,
        exif=("0th", _COPYRIGHT),
        iptc=((2, 116),),
        xmp=_p("dc", "rights"),
    ),
    "rights_usage": FieldSpec(
        "rights_usage", ValueKind.LANG_ALT, xmp=_p("xmpRights", "UsageTerms")
    ),
    "credit": FieldSpec(
        "credit", ValueKind.TEXT, iptc=((2, 110),), xmp=_p("photoshop", "Credit")
    ),
    "source": FieldSpec(
        "source", ValueKind.TEXT, iptc=((2, 115),), xmp=_p("photoshop", "Source")
    ),
    "keywords": FieldSpec(
        "keywords", ValueKind.TEXT_BAG, iptc=((2, 25),), xmp=_p("dc", "subject")
    ),
    "date_created": FieldSpec(
        "date_created",
        ValueKind.DATE,
        exif=("Exif", _DATE_TIME_ORIGINAL),
        iptc=((2, 55), (2, 60)),
        xmp=_p("photoshop", "DateCreated"),
    ),
    "instructions": FieldSpec(
        "instructions",
        ValueKind.TEXT,
        iptc=((2, 40),),
        xmp=_p("photoshop", "Instructions"),
    ),
    # IPTC 2:103 Original Transmission Reference <-> XMP photoshop:TransmissionReference.
    "job_id": FieldSpec(
        "job_id",
        ValueKind.TEXT,
        iptc=((2, 103),),
        xmp=_p("photoshop", "TransmissionReference"),
    ),
    "sublocation": FieldSpec(
        "sublocation",
        ValueKind.TEXT,
        iptc=((2, 92),),
        xmp=_p("Iptc4xmpCore", "Location"),
    ),
    "city": FieldSpec(
        "city", ValueKind.TEXT, iptc=((2, 90),), xmp=_p("photoshop", "City")
    ),
    "state": FieldSpec(
        "state", ValueKind.TEXT, iptc=((2, 95),), xmp=_p("photoshop", "State")
    ),
    "country": FieldSpec(
        "country", ValueKind.TEXT, iptc=((2, 101),), xmp=_p("photoshop", "Country")
    ),
    "country_code": FieldSpec(
        "country_code",
        ValueKind.TEXT,
        iptc=((2, 100),),
        xmp=_p("Iptc4xmpCore", "CountryCode"),
    ),
    # GPS is composite: assembled from the EXIF GPS IFD (lat/lon/refs) by the codec.
    "gps": FieldSpec("gps", ValueKind.GPS, composite=True),
    "rating": FieldSpec("rating", ValueKind.INTEGER, xmp=_p("xmp", "Rating")),
    "label": FieldSpec("label", ValueKind.TEXT, xmp=_p("xmp", "Label")),
}


def fields_for(standard: Standard) -> list[FieldSpec]:
    """Return the field specs that have a physical slot in ``standard``."""
    result = []
    for spec in FIELDS.values():
        if standard is Standard.EXIF and (spec.exif is not None or spec.composite):
            result.append(spec)
        elif standard is Standard.IPTC and spec.iptc:
            result.append(spec)
        elif standard is Standard.XMP and spec.xmp is not None:
            result.append(spec)
    return result
