"""Small shared helpers for the codecs."""

from __future__ import annotations


def decode_text(value: bytes | str) -> str:
    """Decode a metadata byte string to ``str``.

    EXIF/IPTC text is nominally ASCII/Latin-1 but is frequently UTF-8 in the
    wild; try UTF-8 first and fall back to Latin-1 (which never fails).
    """
    if isinstance(value, str):
        return value.rstrip("\x00")
    value = value.rstrip(b"\x00")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return value.decode("latin-1")
