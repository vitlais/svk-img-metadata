"""EXIF decoding: piexif IFD dicts -> canonical model values."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import piexif

from ..errors import MalformedImageError
from ..fields import FIELDS, ValueKind
from ..model import GPSCoord, LangAlt, MetaDate
from ._common import decode_text

# GPS IFD tag ids (piexif.GPSIFD).
_GPS_LAT_REF, _GPS_LAT = 1, 2
_GPS_LON_REF, _GPS_LON = 3, 4
_GPS_ALT_REF, _GPS_ALT = 5, 6


def decode(blob: bytes) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode an EXIF blob into (raw piexif dict, canonical field values)."""
    # piexif.load treats a str as a file path (arbitrary-read risk); the
    # container layer always hands us bytes — enforce that invariant here.
    if not isinstance(blob, (bytes, bytearray)):
        raise MalformedImageError("EXIF blob must be bytes")
    try:
        raw = piexif.load(bytes(blob))
    except Exception as exc:  # piexif raises bare ValueError/struct.error/etc.
        raise MalformedImageError(f"invalid EXIF data: {exc}") from exc

    canonical: dict[str, Any] = {}
    for spec in FIELDS.values():
        if spec.name == "gps":
            gps = _decode_gps(raw.get("GPS") or {})
            if gps is not None:
                canonical["gps"] = gps
            continue
        if spec.exif is None:
            continue
        ifd, tag = spec.exif
        value = raw.get(ifd, {}).get(tag)
        if value is None:
            continue
        converted = _convert(spec.kind, value)
        if converted is not None:
            canonical[spec.name] = converted
    return raw, canonical


def _convert(kind: ValueKind, value: Any) -> Any:
    # A hostile TIFF can declare a text/date tag with a numeric type, so piexif
    # hands back an int/tuple instead of bytes. Such a type-confused tag is not
    # usable as text — skip it rather than crashing on ``.rstrip``.
    if not isinstance(value, (bytes, bytearray, str)):
        return None
    if kind is ValueKind.LANG_ALT:
        text = decode_text(value)
        return LangAlt(text) if text else None
    if kind is ValueKind.TEXT_SEQ:
        text = decode_text(value)
        return [text] if text else None
    if kind is ValueKind.DATE:
        return _decode_datetime(decode_text(value))
    return decode_text(value) or None


def _decode_datetime(text: str) -> MetaDate | None:
    text = text.strip()
    for fmt, has_time in (("%Y:%m:%d %H:%M:%S", True), ("%Y:%m:%d", False)):
        try:
            return MetaDate(
                datetime.strptime(text[: 19 if has_time else 10], fmt), has_time
            )
        except ValueError:
            continue
    return None


def _decode_gps(gps: dict[int, Any]) -> GPSCoord | None:
    lat, lat_ref = gps.get(_GPS_LAT), gps.get(_GPS_LAT_REF)
    lon, lon_ref = gps.get(_GPS_LON), gps.get(_GPS_LON_REF)
    if not (lat and lon and lat_ref and lon_ref):
        return None
    try:
        latitude = _dms_to_degrees(lat, lat_ref)
        longitude = _dms_to_degrees(lon, lon_ref)
        altitude = _decode_altitude(gps)
    except (TypeError, IndexError, ZeroDivisionError, AttributeError) as exc:
        raise MalformedImageError(f"invalid GPS coordinate: {exc}") from exc
    return GPSCoord(latitude, longitude, altitude)


def _dms_to_degrees(dms: Any, ref: bytes | str) -> float:
    degrees = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    value = degrees + minutes / 60 + seconds / 3600
    ref_str = ref.decode() if isinstance(ref, bytes) else ref
    if ref_str.upper() in ("S", "W"):
        value = -value
    return value


def _decode_altitude(gps: dict[int, Any]) -> float | None:
    alt = gps.get(_GPS_ALT)
    if alt is None:
        return None
    value = alt[0] / alt[1]
    if gps.get(_GPS_ALT_REF) == 1:  # 1 = below sea level
        value = -value
    return value
