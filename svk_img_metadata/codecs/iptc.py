"""IPTC-IIM decoding: the binary datastream -> canonical model values."""

from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone
from typing import Any

from ..errors import MalformedImageError
from ..fields import FIELDS, ValueKind
from ..model import LangAlt, MetaDate
from ._common import decode_text

_TAG_MARKER = 0x1C


def decode(iim: bytes) -> tuple[dict[tuple[int, int], list[bytes]], dict[str, Any]]:
    """Decode an IPTC-IIM datastream into (raw datasets, canonical values)."""
    datasets = _parse(iim)
    canonical: dict[str, Any] = {}
    for spec in FIELDS.values():
        if not spec.iptc:
            continue
        if spec.kind is ValueKind.DATE:
            date_vals = datasets.get(spec.iptc[0])
            time_vals = datasets.get(spec.iptc[1]) if len(spec.iptc) > 1 else None
            value = _decode_date(date_vals, time_vals)
            if value is not None:
                canonical[spec.name] = value
            continue
        values = datasets.get(spec.iptc[0])
        if not values:
            continue
        if spec.kind in (ValueKind.TEXT_BAG, ValueKind.TEXT_SEQ):
            canonical[spec.name] = [decode_text(v) for v in values]
        elif spec.kind is ValueKind.LANG_ALT:
            canonical[spec.name] = LangAlt(decode_text(values[0]))
        else:
            canonical[spec.name] = decode_text(values[0])
    return datasets, canonical


def _parse(data: bytes) -> dict[tuple[int, int], list[bytes]]:
    """Parse the IIM stream into ``{(record, dataset): [raw values]}``."""
    out: dict[tuple[int, int], list[bytes]] = {}
    pos = 0
    n = len(data)
    while pos < n:
        if data[pos] != _TAG_MARKER:
            break  # padding or end of datasets
        if pos + 5 > n:
            raise MalformedImageError("truncated IPTC dataset header")
        record = data[pos + 1]
        dataset = data[pos + 2]
        length = struct.unpack(">H", data[pos + 3 : pos + 5])[0]
        pos += 5
        if length & 0x8000:  # extended length: low 15 bits = count of length bytes
            count = length & 0x7FFF
            if count == 0 or pos + count > n:
                raise MalformedImageError("invalid IPTC extended length")
            length = int.from_bytes(data[pos : pos + count], "big")
            pos += count
        if pos + length > n:
            raise MalformedImageError("IPTC dataset value exceeds available data")
        out.setdefault((record, dataset), []).append(data[pos : pos + length])
        pos += length
    return out


def _decode_date(
    date_vals: list[bytes] | None, time_vals: list[bytes] | None
) -> MetaDate | None:
    if not date_vals:
        return None
    date_str = decode_text(date_vals[0])
    if len(date_str) < 8 or not date_str[:8].isdigit():
        return None
    year, month, day = int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8])

    hour = minute = second = 0
    has_time = False
    tzinfo: timezone | None = None
    if time_vals:
        time_str = decode_text(time_vals[0])
        if len(time_str) >= 6 and time_str[:6].isdigit():
            hour, minute, second = (
                int(time_str[0:2]),
                int(time_str[2:4]),
                int(time_str[4:6]),
            )
            has_time = True
            if len(time_str) >= 11 and time_str[6] in "+-":
                try:
                    offset = timedelta(
                        hours=int(time_str[7:9]), minutes=int(time_str[9:11])
                    )
                    tzinfo = timezone(-offset if time_str[6] == "-" else offset)
                except ValueError:
                    tzinfo = None
    try:
        dt = datetime(year, month, day, hour, minute, second, tzinfo=tzinfo)
    except ValueError:
        return None
    return MetaDate(dt, has_time=has_time)
