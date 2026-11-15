# Contributing

Thanks for helping with the STAC Transaction API. This page covers how to propose a change.
See the [README](README.md) for how to run the service locally.

## Workflow

1. Create a branch from `integration` and keep it focused on one change.
2. Open a pull request into `integration`. Releases are made by merging `integration` into `main`.
3. Make sure the pre-commit checks and the tests pass (see below). The `pre-commit` workflow runs on
   every pull request.
4. Add a line to [CHANGELOG.md](CHANGELOG.md) under `[Unreleased]` (see below).

## Commit messages

Use a short imperative title that says what the change does, for example
`Move cachetools to main dependencies`, not `Fix dependency`. Use the body to explain why the change
was needed when that is not obvious.

## Code style

Formatting is checked with [pre-commit](https://pre-commit.com), using Black (line length 145) and
flake8 (see `.flake8`). Install the hooks once, and they run on every commit:

```
pip install pre-commit
pre-commit install
pre-commit run --all-files   # check everything on demand
```

## Tests

Tests live in `tests/` and use pytest. The Kafka producer is mocked, so they need no running
services. From a Poetry environment with Python 3.12:

```
poetry install --no-root --only main,globus,test
poetry run pytest
```

Add or update tests for the code you change. Coverage is reported on every run
(`--cov=src`).

## Dependencies

Dependencies are declared in `pyproject.toml`, and the Docker build installs them from `poetry.lock`.

- Anything `src/` imports unconditionally belongs in `dependencies`. Packages used by only one
  authorizer go in its group (`globus` or `ceda`), and test tools go in `test`. A package that is
  needed at runtime but sits in a group is missing from the default image.
- After changing `pyproject.toml`, run `poetry lock` and commit the updated `poetry.lock`. The
  repository also contains a `uv.lock`; keep it in step if you use `uv`.

## Changelog and versions

The changelog follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- **In a pull request:** add one line to the matching heading (`Added`, `Changed`, `Fixed` or
  `Removed`) under `## [Unreleased]`. Write for someone who uses the API, not for the code reviewer.
- **The version** is set in one place, `version` in `pyproject.toml`. The API reads it from there, so
  do not hard-code it elsewhere.
- **To release:** in a pull request, rename `[Unreleased]` to the new version and date, add a new empty
  `[Unreleased]`, bump `version` in `pyproject.toml`, and add the version link at the bottom of
  `CHANGELOG.md`. After it is merged, tag the commit `vX.Y.Z` and push the tag.

## Docker

The `Dockerfile` has two targets that share a runtime stage with nginx and uvicorn in one container:

- `local` runs with `--reload` and also publishes uvicorn on port 8001, bypassing nginx (development
  only).
- `production` is the default target. nginx terminates TLS on port 8000 and rejects request bodies over
  2 MiB, and uvicorn listens only on `127.0.0.1:8001`. Never expose port 8001 of this image.

## Schemas

The schemas that clients use to validate extensions are published to `gh-pages` by the
`Publish schemas to gh-pages` workflow when `scripts/publish/` or `schemas/` change on `main`. Test
a change with the workflow's dry-run option before relying on it.

## Questions

Open an issue if something is unclear or you want to discuss a larger change before writing it.
