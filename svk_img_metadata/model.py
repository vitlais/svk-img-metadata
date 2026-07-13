"""The unified metadata model.

:class:`ImageMetadata` is what :func:`svk_img_metadata.read` returns. It exposes
both **raw per-standard views** (``.exif`` / ``.iptc`` / ``.xmp``) so nothing is
hidden and unknown data round-trips, and **canonical accessors** for the
descriptive/rights/location fields defined in :mod:`svk_img_metadata.fields`.

The canonical accessors are generated from :data:`~svk_img_metadata.fields.FIELDS`
so the field set stays defined in exactly one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import MetadataError
from .fields import FIELDS

__all__ = ["ImageMetadata", "LangAlt", "MetaDate", "GPSCoord"]


class LangAlt:
    """A language-alternatives value (XMP ``rdf:Alt``), e.g. title/description.

    A plain string maps to the ``x-default`` alternative. Iterating or comparing
    against a ``str`` uses the default language.
    """

    def __init__(
        self, default: str | None = None, *, values: dict[str, str] | None = None
    ) -> None:
        self._values: dict[str, str] = {}
        if values:
            self._values.update(values)
        if default is not None:
            self._values["x-default"] = default

    @property
    def default(self) -> str | None:
        if "x-default" in self._values:
            return self._values["x-default"]
        return next(iter(self._values.values()), None)

    def get(self, lang: str) -> str | None:
        return self._values.get(lang)

    def set(self, lang: str, text: str) -> None:
        self._values[lang] = text

    def to_dict(self) -> dict[str, str]:
        return dict(self._values)

    def __bool__(self) -> bool:
        return bool(self._values)

    def __str__(self) -> str:
        return self.default or ""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LangAlt):
            return self._values == other._values
        if isinstance(other, str):
            return self.default == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"LangAlt({self._values!r})"


@dataclass
class MetaDate:
    """A date/time value that normalises the EXIF/IPTC/XMP representations.

    ``value`` may be timezone-aware or naive. ``has_time`` distinguishes a
    date-only value (IPTC allows date without time) from a full timestamp.
    """

    value: datetime
    has_time: bool = True

    def __str__(self) -> str:
        if self.has_time:
            return self.value.isoformat()
        return self.value.date().isoformat()


@dataclass
class GPSCoord:
    """A decimal WGS-84 coordinate, optionally with altitude in metres."""

    latitude: float
    longitude: float
    altitude: float | None = None


@dataclass
class ImageMetadata:
    """Container for one image's metadata.

    Canonical fields (``description``, ``creator``, …) are available as
    attributes generated from :data:`~svk_img_metadata.fields.FIELDS`; a value of
    ``None`` means "not present". Use :meth:`get` / :meth:`set` for programmatic
    access by field name.
    """

    source_format: str | None = None
    #: Raw per-standard views, populated by the codecs. ``exif``/``iptc`` are
    #: the raw decoded structures; ``xmp`` is an ``XmpDocument``.
    exif: dict[str, Any] = field(default_factory=dict)
    iptc: dict[str, Any] = field(default_factory=dict)
    xmp: Any = None
    _values: dict[str, Any] = field(default_factory=dict, repr=False)
    #: Original container bytes / path, retained so save() can rewrite the file
    #: while preserving pixel data and unmodelled segments.
    _source: bytes | None = field(default=None, repr=False)
    _source_path: Any = field(default=None, repr=False)

    def get(self, name: str) -> Any:
        """Return the canonical field ``name`` (``None`` if absent)."""
        if name not in FIELDS:
            raise KeyError(f"unknown canonical field: {name!r}")
        return self._values.get(name)

    def set(self, name: str, value: Any) -> None:
        """Set the canonical field ``name`` (``None`` clears it)."""
        if name not in FIELDS:
            raise KeyError(f"unknown canonical field: {name!r}")
        if value is None:
            self._values.pop(name, None)
        else:
            self._values[name] = value

    def present_fields(self) -> list[str]:
        """Canonical field names that currently have a value."""
        return [name for name in FIELDS if name in self._values]

    def to_dict(self) -> dict[str, Any]:
        """A plain-dict view of the canonical fields that are set."""
        return {name: self._values[name] for name in FIELDS if name in self._values}

    def save(
        self, path=None, standards: tuple[str, ...] = ("exif", "iptc", "xmp")
    ) -> None:
        """Write the metadata back into the image, preserving pixels/unknowns.

        ``path`` defaults to the file this metadata was read from. ``standards``
        selects which carriers to (re)write; canonical fields fan out to each.
        Requires metadata read from a source image.
        """
        from .containers import save_image

        save_image(self, path, standards)

    def sync(
        self,
        source: str,
        targets: tuple[str, ...] | list[str] | None = None,
        fields: tuple[str, ...] | list[str] | None = None,
        overwrite: bool = False,
    ) -> list[str]:
        """Copy the ``source`` standard's values into fields the targets carry.

        E.g. ``meta.sync("exif", ["iptc", "xmp"])`` populates the IPTC/XMP
        fields from EXIF. Updates the canonical model in place (a later
        :meth:`save` writes them out); returns the field names changed. See
        :mod:`svk_img_metadata.sync`.
        """
        from .sync import sync as _sync

        return _sync(self, source, targets, fields, overwrite)

    def to_xmp(self) -> str:
        """Serialise the current metadata as a standalone XMP packet string.

        Reflects canonical edits and preserves any unknown/custom XMP
        properties from the source.
        """
        from .codecs import xmp as xmp_codec
        from .codecs.xmp import XmpDocument

        base = self.xmp if isinstance(self.xmp, XmpDocument) else None
        return xmp_codec.encode(self.to_dict(), base).decode("utf-8")

    def write_xmp_sidecar(self, image_path=None, naming: str = "basename") -> Path:
        """Write an XMP sidecar file and return its path.

        ``naming``: ``"basename"`` → ``IMG.xmp`` (replace extension);
        ``"fullname"`` → ``IMG.jpg.xmp`` (append). If ``image_path`` is an
        explicit ``.xmp`` path it is used verbatim; otherwise it defaults to the
        source image's path.
        """
        base = image_path if image_path is not None else self._source_path
        if base is None:
            raise MetadataError("no path for sidecar; pass image_path")
        p = Path(base)
        if p.suffix.lower() == ".xmp":
            sidecar = p
        elif naming == "fullname":
            sidecar = p.with_name(p.name + ".xmp")
        else:
            sidecar = p.with_suffix(".xmp")
        sidecar.write_text(self.to_xmp(), encoding="utf-8")
        return sidecar


def _make_property(name: str) -> property:
    def getter(self: ImageMetadata) -> Any:
        return self._values.get(name)

    def setter(self: ImageMetadata, value: Any) -> None:
        self.set(name, value)

    def deleter(self: ImageMetadata) -> None:
        self._values.pop(name, None)

    getter.__name__ = name
    return property(getter, setter, deleter, doc=f"Canonical field {name!r}.")


for _name in FIELDS:
    setattr(ImageMetadata, _name, _make_property(_name))
del _name
