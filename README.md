# svk-img-metadata

[![PyPI](https://img.shields.io/pypi/v/svk-img-metadata.svg)](https://pypi.org/project/svk-img-metadata/)
[![Tests](https://github.com/vitlais/svk-img-metadata/actions/workflows/test.yml/badge.svg)](https://github.com/vitlais/svk-img-metadata/actions/workflows/test.yml)
[![Changelog](https://img.shields.io/github/v/release/vitlais/svk-img-metadata?include_prereleases&label=changelog)](https://github.com/vitlais/svk-img-metadata/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/vitlais/svk-img-metadata/blob/main/LICENSE)

Read, write, and synchronise descriptive image metadata — **EXIF, IPTC-IIM, and XMP** — across **JPEG, PNG, and TIFF**, in mostly-pure Python (`Pillow`, `piexif`, `defusedxml`; no native `exiv2`/`libheif`, no ExifTool).

It focuses on the descriptive / rights / location fields you actually curate (caption, creator, copyright, keywords, location, dates, rating…), not camera-technical tags. A single unified model maps each logical field to its correct home in all three standards, so you can read from wherever the value lives and write it back everywhere it belongs.

## Installation

```bash
pip install svk-img-metadata
```

Requires Python 3.10+.

## Usage

### Read

```python
import svk_img_metadata as svk

meta = svk.read("photo.jpg")

print(meta.description)        # a caption (as a LangAlt; str() gives x-default)
print(meta.creator)            # ["Jane Doe"]
print(meta.keywords)           # ["sky", "sea"]
print(meta.city, meta.country)
print(meta.gps)                # GPSCoord(latitude=59.33, longitude=18.06, altitude=None)
print(meta.present_fields())   # which canonical fields are set
```

Values are merged across the three standards with **XMP > IPTC > EXIF** precedence. The raw per-standard views are available too (`meta.exif`, `meta.iptc`, `meta.xmp`).

### Write

```python
from svk_img_metadata import read
from svk_img_metadata.model import LangAlt, MetaDate, GPSCoord
from datetime import datetime, timezone

meta = read("photo.jpg")
meta.description = LangAlt("Sunset over the archipelago")
meta.creator = ["Jane Doe"]
meta.keywords = ["sunset", "sea"]
meta.copyright = "© 2026 Jane Doe"
meta.date_created = MetaDate(datetime(2026, 7, 12, 20, 30, tzinfo=timezone.utc))
meta.gps = GPSCoord(59.33, 18.06)

meta.save("photo-tagged.jpg")   # or meta.save() to overwrite in place
```

Canonical fields fan out to every standard that carries them. Pixel data and any metadata the library does not model (unknown EXIF tags, custom XMP namespaces, other Photoshop resources) are preserved. Restrict the carriers with `meta.save(path, standards=("xmp",))`.

Canonical fields: `title`, `headline`, `description`, `creator`, `creator_title`, `copyright`, `rights_usage`, `credit`, `source`, `keywords`, `date_created`, `instructions`, `job_id`, `sublocation`, `city`, `state`, `country`, `country_code`, `gps`, `rating`, `label`.

### Synchronise between standards

Copy one standard's values into the fields the others carry — e.g. populate IPTC/XMP from a camera's EXIF:

```python
meta = read("from-camera.jpg")
meta.sync("exif", targets=["iptc", "xmp"])   # fill empty IPTC/XMP fields from EXIF
meta.sync("exif", overwrite=True)            # or force EXIF to win over the merge precedence
meta.save()
```

See where the standards currently disagree:

```python
meta.diff_standards()
# {"description": {"exif": LangAlt('old caption'), "xmp": LangAlt('new caption')}}
```

### Export XMP (string or sidecar)

```python
xml = meta.to_xmp()                              # standalone XMP packet as a string
meta.write_xmp_sidecar()                         # -> photo.xmp   (basename convention)
meta.write_xmp_sidecar(naming="fullname")        # -> photo.jpg.xmp

sidecar = svk.read_sidecar("photo.xmp")          # read a .xmp back into the model
```

### Custom XMP namespaces

```python
svk.register_namespace("https://example.com/ns/1.0/", "acme")
meta.xmp.set("acme:ReviewStatus", "approved")
meta.xmp.get("acme:ReviewStatus")                # "approved"
meta.save()                                      # custom property is round-tripped
```

### Validate required metadata

```python
schema = svk.RequiredFields(["description", "creator", "copyright"])
result = meta.validate(schema)
if not result:
    print("missing:", result.missing)           # e.g. ["copyright"]

# require a field in a specific standard, or raise on failure:
svk.RequiredFields([("copyright", "xmp")])
meta.validate(schema, strict=True)               # raises ValidationError if incomplete
```

### Strip metadata (privacy)

```python
meta.strip(fields=["gps"])   # remove location only
meta.strip()                 # remove all modelled fields
meta.save("clean.jpg")
```

## Format support

| Format | Read | Write |
|--------|------|-------|
| JPEG   | ✅   | ✅    |
| PNG    | ✅   | ✅ (EXIF + XMP; PNG has no standard IPTC slot) |
| TIFF   | ✅   | not yet |
| HEIC   | —    | —     |

Malformed or hostile input always raises a clean `svk_img_metadata.MetadataError` (never an unhandled crash); XMP is parsed with `defusedxml` to block XXE and entity-expansion attacks.

## Development

Uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev      # install project + dev deps
uv run pytest            # run the test suite
uv run ruff check .      # lint
```
