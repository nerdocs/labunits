# Releasing

Releases are published to PyPI by the GitHub Actions workflow `.github/workflows/release.yml`.

1. Bump `version` in `pyproject.toml` (`uv version <X.Y.Z>`), commit.
2. Tag and push: `git tag vX.Y.Z && git push origin main vX.Y.Z`.

The workflow checks that the tag matches the project version, runs the tests, builds sdist and wheel, and uploads
them via PyPI Trusted Publishing (no API token involved).

## One-time setup

- On PyPI, project `labunits` → *Publishing* → add a GitHub trusted publisher: owner `nerdocs`, repository
  `labunits`, workflow `release.yml`, environment `pypi`.
- On GitHub, create the environment `pypi` (Settings → Environments); optionally require a reviewer there.
