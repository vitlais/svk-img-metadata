"""User-defined required-field validation.

No built-in profiles — you declare which fields must be present. A profile is a
one-liner: ``RequiredFields(["description", "creator", "copyright"])``. A field
may optionally be required in a specific standard, e.g.
``RequiredFields([("copyright", "xmp")])``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .errors import MetadataError, ValidationError
from .fields import FIELDS

if TYPE_CHECKING:
    from .model import ImageMetadata

_STANDARDS = ("exif", "iptc", "xmp")


def _is_present(value: Any) -> bool:
    """A value counts as present if it is non-None and not empty."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return bool(value) if hasattr(value, "__bool__") else True


@dataclass(frozen=True)
class _Requirement:
    field: str
    standard: str | None  # None = the merged canonical model


@dataclass
class ValidationResult:
    """Outcome of validating metadata against a schema."""

    ok: bool
    missing: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


class RequiredFields:
    """A schema requiring the given canonical fields to be present.

    Each entry is a field name, or a ``(field, standard)`` tuple to require it in
    a specific standard's own metadata. ``standard`` sets a default carrier for
    plain-string entries.
    """

    def __init__(self, fields: list, standard: str | None = None) -> None:
        self.requirements: list[_Requirement] = []
        for item in fields:
            name, std = (
                (item, standard) if isinstance(item, str) else (item[0], item[1])
            )
            if name not in FIELDS:
                raise MetadataError(f"unknown canonical field: {name!r}")
            if std is not None and std not in _STANDARDS:
                raise MetadataError(f"unknown standard: {std!r}")
            self.requirements.append(_Requirement(name, std))

    def validate(self, meta: ImageMetadata) -> ValidationResult:
        from .sync import standard_values

        cache: dict[str, dict] = {}
        missing: list[str] = []
        for req in self.requirements:
            if req.standard is None:
                present = _is_present(meta.get(req.field))
            else:
                if req.standard not in cache:
                    cache[req.standard] = standard_values(meta, req.standard)
                present = _is_present(cache[req.standard].get(req.field))
            if not present:
                label = (
                    req.field if req.standard is None else f"{req.field}@{req.standard}"
                )
                missing.append(label)
        return ValidationResult(ok=not missing, missing=missing)


def validate(
    meta: ImageMetadata, schema: RequiredFields, strict: bool = False
) -> ValidationResult:
    """Validate ``meta`` against ``schema``; raise ValidationError if ``strict``."""
    result = schema.validate(meta)
    if strict and not result.ok:
        raise ValidationError(f"missing required metadata: {', '.join(result.missing)}")
    return result
