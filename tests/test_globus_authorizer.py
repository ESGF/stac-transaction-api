"""Unit tests for src/authorizer/globus_authorizer.py."""

import time
from unittest import mock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from authorizer import globus_authorizer as ga
from settings import settings

GROUP_ID = "11111111-1111-1111-1111-111111111111"
OTHER_GROUP_ID = "22222222-2222-2222-2222-222222222222"
POLICY = [
    f"collection:CMIP6:role=CREATE:group:{GROUP_ID}",
    f"collection:CMIP6:role=UPDATE:group:{OTHER_GROUP_ID}",
]


def token_info(**overrides):
    info = {
        "active": True,
        "aud": [settings.client.client_id],
        "scope": settings.client.scope_string,
        "iss": settings.client.issuer,
        "client_id": "cid",
        "sub": "user-1",
        "exp": int(time.time()) + 3600,
    }
    info.update(overrides)
    return info


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Reset module-level caches around every test."""
    monkeypatch.setattr(ga, "_auth_cache", ga._AuthTTLCache())
    monkeypatch.setattr(ga, "_policy_cache", None)


@pytest.fixture
def fake_client(monkeypatch):
    """Replace the Globus confidential client on settings with a mock."""
    fake = mock.MagicMock()
    fake.oauth2_token_introspect.return_value.data = token_info()
    monkeypatch.setattr(settings.client, "confidential_client", fake)
    return fake


@pytest.fixture
def app_client(fake_client, monkeypatch):
    """App protected by GlobusAuthorizer with group lookup + policy stubbed."""
    monkeypatch.setattr(ga, "get_access_control_policy", lambda: POLICY)
    monkeypatch.setattr(ga.GlobusAuthorizer, "get_groups", lambda self, token: [{"group_id": GROUP_ID, "identity_id": "i"}])

    app = FastAPI()
    app.add_middleware(ga.GlobusAuthorizer)

    @app.get("/whoami")
    async def whoami(request: Request):
        return {"client_id": request.state.authorizer.requester_data.client_id}

    @app.get("/healthcheck")
    async def healthcheck():
        return {"ok": True}

    return TestClient(app)


AUTH = {"Authorization": "Bearer abc123"}


# --------------------------------------------------------------------------
# _AuthTTLCache
# --------------------------------------------------------------------------
class TestAuthTTLCache:
    def test_miss_returns_none(self):
        assert ga._AuthTTLCache().get("tok") is None

    def test_hit_returns_value(self):
        cache = ga._AuthTTLCache()
        cache.set("tok", {"a": 1}, ttl=60)
        assert cache.get("tok") == {"a": 1}

    def test_tokens_are_not_stored_in_plaintext(self):
        cache = ga._AuthTTLCache()
        cache.set("super-secret-token", {"a": 1}, ttl=60)
        assert "super-secret-token" not in cache._entries

    def test_expired_entry_returns_none_and_is_removed(self, monkeypatch):
        cache = ga._AuthTTLCache()
        now = 1000.0
        monkeypatch.setattr(ga.time, "monotonic", lambda: now)
        cache.set("tok", {"a": 1}, ttl=10)

        monkeypatch.setattr(ga.time, "monotonic", lambda: now + 10)
        assert cache.get("tok") is None
        assert cache._entries == {}

    @pytest.mark.parametrize("ttl", [0, -5])
    def test_non_positive_ttl_not_cached(self, ttl):
        cache = ga._AuthTTLCache()
        cache.set("tok", {"a": 1}, ttl=ttl)
        assert cache.get("tok") is None

    def test_expired_entries_evicted_when_over_capacity(self, monkeypatch):
        cache = ga._AuthTTLCache(max_entries=2)
        now = 1000.0
        monkeypatch.setattr(ga.time, "monotonic", lambda: now)
        cache.set("old1", {}, ttl=5)
        cache.set("old2", {}, ttl=5)

        monkeypatch.setattr(ga.time, "monotonic", lambda: now + 100)
        cache.set("new", {"n": 1}, ttl=60)

        assert len(cache._entries) == 1
        assert cache.get("new") == {"n": 1}


# --------------------------------------------------------------------------
# _cache_ttl_seconds
# --------------------------------------------------------------------------
class TestCacheTTL:
    def test_no_exp_uses_max(self):
        assert ga._cache_ttl_seconds({}, 300) == 300

    def test_exp_further_than_max_is_capped(self):
        assert ga._cache_ttl_seconds({"exp": int(time.time()) + 10_000}, 300) == 300

    def test_exp_sooner_than_max_wins(self):
        ttl = ga._cache_ttl_seconds({"exp": int(time.time()) + 60}, 300)
        assert 58 <= ttl <= 60

    def test_already_expired_is_zero(self):
        assert ga._cache_ttl_seconds({"exp": int(time.time()) - 60}, 300) == 0


# --------------------------------------------------------------------------
# _load_access_control_policy
# --------------------------------------------------------------------------
class TestLoadPolicy:
    def test_file_scheme_strips_blank_lines(self, tmp_path):
        path = tmp_path / "policy.txt"
        path.write_text("  line-a  \n\n   \nline-b\n")
        assert ga._load_access_control_policy(f"file://{path}") == ["line-a", "line-b"]

    def test_s3_scheme(self):
        body = mock.MagicMock()
        body.read.return_value = b"line-a\nline-b\n"
        with mock.patch.object(ga.boto3, "client") as boto_client:
            boto_client.return_value.get_object.return_value = {"Body": body}
            result = ga._load_access_control_policy("s3://my-bucket/path/policy.txt")

        assert result == ["line-a", "line-b"]
        boto_client.return_value.get_object.assert_called_once_with(Bucket="my-bucket", Key="path/policy.txt")

    def test_s3_without_key_raises(self):
        with pytest.raises(RuntimeError, match="Invalid S3 policy path"):
            ga._load_access_control_policy("s3://my-bucket")

    def test_http_scheme(self):
        with mock.patch.object(ga.urllib3, "PoolManager") as pool:
            pool.return_value.request.return_value = mock.Mock(status=200, data=b"line-a\n")
            assert ga._load_access_control_policy("https://example.org/policy.txt") == ["line-a"]

    def test_http_error_status_raises(self):
        with mock.patch.object(ga.urllib3, "PoolManager") as pool:
            pool.return_value.request.return_value = mock.Mock(status=503, data=b"")
            with pytest.raises(RuntimeError, match="HTTP 503"):
                ga._load_access_control_policy("https://example.org/policy.txt")


# --------------------------------------------------------------------------
# get_access_control_policy (caching)
# --------------------------------------------------------------------------
class TestGetPolicy:
    def test_loads_once_while_cache_valid(self):
        with mock.patch.object(ga, "_load_access_control_policy", return_value=["p"]) as load:
            assert ga.get_access_control_policy() == ["p"]
            assert ga.get_access_control_policy() == ["p"]
        load.assert_called_once()

    def test_reloads_after_ttl(self, monkeypatch):
        monkeypatch.setattr(settings.client, "policy_cache_ttl_seconds", 10)
        now = {"t": 1000.0}
        monkeypatch.setattr(ga.time, "monotonic", lambda: now["t"])

        with mock.patch.object(ga, "_load_access_control_policy", side_effect=[["v1"], ["v2"]]) as load:
            assert ga.get_access_control_policy() == ["v1"]
            now["t"] += 11
            assert ga.get_access_control_policy() == ["v2"]
        assert load.call_count == 2

    def test_stale_policy_served_when_refresh_fails(self, monkeypatch):
        monkeypatch.setattr(settings.client, "policy_cache_ttl_seconds", 10)
        now = {"t": 1000.0}
        monkeypatch.setattr(ga.time, "monotonic", lambda: now["t"])

        with mock.patch.object(ga, "_load_access_control_policy", side_effect=[["v1"], RuntimeError("down")]):
            ga.get_access_control_policy()
            now["t"] += 11
            assert ga.get_access_control_policy() == ["v1"]

    def test_error_raised_when_no_stale_policy(self):
        with mock.patch.object(ga, "_load_access_control_policy", side_effect=RuntimeError("down")):
            with pytest.raises(RuntimeError):
                ga.get_access_control_policy()


# --------------------------------------------------------------------------
# _authorizer_context
# --------------------------------------------------------------------------
class TestAuthorizerContext:
    def test_only_entitlements_for_users_groups_are_added(self, monkeypatch):
        monkeypatch.setattr(ga, "get_access_control_policy", lambda: POLICY)
        fake_authorizer = mock.MagicMock()
        monkeypatch.setattr(ga, "Authorizer", mock.MagicMock(return_value=fake_authorizer))

        auth = {"token_info": token_info(), "groups": [{"group_id": GROUP_ID}]}
        result = ga._authorizer_context(auth)

        assert result is fake_authorizer
        fake_authorizer.add.assert_called_once_with([POLICY[0]])

    def test_requester_data_from_token_info(self, monkeypatch):
        monkeypatch.setattr(ga, "get_access_control_policy", lambda: [])
        auth = {"token_info": token_info(client_id="c1", sub="s1", iss="i1"), "groups": []}

        result = ga._authorizer_context(auth)

        assert result.requester_data.client_id == "c1"
        assert result.requester_data.sub == "s1"
        assert result.requester_data.iss == "i1"

    def test_no_groups_means_no_entitlements(self, monkeypatch):
        monkeypatch.setattr(ga, "get_access_control_policy", lambda: POLICY)
        fake_authorizer = mock.MagicMock()
        monkeypatch.setattr(ga, "Authorizer", mock.MagicMock(return_value=fake_authorizer))

        ga._authorizer_context({"token_info": token_info(), "groups": []})

        fake_authorizer.add.assert_called_once_with([])


# --------------------------------------------------------------------------
# GlobusAuthorizer middleware
# --------------------------------------------------------------------------
class TestMiddleware:
    @pytest.mark.parametrize("path", ["/healthcheck"])
    def test_bypass_paths_need_no_auth(self, app_client, path):
        assert app_client.get(path).status_code == 200

    def test_missing_header_401(self, app_client):
        response = app_client.get("/whoami")
        assert response.status_code == 401
        assert "No authorization header" in response.json()["detail"]

    @pytest.mark.parametrize("header", ["Basic abc", "abc123", "bearer abc"])
    def test_non_bearer_header_401(self, app_client, header):
        response = app_client.get("/whoami", headers={"Authorization": header})
        assert response.status_code == 401
        assert "Invalid authorization header" in response.json()["detail"]

    def test_valid_token_succeeds(self, app_client):
        response = app_client.get("/whoami", headers=AUTH)
        assert response.status_code == 200
        assert response.json() == {"client_id": "cid"}

    @pytest.mark.parametrize(
        "overrides,message",
        [
            ({"active": False}, "Inactive token"),
            ({"aud": ["someone-else"]}, "Invalid token audience"),
            ({"aud": []}, "Invalid token audience"),
            ({"scope": "wrong-scope"}, "Invalid token scope"),
            ({"iss": "https://evil.example.org"}, "Invalid token issuer"),
        ],
    )
    def test_invalid_token_info_401(self, app_client, fake_client, overrides, message):
        fake_client.oauth2_token_introspect.return_value.data = token_info(**overrides)
        response = app_client.get("/whoami", headers=AUTH)
        assert response.status_code == 401
        assert message in response.json()["detail"]

    def test_no_active_groups_401(self, app_client, monkeypatch):
        monkeypatch.setattr(ga.GlobusAuthorizer, "get_groups", lambda self, token: [])
        response = app_client.get("/whoami", headers=AUTH)
        assert response.status_code == 401
        assert "No active group memberships" in response.json()["detail"]

    def test_second_request_uses_cache(self, app_client, fake_client):
        assert app_client.get("/whoami", headers=AUTH).status_code == 200
        assert app_client.get("/whoami", headers=AUTH).status_code == 200
        fake_client.oauth2_token_introspect.assert_called_once()

    def test_failed_validation_not_cached(self, app_client, fake_client):
        fake_client.oauth2_token_introspect.return_value.data = token_info(active=False)
        app_client.get("/whoami", headers=AUTH)
        app_client.get("/whoami", headers=AUTH)
        assert fake_client.oauth2_token_introspect.call_count == 2

    def test_expired_token_is_not_cached(self, app_client, fake_client):
        fake_client.oauth2_token_introspect.return_value.data = token_info(exp=int(time.time()) - 5)
        app_client.get("/whoami", headers=AUTH)
        app_client.get("/whoami", headers=AUTH)
        assert fake_client.oauth2_token_introspect.call_count == 2


# --------------------------------------------------------------------------
# get_groups
# --------------------------------------------------------------------------
class TestGetGroups:
    def test_only_active_memberships_returned(self, fake_client):
        resource_server = ga.GroupsClient.resource_server
        fake_client.oauth2_get_dependent_tokens.return_value.by_resource_server = {
            resource_server: {"access_token": "groups-token"}
        }
        groups_response = [
            {
                "id": "g1",
                "my_memberships": [
                    {"status": "active", "identity_id": "i1"},
                    {"status": "invited", "identity_id": "i2"},
                ],
            },
            {"id": "g2", "my_memberships": [{"status": "pending", "identity_id": "i3"}]},
            {"id": "g3"},
        ]
        with mock.patch.object(ga, "GroupsClient") as groups_client_cls, mock.patch.object(ga, "AccessTokenAuthorizer"):
            groups_client_cls.resource_server = resource_server
            groups_client_cls.return_value.get_my_groups.return_value = groups_response
            result = ga.GlobusAuthorizer(app=mock.MagicMock()).get_groups("user-token")

        assert result == [{"group_id": "g1", "identity_id": "i1"}]
