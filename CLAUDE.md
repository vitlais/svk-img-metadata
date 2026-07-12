# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This is an **early-stage skeleton** generated from a Python library template. `svk_img_metadata/__init__.py` currently holds only a placeholder `example_function`; the intended purpose (per the package name) is reading/writing image metadata such as EXIF/XMP/IPTC. Expect to build out the real API from near-zero — most files are template defaults.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) (`uv.lock` is committed) with a setuptools build backend.

```bash
uv sync --group dev          # install project + dev deps (pytest) into .venv
uv run pytest                # run the full test suite
uv run pytest tests/test_svk_img_metadata.py::test_example_function  # run a single test
uv run python -m build       # build sdist/wheel (needs the `build` package)
```

CI installs with plain pip instead (`pip install . --group dev`) and runs `python -m pytest` — either toolchain works locally.

## Architecture & conventions

- **Layout**: a single flat package `svk_img_metadata/` with tests in `tests/`. Public API is re-exported from `svk_img_metadata/__init__.py` and imported in tests as `from svk_img_metadata import ...`.
- **Python support**: `requires-python = ">=3.10"`, and CI runs the matrix **3.10 → 3.14**. Don't use syntax/stdlib features newer than 3.10.
- **No linter or type checker is configured** yet — if you add `ruff`/`mypy`, add it to the `dev` dependency group in `pyproject.toml` and to CI.

## Release flow

Publishing is fully automated and **tag/release-driven** — do not publish manually.

- `.github/workflows/test.yml` runs the pytest matrix on every push and PR.
- `.github/workflows/publish.yml` triggers on a GitHub **release (`created`)**: it re-runs the test matrix, builds, then publishes to PyPI via **trusted publishing** (OIDC, `environment: release`). Cutting a GitHub release is what ships a version, so bump `version` in `pyproject.toml` before tagging.
- **The publish workflow is currently disabled** — PyPI trusted-publishing permissions for this repo haven't been set up yet. Releases will not reach PyPI until the OIDC publisher is configured on PyPI and the workflow is re-enabled.
