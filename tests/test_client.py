"""Unit tests for src/client.py (TransactionClient)."""

import json
from unittest import mock

import pytest
from esgf_core_utils.models.exceptions import (
    AuthorizationException,
    ExpectedExtensionsMissingException,
    ExtensionBelowMinimumException,
    MissingPermissionException,
    OperationNotPermittedException,
    RFC9457Exception,
    STACValidationException,
    UnexpectedExtensionException,
    UnknownException,
)
from stac_fastapi.extensions.transaction.request import PartialItem
from stac_pydantic.item import Item

import client as client_module
from client import TransactionClient

REQUESTER = {"client_id": "cid", "iss": "https://auth.example.org", "sub": "user-1"}

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
}


@pytest.fixture
def tc():
    """TransactionClient with a mocked Kafka producer."""
    instance = TransactionClient()
    instance.producer = mock.MagicMock()
    return instance


@pytest.fixture
def request_obj():
    """Fake FastAPI request with an authorizer on request.state."""
    req = mock.MagicMock()
    req.headers = {"x-request-id": "req-123", "user-agent": "my-client/1.2.3"}
    req.state.authorizer.requester_data.model_dump.return_value = REQUESTER
    return req


@pytest.fixture
def item():
    return Item.model_validate(
        {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": "item-1",
            "collection": "CMIP6",
            "geometry": POLYGON,
            "bbox": [0, 0, 10, 10],
            "properties": {"datetime": "2024-01-01T00:00:00Z"},
            "links": [],
            "assets": {},
            "stac_extensions": [],
        }
    )


@pytest.fixture
def valid(monkeypatch):
    """Make extension/schema validation a no-op (covered in test_utils.py)."""
    monkeypatch.setattr(client_module, "validate_extensions", lambda collection_id, item_extensions, **kw: item_extensions)
    monkeypatch.setattr(client_module, "validate_post", mock.MagicMock())
    monkeypatch.setattr(client_module, "validate_patch", mock.MagicMock())


def _produced_event(tc) -> tuple[str, dict]:
    kwargs = tc.producer.success.call_args.kwargs
    return kwargs["key"], json.loads(kwargs["value"])


# --------------------------------------------------------------------------
# authorize
# --------------------------------------------------------------------------
class TestAuthorize:
    def test_returns_auth_with_requester_data(self, tc, request_obj, item):
        auth = tc.authorize(
            collection_id="CMIP6",
            item=item,
            role="CREATE",
            request=request_obj,
            request_id="r",
            event_id="e",
        )
        assert auth.requester_data.model_dump() == REQUESTER
        request_obj.state.authorizer.authorize.assert_called_once_with(
            collection_id="CMIP6", item=item, role="CREATE", request_id="r", event_id="e"
        )

    def test_permission_error_propagates(self, tc, request_obj, item):
        request_obj.state.authorizer.authorize.side_effect = MissingPermissionException("collection", "CMIP6")
        with pytest.raises(MissingPermissionException):
            tc.authorize(
                collection_id="CMIP6",
                item=item,
                role="CREATE",
                request=request_obj,
                request_id="r",
                event_id="e",
            )


