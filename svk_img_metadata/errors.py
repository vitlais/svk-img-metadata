"""Exception hierarchy for svk-img-metadata.

Every error this library raises for bad input derives from :class:`MetadataError`.
Parsing untrusted image bytes must never leak a raw ``struct.error``,
``IndexError``, ``RecursionError`` or similar to the caller — the container and
codec layers catch those and re-raise as one of the exceptions below.
"""

from __future__ import annotations


class MetadataError(Exception):
    """Base class for all errors raised by this library."""


class UnsupportedFormatError(MetadataError):
    """The image is not a container format this library can handle."""


class MalformedImageError(MetadataError):
    """The image (or an embedded metadata block) is structurally invalid.

    Raised for truncation, bad offsets/lengths, wrong endianness, oversized
    length fields, and any other corruption encountered while parsing
    attacker-controlled bytes.
    """


class ValidationError(MetadataError):
    """Required metadata was missing when validating against a schema.

    Note: :class:`~svk_img_metadata.validate.RequiredFields` validation
    normally returns a report object rather than raising; this exception is for
    callers that opt into strict/raising validation.
    """
