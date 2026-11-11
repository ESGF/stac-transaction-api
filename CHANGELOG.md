# Changelog

All notable changes to this project are recorded in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version number lives in one place, `version` in `pyproject.toml`; the API reads it from there.

## [Unreleased]

## [1.3.1] - 2026-11-11

### Fixed

- `cachetools`, which `src/api.py` imports, was installed only with the `ceda` dependency group, so
  images built with the default `globus` authorizer could not import it. It is now a main
  dependency.
- `poetry.lock` was missing the `globus`, `ceda` and `test` dependency groups. It is regenerated to
  include them; no existing package changed version.

## [1.3.0] - 2026-11-11

Includes pull request [#53](https://github.com/ESGF/stac-transaction-api/pull/53).

### Added

- The EGI `/scope` endpoint also returns a `template` with dynamic scopes built from the EGI group
  admin API (one per project and role, plus a node template). The result is cached for
  `scope.ttl` seconds (default 8 hours). New `ScopeSettings` configure it.
- `TimeoutSettings` (`connect`, `read`) for the EGI token introspection request.
- PATCH requests are authorized with the role returned by `evaluate_patch` from `esgf-core-utils`
  instead of a fixed `UPDATE`.
- nginx runs in the same container as uvicorn. It terminates TLS on port 8000 and rejects request
  bodies larger than 2 MiB with HTTP 413. uvicorn listens only behind it, on `127.0.0.1:8001`.
- The `local` image target also publishes uvicorn directly on port 8001, bypassing nginx.
- Build the production image locally with `docker build --target production -t stac-transaction-api:production .`.
- Failed Kafka produce calls log the affected item.

### Changed

- Requires `esgf-core-utils` 1.2.0 or later.
- Validation errors raised by `esgf-core-utils` are re-raised with `instance` set to
  `<request_id>:<event_id>` instead of being wrapped in a new `RFC9457Exception`.
- Invalid or incomplete token introspection responses return `InvalidTokenException`, and a missing
  `entitlements` claim is treated as empty.
- The EGI `/scope` response `scope` field is now `default_scope` (`offline_access entitlements`)
  rather than a single configured string.
- The Dockerfile has two build targets, `local` (with `--reload`) and `production`, sharing one
  runtime stage. The README is shortened accordingly.
- The `production` image serves HTTPS on port 8000 through nginx, and the `local` image does too.
  uvicorn trusts `X-Forwarded-For` from nginx and the private address ranges, so the client address
  in its log is the real client rather than the load balancer.
- Added `uv.lock` alongside `poetry.lock`.

## [1.2.0] - 2026-10-21

### Added

- A `Publish schemas to gh-pages` workflow and `scripts/publish/` that generate the extension
  schemas and publish them to `gh-pages`. It runs on demand, on pushes to `main` that touch the
  schemas or scripts, and nightly, and supports a dry run.
- Schemas for the `CMIP6Test` collection.
- A pytest suite under `tests/` with coverage configuration (33% to 92% coverage).

### Changed

- The `CMIP6Test` extension schema URL and default version point at an existing schema, and the
  minimum CMIP7 extension schema version is higher.
- The extension schema URL regex accepts multi-digit version numbers.
- Runtime dependencies are declared in the main group of `pyproject.toml`, and Black is configured.
- `test/` is renamed to `data_challenges/` so it is not confused with `tests/`.

### Removed

- Unused `event_id` and `request_id` parameters of `validate_patch`.
- `src/test_api.py`, superseded by `tests/test_api.py`.

## [1.1.0] - 2026-07-21

Covers everything merged to `main` after 1.0.0, through pull request
[#52](https://github.com/ESGF/stac-transaction-api/pull/52).

### Added

- Validation of item geometry, including the WGS84 bounding box, and a check that extensions are not
  below a minimum version (`ExtensionBelowMinimumException`).
- A check that the EGI token audience matches the host (`InvalidTokenAudienceException`), and a
  `/scope` endpoint for EGI authorization with the scope as a setting.
- The access control policy is cached and can be loaded from `s3://`.
- Missing extension schema URLs are handled, and validation errors include more detail and their
  cause.
- Schema URLs for the `CMIP6Plus` and `CORDEX-CMIP6` collections.
- For PATCH requests, the institute id is taken from the item id, and the institution is optional in
  the identifier pattern.
- uvicorn logs the `X-Forwarded-For` address, the health check is filtered out of the access log,
  and a `debug` setting is available.
- A pre-commit workflow that runs on pushes and pull requests to `main` and `integration`.

### Changed

- Refactored to use `esgf-core-utils` (previously `esgf-playground-utils`) for models, Kafka and
  projects and nodes. The authorizers move to `src/authorizer/` and the settings to
  `src/settings/`.
- The Globus and EGI authorizers both use the `Authorizer` from `esgf-core-utils`. The authorizer is
  selected with `TRANSACTION_AUTHORIZER` (`globus` or `egi`).
- Dependencies are managed with Poetry only, and the pinned versions are relaxed.
- Updated default ESGF extension schema versions.

### Removed

- Item update (PUT) and delete methods; only create and patch remain.
- The `esgvoc` dependency and `requirements.txt`.
- The check that the collection id matches `item.collection`.

## [1.0.0] - 2026-05-01

Initial release, the state of `main` on 2026-05-01.

### Added

- A STAC Transaction API built on `stac-fastapi` for creating, updating, patching and deleting
  items. Requests are authorized and published as events, with `auth` metadata, to Kafka on AWS MSK.
- Globus and EGI authorizers with authorization caching and an access control policy.
- Validation of items, STAC extensions and PATCH operations.
- Configuration from the environment, with secrets loaded from AWS Secrets Manager.
- A Docker image, a local Kafka stack (`compose-kafka.yaml` and ksqlDB scripts), pre-commit hooks,
  an initial CI/CD workflow and Poetry for dependencies.
- Scripts to download, process and send items for the data challenges.

[Unreleased]: https://github.com/ESGF/stac-transaction-api/compare/v1.3.1...HEAD
[1.3.1]: https://github.com/ESGF/stac-transaction-api/releases/tag/v1.3.1
[1.3.0]: https://github.com/ESGF/stac-transaction-api/releases/tag/v1.3.0
[1.2.0]: https://github.com/ESGF/stac-transaction-api/releases/tag/v1.2.0
[1.1.0]: https://github.com/ESGF/stac-transaction-api/releases/tag/v1.1.0
[1.0.0]: https://github.com/ESGF/stac-transaction-api/releases/tag/v1.0.0
