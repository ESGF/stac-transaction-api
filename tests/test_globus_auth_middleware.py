import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from authorizer.globus_auth_middleware import (
    GlobusAuthorizer,
    _AuthTTLCache,
    _cache_ttl_seconds,
)
from settings import settings

# Token info that satisfies _validate_token_info against the test settings
# (values match what conftest.py sets via env vars)
VALID_TOKEN_INFO = {
    "active": True,
    "aud": ["test-client-id"],
    "scope": "test-scope",
    "iss": "https://auth.globus.org",
    "exp": int(time.time()) + 3600,
    "client_id": "test-client-id",
    "sub": "test-subject",
}

ACTIVE_GROUPS = [{"group_id": "group-abc", "identity_id": "identity-xyz"}]


@pytest.fixture
def middleware():
    return GlobusAuthorizer(app=MagicMock())


@pytest.fixture
def test_app():
    app = FastAPI()
    app.add_middleware(GlobusAuthorizer)

    @app.get("/test")
    async def test_route():
        return {"ok": True}

    @app.get("/healthcheck")
    async def healthcheck():
        return {"healthcheck": True}

    return app


class TestAuthTTLCache:
    def test_miss_returns_none(self):
        cache = _AuthTTLCache()
        assert cache.get("some-token") is None

    def test_hit_returns_auth(self):
        cache = _AuthTTLCache()
        auth = {"token_info": VALID_TOKEN_INFO, "groups": ACTIVE_GROUPS}
        cache.set("token", auth, ttl=300)
        assert cache.get("token") == auth

    def test_expired_entry_returns_none(self):
        cache = _AuthTTLCache()
        cache.set("token", {"token_info": {}, "groups": []}, ttl=300)
        key = cache._key("token")
        cache._entries[key].expires_at = time.monotonic() - 1
        assert cache.get("token") is None

    def test_zero_ttl_not_stored(self):
        cache = _AuthTTLCache()
        cache.set("token", {"token_info": {}, "groups": []}, ttl=0)
        assert cache.get("token") is None

    def test_negative_ttl_not_stored(self):
        cache = _AuthTTLCache()
        cache.set("token", {"token_info": {}, "groups": []}, ttl=-1)
        assert cache.get("token") is None

    def test_different_tokens_are_independent(self):
        cache = _AuthTTLCache()
        auth_a = {"token_info": {}, "groups": [{"group_id": "a"}]}
        auth_b = {"token_info": {}, "groups": [{"group_id": "b"}]}
        cache.set("token-a", auth_a, ttl=300)
        cache.set("token-b", auth_b, ttl=300)
        assert cache.get("token-a") == auth_a
        assert cache.get("token-b") == auth_b


class TestCacheTTLSeconds:
    def test_no_exp_returns_max_ttl(self):
        assert _cache_ttl_seconds({}, max_ttl=300) == 300

    def test_exp_in_near_future_returns_remaining(self):
        future_exp = int(time.time()) + 100
        result = _cache_ttl_seconds({"exp": future_exp}, max_ttl=300)
        assert result == 100

    def test_exp_far_future_capped_by_max_ttl(self):
        future_exp = int(time.time()) + 9999
        result = _cache_ttl_seconds({"exp": future_exp}, max_ttl=300)
        assert result == 300

    def test_exp_in_past_returns_zero(self):
        past_exp = int(time.time()) - 100
        result = _cache_ttl_seconds({"exp": past_exp}, max_ttl=300)
        assert result == 0


class TestValidateTokenInfo:
    def test_valid_token_returns_none(self, middleware):
        assert middleware._validate_token_info(VALID_TOKEN_INFO) is None

    def test_inactive_token_returns_401(self, middleware):
        token_info = {**VALID_TOKEN_INFO, "active": False}
        response = middleware._validate_token_info(token_info)
        assert response.status_code == 401
        assert "Inactive token" in response.body.decode()

    def test_wrong_audience_returns_401(self, middleware):
        token_info = {**VALID_TOKEN_INFO, "aud": ["wrong-client-id"]}
        response = middleware._validate_token_info(token_info)
        assert response.status_code == 401
        assert "Invalid token audience" in response.body.decode()

    def test_wrong_scope_returns_401(self, middleware):
        token_info = {**VALID_TOKEN_INFO, "scope": "wrong-scope"}
        response = middleware._validate_token_info(token_info)
        assert response.status_code == 401
        assert "Invalid token scope" in response.body.decode()

    def test_wrong_issuer_returns_401(self, middleware):
        token_info = {**VALID_TOKEN_INFO, "iss": "https://evil.auth.example.com"}
        response = middleware._validate_token_info(token_info)
        assert response.status_code == 401
        assert "Invalid token issuer" in response.body.decode()


class TestGlobusAuthorizerDispatch:
    def test_no_auth_header_returns_401(self, test_app):
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/test")
        assert response.status_code == 401
        assert "No authorization header" in response.json()["detail"]

    def test_non_bearer_scheme_returns_401(self, test_app):
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/test", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert response.status_code == 401
        assert "Invalid authorization header" in response.json()["detail"]

    def test_healthcheck_bypasses_auth(self, test_app):
        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/healthcheck")
        assert response.status_code == 200

    def test_no_active_groups_returns_401(self, test_app, mocker):
        mock_response = MagicMock()
        mock_response.data = VALID_TOKEN_INFO
        mocker.patch.object(
            settings.client.confidential_client,
            "oauth2_token_introspect",
            return_value=mock_response,
        )
        mocker.patch.object(GlobusAuthorizer, "get_groups", return_value=[])

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/test", headers={"Authorization": "Bearer valid-token"})
        assert response.status_code == 401
        assert "No active group memberships" in response.json()["detail"]

    def test_valid_token_with_groups_calls_next(self, test_app, mocker):
        mock_response = MagicMock()
        mock_response.data = VALID_TOKEN_INFO
        mocker.patch.object(
            settings.client.confidential_client,
            "oauth2_token_introspect",
            return_value=mock_response,
        )
        mocker.patch.object(GlobusAuthorizer, "get_groups", return_value=ACTIVE_GROUPS)
        mocker.patch(
            "authorizer.globus_auth_middleware.get_access_control_policy",
            return_value=[],
        )

        client = TestClient(test_app, raise_server_exceptions=False)
        response = client.get("/test", headers={"Authorization": "Bearer valid-token"})
        assert response.status_code == 200

    def test_cache_hit_skips_introspect(self, test_app, mocker):
        introspect_mock = mocker.patch.object(
            settings.client.confidential_client,
            "oauth2_token_introspect",
        )
        mocker.patch(
            "authorizer.globus_auth_middleware._auth_cache.get",
            return_value={"token_info": VALID_TOKEN_INFO, "groups": ACTIVE_GROUPS},
        )
        mocker.patch(
            "authorizer.globus_auth_middleware.get_access_control_policy",
            return_value=[],
        )

        client = TestClient(test_app, raise_server_exceptions=False)
        client.get("/test", headers={"Authorization": "Bearer cached-token"})
        introspect_mock.assert_not_called()