# --------------------------------------------------------------------------
# create_item
# --------------------------------------------------------------------------
class TestCreateItem:
    async def test_success_publishes_event(self, tc, request_obj, item, valid):
        response = await tc.create_item("CMIP6", item, request_obj)

        assert response.status_code == 202
        tc.producer.success.assert_called_once()
        key, event = _produced_event(tc)
        assert key == "item-1"
        assert event["data"]["payload"]["method"] == "POST"
        assert event["data"]["payload"]["collection_id"] == "CMIP6"
        assert event["data"]["payload"]["item"]["id"] == "item-1"
        assert event["metadata"]["request_id"] == "req-123"
        assert event["metadata"]["publisher"] == {"package": "my-client", "version": "1.2.3"}

    async def test_generates_request_id_when_header_absent(self, tc, request_obj, item, valid):
        request_obj.headers = {}
        await tc.create_item("CMIP6", item, request_obj)
        _, event = _produced_event(tc)
        assert len(event["metadata"]["request_id"]) == 32  # uuid4 hex

    async def test_user_agent_without_version(self, tc, request_obj, item, valid):
        request_obj.headers = {"user-agent": "curl"}
        await tc.create_item("CMIP6", item, request_obj)
        _, event = _produced_event(tc)
        assert event["metadata"]["publisher"] == {"package": "curl", "version": ""}

    async def test_missing_permission_becomes_authorization_error(self, tc, request_obj, item, valid):
        request_obj.state.authorizer.authorize.side_effect = MissingPermissionException("collection", "CMIP6")
        with pytest.raises(AuthorizationException) as exc:
            await tc.create_item("CMIP6", item, request_obj)
        assert exc.value.status_code == 403
        assert exc.value.instance.startswith("req-123:")
        tc.producer.success.assert_not_called()

    @pytest.mark.parametrize(
        "error",
        [
            lambda: ExpectedExtensionsMissingException(extensions=["x"]),
            lambda: OperationNotPermittedException(op="move"),
            lambda: STACValidationException(),
            lambda: UnexpectedExtensionException(extension="x"),
            lambda: ExtensionBelowMinimumException(extension="x", minimum_version="v1.0.0"),
        ],
        ids=["missing", "op", "stac", "unexpected", "below-min"],
    )
    async def test_validation_errors_become_400_rfc9457(self, tc, request_obj, item, valid, monkeypatch, error):
        original = error()
        monkeypatch.setattr(client_module, "validate_post", mock.MagicMock(side_effect=original))

        with pytest.raises(RFC9457Exception) as exc:
            await tc.create_item("CMIP6", item, request_obj)

        assert exc.value.status_code == 400
        assert exc.value.detail == original.detail
        assert exc.value.title == original.title
        assert exc.value.instance.startswith("req-123:")
        assert exc.value.__cause__ is original
        tc.producer.success.assert_not_called()

    async def test_extension_validation_error_also_mapped(self, tc, request_obj, item, valid, monkeypatch):
        monkeypatch.setattr(
            client_module,
            "validate_extensions",
            mock.MagicMock(side_effect=UnexpectedExtensionException(extension="bad")),
        )
        with pytest.raises(RFC9457Exception) as exc:
            await tc.create_item("CMIP6", item, request_obj)
        assert exc.value.status_code == 400

    async def test_default_extensions_passed_to_validate_post(self, tc, request_obj, item, monkeypatch):
        defaults = ["https://example.org/a", "https://example.org/b"]
        monkeypatch.setattr(client_module, "validate_extensions", lambda **kw: defaults)
        post = mock.MagicMock()
        monkeypatch.setattr(client_module, "validate_post", post)

        await tc.create_item("CMIP6", item, request_obj)

        post.assert_called_once_with(item_id="item-1", item=item, extensions=defaults)

    async def test_kafka_failure_becomes_unknown_exception(self, tc, request_obj, item, valid):
        tc.producer.success.side_effect = RuntimeError("kafka down")
        with pytest.raises(UnknownException) as exc:
            await tc.create_item("CMIP6", item, request_obj)
        assert exc.value.status_code == 500
        assert exc.value.instance.startswith("req-123:")


