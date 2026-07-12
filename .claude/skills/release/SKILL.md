---
name: release
description: Cut a new release of svk-img-metadata — bump the version, draft release notes from git history, tag, and create the GitHub release. User-invoked only.
disable-model-invocation: true
---

# Release

Cut a new release of `svk-img-metadata`. Releasing is **GitHub-release-driven**: creating a GitHub release is what would trigger `.github/workflows/publish.yml`. Follow these steps in order and confirm the version with the user before tagging.

## Preconditions

1. Confirm the working tree is clean and on `main`, up to date with `origin/main`:
   ```bash
   git status --porcelain && git rev-parse --abbrev-ref HEAD && git fetch origin && git status -sb
   ```
   If not clean / not on `main` / behind origin, stop and tell the user.
2. Confirm CI is green on `main` (the test matrix must pass before shipping).

## Steps

1. **Determine versions.** Read the current version from `pyproject.toml` (`version = "X.Y"`) and the latest tag:
   ```bash
   git tag --list --sort=-v:refname | head -5
   ```
   Propose the next version and **ask the user to confirm** (patch / minor / major). Do not guess silently. This project uses `MAJOR.MINOR` today (e.g. `0.1`); match the existing scheme unless the user says otherwise.

2. **Draft release notes.** Summarize changes since the last tag, grouped (Features / Fixes / Internal). Use:
   ```bash
   git log <last-tag>..HEAD --no-merges --pretty=format:'%s'
   ```
   If there is no prior tag, summarize since the first commit. Show the draft to the user for approval.

3. **Bump the version.** Edit `version` in `pyproject.toml` to the confirmed value. Commit on `main`:
   ```
   git commit -am "Release vX.Y"
   ```
   (Ends the commit message with the standard Co-Authored-By trailer.)

4. **Tag and push.**
   ```bash
   git tag vX.Y
   git push origin main --tags
   ```

5. **Create the GitHub release.** Prefer the GitHub MCP tools (in this repo `gh pr`/`gh release` has been observed to swallow output). Create a release for tag `vX.Y` with the approved notes. This is the step that "ships" the version.

## ⚠️ PyPI publishing is currently disabled

`.github/workflows/publish.yml` is **turned off** pending PyPI trusted-publishing (OIDC) setup for this repo. **Creating the GitHub release will NOT publish to PyPI yet.** After creating the release, explicitly tell the user:

> The GitHub release is created, but it will not reach PyPI until the trusted publisher is configured on PyPI and the publish workflow is re-enabled.

Do not attempt to publish to PyPI manually or to re-enable/edit the workflow as part of this skill (the workflow-guard hook will prompt on any `.github/workflows/` edit). See the "Release flow" and "Security" sections of `CLAUDE.md` for context.
