"""Directional synchronisation of shared fields between metadata standards.

Reads a chosen *source* standard's own values (from the raw per-standard view)
and copies them into the unified canonical model, restricted to fields that the
*target* standards can carry. Because :meth:`ImageMetadata.save` fans the
canonical values back out to each standard, a subsequent save propagates the
copied values into the targets' physical locations.

This is the pragmatic MWG-table-driven mapping the project opted for — no
IPTCDigest / precedence machinery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .codecs import exif as exif_codec
from .codecs import iptc as iptc_codec
from .errors import MetadataError
from .fields import FIELDS, Standard, has_slot

if TYPE_CHECKING:
    from .model import ImageMetadata

_STANDARDS = ("exif", "iptc", "xmp")


def standard_values(meta: ImageMetadata, standard: str) -> dict:
    """The canonical values a single standard currently holds in ``meta``."""
    if standard == "exif":
        return exif_codec.canonical_from_raw(meta.exif) if meta.exif else {}
    if standard == "iptc":
        return iptc_codec.canonical_from_datasets(meta.iptc) if meta.iptc else {}
    if standard == "xmp":
        return meta.xmp.canonical() if meta.xmp is not None else {}
    raise MetadataError(f"unknown standard: {standard!r}")


def sync(
    meta: ImageMetadata,
    source: str,
    targets: tuple[str, ...] | list[str] | None = None,
    fields: tuple[str, ...] | list[str] | None = None,
    overwrite: bool = False,
) -> list[str]:
    """Copy ``source`` standard's values into fields carried by ``targets``.

    Returns the list of canonical field names that were updated. See the module
    docstring for the model. ``overwrite=False`` only fills fields that are
    currently empty in the model.
    """
    if source not in _STANDARDS:
        raise MetadataError(f"unknown source standard: {source!r}")
    target_set = (
        tuple(targets)
        if targets is not None
        else tuple(s for s in _STANDARDS if s != source)
    )
    for name in target_set:
        if name not in _STANDARDS:
            raise MetadataError(f"unknown target standard: {name!r}")
    target_standards = [Standard(s) for s in target_set]

    field_filter = set(fields) if fields is not None else None
    source_values = standard_values(meta, source)

    updated: list[str] = []
    for name, value in source_values.items():
        if field_filter is not None and name not in field_filter:
            continue
        spec = FIELDS[name]
        if not any(has_slot(spec, std) for std in target_standards):
            continue
        if not overwrite and meta.get(name) is not None:
            continue
        meta.set(name, value)
        updated.append(name)
    return updated
