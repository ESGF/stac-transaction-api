# STAC Transaction API — Code Review & Recommendations

*Perspective: Research Software Engineer, ESGF/climate data infrastructure*

---

## 1. Critical Issues

These are bugs or security problems that need attention now.

---

### ✅ Bug: `patch_item` never reads headers correctly

**`src/client.py`** — Fixed. `request.headers.get("headers", {})` was replaced with `request.headers`, and the missing `MissingPermissionException` guard was added to match `create_item` behavior.

---

### Bug: `scripts/run-local.sh` passes `--detach` to the wrong process

`--detach` is passed as a positional argument to `uvicorn` inside the container, not as a flag to `docker run`. The container never actually detaches.

---

### Security: TLS verification disabled in EGI authorizer

**`src/authorizer/egi_authorizer.py`**:

```python
response = httpx.post(..., verify=False)
```

This disables TLS certificate verification for every token introspection call to EGI AAI — the most security-critical call in the EGI path. This should use a proper CA bundle or at minimum be a configurable option, not hardcoded off.

---

### ✅ Performance: Live HTTP fetch for JSON Schema on every request

**`src/utils.py` — `get_extension_validator()`** — Fixed. Added `@functools.lru_cache(maxsize=None)` so each schema URI is fetched once per process lifetime.

---

## 2. Architecture Concerns

---

### ✅ Sync Globus/HTTPX calls inside async middleware

Fixed. `oauth2_token_introspect`, `get_groups`, and `_authorizer_context` in `GlobusAuthorizer` are now wrapped with `asyncio.to_thread()`. The EGI authorizer was already using `httpx.AsyncClient` correctly — no change needed there.

---

### Access control policy is a flat text file

The policy format is a newline-delimited list of entitlement strings parsed by regex. While simple, this approach has some limitations worth thinking about:

- No schema validation on the policy file itself — a malformed line silently fails to add permissions
- Stale-cache fallback on refresh failure is good, but there's no alerting when this happens
- The `"*"` wildcard in current policies grants all nodes/projects — fine for dev, but production policies should probably use explicit node IDs

---

### `DEFAULT_EXTENSIONS` hardcoded in settings

The mapping of collection IDs to required STAC extensions and their version floors (`CMIP6`, `CMIP6Plus`, `CMIP7`, `CORDEX-CMIP6`, `obs4MIPs`) is hardcoded in **`src/settings/__init__.py`**. Adding a new collection or bumping an extension version requires a code change and a deploy. This is a configuration concern that would ideally live in an external config file or environment variable.

---

### ✅ Unimplemented endpoints return 500

Fixed. A global `NotImplementedError` handler in `api.py` now returns `405 Method Not Allowed` instead of a 500.

---

### ✅ Inconsistent import style in `client.py`

Fixed. `from src.authorizer import Authorizer` corrected to `from authorizer import Authorizer`, consistent with all other files.

---

## 3. Testing

This is the area most in need of investment.

---

### One unit test exists

The entire automated test suite is a single test: `test_api.py::TestAPI::test_api__healthcheck`. It verifies the healthcheck endpoint returns 200. Nothing else is tested automatically.

The real test tooling lives in `test/` — but those are manual integration scripts (`data_challenge.py`, `stac_client.py`), not pytest tests. They require live Globus auth, a running API, and real Kafka. Valuable for data challenges, but they're not a substitute for automated tests.

---

### What should have test coverage

- Authorization logic in `GlobusAuth` (`globus_auth_model.py`) — the permission model is non-trivial and bugs here are security bugs
- Validation utilities in `utils.py` — `validate_extensions`, `operation_to_partial_item`, `validate_post`, `validate_patch`
- The `patch_item` header bug fixed in this branch would have been caught by a test

---

### Unit test file is inside `src/`

`src/test_api.py` is unusual placement — test files conventionally live outside the source package. It also means running `pytest` from the project root requires knowing to look in `src/`. This is likely an artifact of how uvicorn's working directory is set up in Docker, but it's worth standardizing.

---

## 4. Dependency & Build

---

### ✅ globus-sdk upgraded from 3.62.0 to 4.8.1

`test/stac_client.py` migrated from deprecated `SimpleJSONFileAdapter` to `JSONTokenStorage`.

---

### `pyjwt` appears unused

`pyjwt==2.12.1` is in the `globus` dependency group but there are no imports of `jwt` anywhere in `src/`. If it's truly unused, it should be removed. If it's needed transitively, it should be documented.

---

### `boto3` pinned to an exact version

`boto3==1.43.6` (exact pin) will fall behind quickly. AWS SDK minor releases are frequent and often include bug fixes. A floor constraint (`boto3>=1.43.6`) would be more appropriate unless there's a specific compatibility reason for the exact pin.

---

### No lock file checked for the test runner

The project has a `poetry.lock`, but the CI pipeline only runs `pre-commit` (black + flake8). Tests are never run in CI. Combined with a single test, this means the CI gives very little confidence about correctness.

---

### Docker builds `librdkafka` from source

This is correct and necessary for `confluent-kafka` on the AWS SAM base image. However, the build stage clones `librdkafka` at tag `v2.6.0` — this is a tag (good), but worth noting: if the tag were ever moved it would silently pull different code. Low risk in practice.

---

## 5. Minor / Style

- **`src/settings/globus.py:17`** — `confidential_client: Any` loses type safety. Should be `confidential_client: ConfidentialAppAuthClient`.
- **`compose.yaml`** — mounts `./src` as a volume for live reload (good for development), but this means the container's behavior differs from the Docker image — local dev and production are running different filesystem layouts.
- **`compose-kafka.yaml`** — replication factor 1 everywhere is expected for local dev, but worth a comment so no one accidentally uses this compose file as a template for staging.
- **`.flake8` max-line-length is 145** but the pre-commit black config also uses 145. These match, which is good. Worth noting that 145 is wider than most style guides recommend, though that's a preference call.
- **`scripts/globus_setup.py`** hardcodes a UChicago-specific native app client ID and project name (`"ESGFNG"`). If other institutions run their own deployments, this script won't generalize without modification.

---

## Priority Summary

| Priority | Status | Item |
|---|---|---|
| **P0** | ✅ Fixed | `patch_item` header bug — publisher identity was wrong in all PATCH Kafka events |
| **P1** | ✅ Fixed | Cache JSON Schema validators — were fetched live on every request |
| **P1** | Open | Fix TLS verification in EGI authorizer |
| **P1** | Open | Add tests for authorization and validation logic |
| **P2** | ✅ Fixed | Return 405 from unimplemented endpoints instead of 500 |
| **P2** | ✅ Fixed | Offload sync Globus/HTTPX calls off the event loop |
| **P2** | Open | Fix `run-local.sh` `--detach` flag placement |
| **P2** | ✅ Fixed | Fix inconsistent `from src.authorizer` import in `client.py` |
| **P3** | ✅ Fixed | globus-sdk upgraded to 4.8.1 |
| **P3** | Open | Move `DEFAULT_EXTENSIONS` to external config |
| **P3** | Open | Remove or justify `pyjwt` dependency |
| **P3** | Open | Fix `confidential_client: Any` type annotation |
