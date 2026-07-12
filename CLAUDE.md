# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

The library reads/writes descriptive image metadata (EXIF, IPTC-IIM, XMP) for JPEG/TIFF/PNG. It is **under active construction** against the milestone plan (M0 scaffold done; JPEG read/write, sync, XMP export, and validation follow). Design decisions: mostly-pure-Python with permissive deps (`Pillow`, `piexif`, `defusedxml`) — no GPL/native `exiv2`/`libheif`; HEIC and camera-technical tags are deferred/out of scope.

Key modules: `fields.py` is the **single source of truth** mapping each canonical field to its EXIF/IPTC/XMP location — read-merge, write-fanout, and sync all consult it, never duplicate it. `model.py` holds `ImageMetadata` (raw per-standard views + generated canonical accessors) and the typed values (`LangAlt`, `MetaDate`, `GPSCoord`). `containers/` sniffs format and does marker/chunk I/O; `errors.py` defines the `MetadataError` hierarchy that all bad-input paths must raise.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) (`uv.lock` is committed) with a setuptools build backend.

```bash
uv sync --group dev          # install project + dev deps (pytest) into .venv
uv run pytest                # run the full test suite
uv run pytest tests/test_model.py::test_canonical_attribute_roundtrip  # run a single test
uv run python -m build       # build sdist/wheel (needs the `build` package)
```

CI installs with plain pip instead (`pip install . --group dev`) and runs `python -m pytest` — either toolchain works locally.

## Architecture & conventions

- **Layout**: package `svk_img_metadata/` (submodules `errors`, `fields`, `model`, `containers/`; `codecs/`, `sync`, `validate` land in later milestones) with tests in `tests/`. Public API is re-exported from `svk_img_metadata/__init__.py` and imported in tests as `from svk_img_metadata import ...`.
- **Python support**: `requires-python = ">=3.10"`, and CI runs the matrix **3.10 → 3.14**. Don't use syntax/stdlib features newer than 3.10.
- **Ruff** is the linter/formatter (dev dependency, `[tool.ruff]` in `pyproject.toml`, `target-version = "py310"`). A `PostToolUse` hook auto-runs `ruff format` + `ruff check --fix` on edited `.py` files. No type checker is configured yet — if you add `mypy`/`ty`, add it to the `dev` group and to CI.

## Security

This library parses **untrusted image files** — treat every input byte as attacker-controlled. The rules below are hard requirements, not suggestions.

- **XMP is RDF/XML — never parse it with an unsafe XML parser.** XMP packets must be parsed with **`defusedxml`** (or an `lxml`/stdlib parser with DTD processing and external-entity resolution explicitly disabled and entity-expansion bounded). Parsing XMP with stdlib `xml.etree`/`xml.dom` or a default-configured `lxml` is an XXE (data exfiltration / SSRF) and billion-laughs (DoS) vulnerability. Enforce this the moment any `import xml` / `lxml` / XMP-handling code appears.
- **Guard against resource exhaustion**: keep Pillow's decompression-bomb limit (`Image.MAX_IMAGE_PIXELS`) enabled; validate every EXIF/IPTC length/count field against the actual remaining bytes before allocating or looping; cap TIFF IFD-chain / nested-structure traversal depth.
- **Malformed input must raise a clean library exception** — never an unhandled `struct.error`/`IndexError`/`MemoryError`/`RecursionError`, and never silent trust of a bad offset or length.
- **Pin and vet parsing dependencies** (Pillow, piexif, pyexiv2, exifread…): pyexiv2 wraps native exiv2 and Pillow bundles native codecs — both carry memory-safety CVEs, so check CVEs at add-time and before each release.
- A read-only `security-reviewer` subagent (`.claude/agents/security-reviewer.md`) audits for these; run it when adding parsing code or a parsing dependency, and before releases.

## Release flow

Publishing is fully automated and **tag/release-driven** — do not publish manually.

- `.github/workflows/test.yml` runs the pytest matrix on every push and PR.
- `.github/workflows/publish.yml` triggers on a GitHub **release (`created`)**: it re-runs the test matrix, builds, then publishes to PyPI via **trusted publishing** (OIDC, `environment: release`). Cutting a GitHub release is what ships a version, so bump `version` in `pyproject.toml` before tagging.
- **The publish workflow is currently disabled** — PyPI trusted-publishing permissions for this repo haven't been set up yet. Releases will not reach PyPI until the OIDC publisher is configured on PyPI and the workflow is re-enabled.
