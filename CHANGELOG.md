# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-13

First release. A mostly-pure-Python library to read, write, and synchronise
descriptive image metadata (EXIF, IPTC-IIM, XMP) across JPEG, PNG, and TIFF,
using permissive dependencies only (`Pillow`, `piexif`, `defusedxml`).

### Added

- **Unified model** — `read()` merges each logical field across the standards
  with XMP > IPTC > EXIF precedence into an `ImageMetadata` with canonical
  accessors, alongside the raw per-standard views. Typed values `LangAlt`,
  `MetaDate`, and `GPSCoord`. `fields.py` maps every canonical field to its
  EXIF/IPTC/XMP location as the single source of truth.
- **JPEG** — read and embedded write, preserving pixels and unmodelled metadata
  (unknown EXIF tags, custom XMP namespaces, other Photoshop IRB resources).
- **PNG** — read and embedded write (EXIF via `eXIf`, XMP via `iTXt`); PNG has
  no standard IPTC slot.
- **TIFF** — read (EXIF via piexif, XMP tag 700, IPTC tag 33723); metadata
  writing via XMP sidecar (embedding intentionally unsupported).
- **Sync** — `ImageMetadata.sync()` copies a source standard's values into the
  fields the target standards carry, with `overwrite` and field filters.
- **XMP export** — `to_xmp()` (string), `write_xmp_sidecar()` (basename and
  fullname conventions), and `read_sidecar()`.
- **Custom XMP namespaces** — `register_namespace()` plus `XmpDocument.get`/`set`
  for arbitrary properties by `prefix:local` or `{uri}local`.
- **Validation** — user-defined `RequiredFields` schemas (per-field or
  per-standard) returning a `ValidationResult`, with an optional strict mode.
- **Strip** — `strip()` removes modelled fields for privacy.
- **Diff** — `diff_standards()` reports fields whose value disagrees across
  standards.
- **Safety** — untrusted images are parsed defensively: XMP via `defusedxml`
  (blocks XXE and billion-laughs), bounds-checked marker/chunk/IIM parsing, and
  a clean `MetadataError` on any malformed input.

Tested on Python 3.10–3.14.

[Unreleased]: https://github.com/vitlais/svk-img-metadata/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/vitlais/svk-img-metadata/releases/tag/v0.1.0
