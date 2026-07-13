# STAC Transaction API — Code Review & Recommendations

*Perspective: Research Software Engineer, ESGF/climate data infrastructure*

---

## 1. Critical Issues

These are bugs or security problems that need attention now.

---

### Bug: `patch_item` never reads headers correctly

**`src/client.py`** — the header-reading line reads the literal string key `"headers"` from the request headers instead of reading the headers object itself:

```python
# What the code does
headers = request.headers.get("headers", {})   # always returns {}

# What it should do
headers = request.headers
```

**Impact:** In every `PATCH` request, `User-Agent` is always `"/"` and `x-request-id` is always a freshly generated UUID, so the publisher identity embedded in every Kafka event is wrong.

---

### Bug: `scripts/run-local.sh` passes `--detach` to the wrong process

`--detach` is passed as a positional argument to `uvicorn` inside the container, not as a flag to `docker run`. The container never actually detaches.

---

### Security: Credentials in the repository

**`src/.env.integration`** and **`src/.env.production`** contain live Kafka SASL passwords and Globus client secrets and appear to be committed to the repo. Even if `.gitignore` covers `.env.*` patterns, `.env.integration` and `.env.production` are non-standard names that may slip through. These should be verified to not be in git history and should be managed through a secrets manager (AWS Secrets Manager, Vault, GitHub Actions secrets).

---

### Security: TLS verification disabled in EGI authorizer

**`src/authorizer/egi_authorizer.py`**:

```python
response = httpx.post(..., verify=False)
```

This disables TLS certificate verification for every token introspection call to EGI AAI — the most security-critical call in the EGI path. This should use a proper CA bundle or at minimum be a configurable option, not hardcoded off.

---

### Performance: Live HTTP fetch for JSON Schema on every request

**`src/utils.py` — `get_extension_validator()`** fetches the extension's JSON Schema over HTTP on every single validation call with no caching:

```python
response = httpx.get(extension)  # every request, no cache
validator = jsonschema.Draft7Validator(response.json())
```

For a publish endpoint under any real load, this means every POST or PATCH makes multiple outbound HTTP calls to external schema URIs. This is a network dependency in the hot path, adds latency, and will cause failures if those URLs are temporarily unreachable. The validator should be cached (e.g., in a module-level dict keyed by URI).

---

## 2. Architecture Concerns

---

### Sync Globus/HTTPX calls inside async middleware

Both `GlobusAuthorizer` and `EGIAuthorizer` are `async def dispatch()` methods, but internally they make blocking synchronous calls:

- Globus SDK (`oauth2_token_introspect`, `oauth2_get_dependent_tokens`, `get_my_groups`) is synchronous
- `EGIAuthorizer` uses `httpx.post(...)` (synchronous) inside an async handler

This blocks the entire asyncio event loop during every token validation cache miss. For a research infrastructure service that may experience bursty load during data challenges or publication campaigns, this could cause significant latency spikes. The fix is to either use `asyncio.to_thread()` to offload blocking calls, or switch to an async HTTP client for the EGI path.

The existing auth cache in `GlobusAuthorizer` partially mitigates this, but only after the first request per token.

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

### Unimplemented endpoints return 500

`update_item`, `delete_item`, `create_collection`, etc. raise `NotImplementedError`, which FastAPI will catch and return as a 500 Internal Server Error. Publishers hitting these will see a server error rather than a clear `405 Method Not Allowed`. These should return proper HTTP responses.

---

### Inconsistent import style in `client.py`

```python
# client.py uses:
from src.authorizer import Authorizer

# api.py and everything else uses:
from authorizer import Authorizer
```

This suggests `client.py` was written or run from a different working directory context. It may work in some environments and fail in others depending on how `PYTHONPATH` is set.

---

## 3. Testing

This is the area most in need of investment.

---

### One unit test exists

The entire automated test suite is a single test: `test_api.py::TestAPI::test_api__healthcheck`. It verifies the healthcheck endpoint returns 200. Nothing else is tested automatically.

The real test tooling lives in `test/` — but those are manual integration scripts (`data_challenge.py`, `stac_client.py`), not pytest tests. They require live Globus auth, a running API, and real Kafka. Valuable for data challenges, but they're not a substitute for automated tests.

---

### What should have test coverage

- Authorization logic in `GlobusAuth` (`globus_auth.py`) — the permission model is non-trivial and bugs here are security bugs
- Validation utilities in `utils.py` — `validate_extensions`, `operation_to_partial_item`, `validate_post`, `validate_patch`
- The `patch_item` header bug described above would have been caught by a test

---

### Unit test file is inside `src/`

`src/test_api.py` is unusual placement — test files conventionally live outside the source package. It also means running `pytest` from the project root requires knowing to look in `src/`. This is likely an artifact of how uvicorn's working directory is set up in Docker, but it's worth standardizing.

---

## 4. Dependency & Build

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

| Priority | Item |
|---|---|
| **P0** | Audit credentials in git history (`.env.integration`, `.env.production`) |
| **P0** | Fix `patch_item` header bug — publisher identity is wrong in all PATCH Kafka events |
| **P1** | Cache JSON Schema validators — currently fetched live on every request |
| **P1** | Fix TLS verification in EGI authorizer |
| **P1** | Add tests for authorization and validation logic |
| **P2** | Offload sync Globus/HTTPX calls off the event loop |
| **P2** | Return 405 from unimplemented endpoints instead of 500 |
| **P2** | Fix `run-local.sh` `--detach` flag placement |
| **P3** | Move `DEFAULT_EXTENSIONS` to external config |
| **P3** | Remove or justify `pyjwt` dependency |
| **P3** | Fix `confidential_client: Any` type annotation |