# --------------------------------------------------------------------------
# patch_item
# --------------------------------------------------------------------------
class TestPatchItem:
    async def test_partial_item_success(self, tc, request_obj, valid):
        patch = PartialItem.model_validate({"properties": {"title": "new"}})
        response = await tc.patch_item("CMIP6", "item-1", patch, request_obj)

        assert response.status_code == 202
        key, event = _produced_event(tc)
        assert key == "item-1"
        assert event["data"]["payload"]["method"] == "PATCH"
        assert event["data"]["payload"]["item_id"] == "item-1"
        assert event["data"]["payload"]["patch"]["properties"]["title"] == "new"

    async def test_json_patch_operations_success(self, tc, request_obj, valid):
        from pydantic import TypeAdapter
        from stac_fastapi.extensions.transaction.request import PatchOperation

        op = TypeAdapter(PatchOperation).validate_python({"op": "add", "path": "/properties/title", "value": "t"})
        response = await tc.patch_item("CMIP6", "item-1", [op], request_obj)

        assert response.status_code == 202
        _, event = _produced_event(tc)
        # The original operations (not the merged item) are published.
        assert event["data"]["payload"]["patch"][0]["op"] == "add"
        assert event["data"]["payload"]["patch"][0]["path"] == "/properties/title"

    async def test_move_operation_rejected_before_publish(self, tc, request_obj, valid):
        from pydantic import TypeAdapter
        from stac_fastapi.extensions.transaction.request import PatchOperation

        op = TypeAdapter(PatchOperation).validate_python({"op": "move", "path": "/properties/a", "from": "/properties/b"})
        with pytest.raises(OperationNotPermittedException):
            await tc.patch_item("CMIP6", "item-1", [op], request_obj)
        tc.producer.success.assert_not_called()

    async def test_validation_error_becomes_400_rfc9457(self, tc, request_obj, valid, monkeypatch):
        original = STACValidationException()
        monkeypatch.setattr(client_module, "validate_patch", mock.MagicMock(side_effect=original))
        patch = PartialItem.model_validate({"properties": {"title": "new"}})

        with pytest.raises(RFC9457Exception) as exc:
            await tc.patch_item("CMIP6", "item-1", patch, request_obj)

        assert exc.value.status_code == 400
        assert exc.value.detail == original.detail
        tc.producer.success.assert_not_called()

    async def test_authorization_uses_update_role(self, tc, request_obj, valid):
        patch = PartialItem.model_validate({"properties": {"title": "new"}})
        await tc.patch_item("CMIP6", "item-1", patch, request_obj)
        assert request_obj.state.authorizer.authorize.call_args.kwargs["role"] == "UPDATE"

    async def test_kafka_failure_becomes_unknown_exception(self, tc, request_obj, valid):
        tc.producer.success.side_effect = RuntimeError("kafka down")
        patch = PartialItem.model_validate({"properties": {"title": "new"}})
        with pytest.raises(UnknownException):
            await tc.patch_item("CMIP6", "item-1", patch, request_obj)

    @pytest.mark.xfail(
        strict=True,
        reason="patch_item reads headers via request.headers.get('headers', {}) "
        "(a header literally named 'headers'), so X-Request-ID and User-Agent "
        "are ignored; create_item reads request.headers directly.",
    )
    async def test_request_id_and_user_agent_taken_from_request_headers(self, tc, request_obj, valid):
        request_obj.headers = {"X-Request-ID": "req-abc", "user-agent": "my-client/1.2.3"}
        patch = PartialItem.model_validate({"properties": {"title": "new"}})
        await tc.patch_item("CMIP6", "item-1", patch, request_obj)
        _, event = _produced_event(tc)
        assert event["metadata"]["request_id"] == "req-abc"
        assert event["metadata"]["publisher"]["package"] == "my-client"


# --------------------------------------------------------------------------
# unimplemented operations
# --------------------------------------------------------------------------
class TestNotImplemented:
    @pytest.mark.parametrize(
        "method,args",
        [
            ("update_item", ("CMIP6", "item-1", None, None)),
            ("delete_item", ("CMIP6", "item-1", None)),
        ],
    )
    async def test_item_methods(self, tc, method, args):
        with pytest.raises(NotImplementedError):
            await getattr(tc, method)(*args)

    @pytest.mark.parametrize(
        "method,args",
        [
            ("create_collection", (None,)),
            ("patch_collection", (None,)),
            ("update_collection", (None,)),
            ("delete_collection", ("CMIP6",)),
        ],
    )
    async def test_collection_methods(self, tc, method, args):
        with pytest.raises(NotImplementedError):
            await getattr(tc, method)(*args)
