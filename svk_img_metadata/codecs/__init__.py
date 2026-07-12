"""Per-standard encoders/decoders between raw blobs and the canonical model.

Each module exposes ``decode(blob) -> (raw_view, canonical_values)``. Encoders
(the reverse direction) are added in the write milestone.
"""
