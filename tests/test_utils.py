"""Unit tests for src/utils.py (validation logic)."""

import json
from unittest import mock

import httpx
import pytest
from esgf_core_utils.models.exceptions import (
    ExpectedExtensionsMissingException,
    ExtensionBelowMinimumException,
    OperationNotPermittedException,
    STACValidationException,
    UnexpectedExtensionException,
)
from stac_fastapi.extensions.transaction.request import PartialItem, PatchOperation
from stac_pydantic.item import Item

import utils

CMIP6 = "https://esgf.github.io/stac-transaction-api/cmip6/v{}/schema.json"
ALT_ASSETS = "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
ALL_CMIP6 = [CMIP6.format("2.0.0"), ALT_ASSETS, FILE_EXT]

POLYGON = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
}


def _response(schema=None, status=200, text=None):
    """Build a fake httpx response for utils.httpx.get."""
    request = httpx.Request("GET", "https://example.org/schema.json")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=schema, request=request)


@pytest.fixture
def schema_get():
    """Patch httpx.get in utils; set .return_value / .side_effect in the test."""
    with mock.patch("utils.httpx.get") as get:
        yield get


# Known bugs in src/utils.py, pinned as strict xfails (they flip to failures,
# prompting removal of the marker, once the bug is fixed).
BUG_STRICT_PRECEDENCE = pytest.mark.xfail(
    strict=True,
    reason="utils.validate_extensions: `strict & len(missing) > 0` parses as "
    "`(strict & len(missing)) > 0`, so strict mode only raises when the number "
    "of missing extensions is odd. Should be `strict and missing_extensions`.",
)
BUG_NULL_KEYS_MUTATION = pytest.mark.xfail(
    strict=True,
    reason="utils.get_null_keys deletes keys from a dict while iterating over "
    "it -> RuntimeError whenever a patch contains a null/removed value.",
)


# --------------------------------------------------------------------------
# validate_extension_version
# --------------------------------------------------------------------------
class TestValidateExtensionVersion:
    def test_equal_version_ok(self):
        utils.validate_extension_version(CMIP6.format("2.0.0"), CMIP6.format("2.0.0"))

    def test_higher_version_ok(self):
        utils.validate_extension_version(CMIP6.format("2.0.0"), CMIP6.format("2.1.0"))

    def test_multi_digit_version_compared_numerically(self):
        # "10.0.0" must be > "9.0.0" (string comparison would get this wrong)
        utils.validate_extension_version(CMIP6.format("9.0.0"), CMIP6.format("10.0.0"))

    def test_lower_version_raises(self):
        with pytest.raises(ExtensionBelowMinimumException) as exc:
            utils.validate_extension_version(CMIP6.format("2.0.0"), CMIP6.format("1.9.9"))
        assert exc.value.status_code == 400
        assert "v2.0.0" in exc.value.detail


# --------------------------------------------------------------------------
# validate_extensions
# --------------------------------------------------------------------------
class TestValidateExtensions:
    def test_defaults_added_when_missing(self):
        result = utils.validate_extensions("CMIP6", [])
        assert sorted(result) == sorted(ALL_CMIP6)

    def test_only_missing_defaults_added(self):
        result = utils.validate_extensions("CMIP6", [CMIP6.format("2.3.0")])
        assert result.count(CMIP6.format("2.3.0")) == 1
        assert ALT_ASSETS in result and FILE_EXT in result
        assert CMIP6.format("2.0.0") not in result

    def test_all_present_returns_unchanged(self):
        given = list(ALL_CMIP6)
        assert utils.validate_extensions("CMIP6", given) == ALL_CMIP6

    def test_unexpected_extension_raises(self):
        with pytest.raises(UnexpectedExtensionException):
            utils.validate_extensions("CMIP6", ["https://example.org/other/v1.0.0/schema.json"])

    def test_unknown_collection_rejects_everything(self):
        with pytest.raises(UnexpectedExtensionException):
            utils.validate_extensions("NOPE", [ALT_ASSETS])

    def test_unknown_collection_with_no_extensions_ok(self):
        assert utils.validate_extensions("NOPE", []) == []

    def test_version_below_minimum_raises(self):
        with pytest.raises(ExtensionBelowMinimumException):
            utils.validate_extensions("CMIP6", [CMIP6.format("1.0.0")])

    def test_strict_missing_all_raises(self):
        # 3 extensions are missing here.
        with pytest.raises(ExpectedExtensionsMissingException):
            utils.validate_extensions("CMIP6", [], strict=True)

    def test_strict_missing_one_raises(self):
        with pytest.raises(ExpectedExtensionsMissingException):
            utils.validate_extensions("CMIP6", [CMIP6.format("2.0.0"), ALT_ASSETS], strict=True)

    @BUG_STRICT_PRECEDENCE
    def test_strict_missing_two_raises(self):
        with pytest.raises(ExpectedExtensionsMissingException):
            utils.validate_extensions("CMIP6", [CMIP6.format("2.0.0")], strict=True)

    def test_strict_all_present_ok(self):
        assert utils.validate_extensions("CMIP6", list(ALL_CMIP6), strict=True) == ALL_CMIP6


# --------------------------------------------------------------------------
# validate_bbox / validate_geometry
# --------------------------------------------------------------------------
class TestBboxAndGeometry:
    @pytest.mark.parametrize(
        "bbox",
        [[-180, -90, 180, 90], [0, 0, 1, 1], [-10.5, -5.5, 10.5, 5.5, 0, 100]],
    )
    def test_valid_bbox(self, bbox):
        utils.validate_bbox(bbox)

    @pytest.mark.parametrize(
        "bbox",
        [
            [-181, 0, 0, 1],
            [0, -91, 1, 0],
            [0, 0, 181, 1],
            [0, 0, 1, 91],
        ],
    )
    def test_invalid_bbox(self, bbox):
        with pytest.raises(STACValidationException) as exc:
            utils.validate_bbox(bbox)
        assert "Bbox is invalid" in exc.value.detail

    def test_valid_geometry(self):
        utils.validate_geometry(POLYGON)

    def test_self_intersecting_geometry_invalid(self):
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
        }
        with pytest.raises(STACValidationException) as exc:
            utils.validate_geometry(bowtie)
        assert "Geometry is invalid" in exc.value.detail

    def test_geometry_outside_wgs84_invalid(self):
        far = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [500, 0], [500, 10], [0, 10], [0, 0]]],
        }
        with pytest.raises(STACValidationException) as exc:
            utils.validate_geometry(far)
        assert "Bbox is invalid" in exc.value.detail


# --------------------------------------------------------------------------
# get_extension_validator
# --------------------------------------------------------------------------
class TestGetExtensionValidator:
    def test_returns_working_validator(self, schema_get):
        schema_get.return_value = _response({"type": "object", "required": ["a"]})
        validator = utils.get_extension_validator("https://example.org/schema.json")
        assert validator.is_valid({"a": 1})
        assert not validator.is_valid({})

    def test_http_status_error(self, schema_get):
        schema_get.return_value = _response({}, status=404)
        with pytest.raises(UnexpectedExtensionException) as exc:
            utils.get_extension_validator("https://example.org/schema.json")
        assert "Error 404" in exc.value.detail

    def test_request_error(self, schema_get):
        schema_get.side_effect = httpx.ConnectError(
            "boom", request=httpx.Request("GET", "https://example.org/schema.json")
        )
        with pytest.raises(UnexpectedExtensionException) as exc:
            utils.get_extension_validator("https://example.org/schema.json")
        assert "An error occurred" in exc.value.detail

    def test_invalid_json(self, schema_get):
        schema_get.return_value = _response(text="{not json")
        with pytest.raises(UnexpectedExtensionException) as exc:
            utils.get_extension_validator("https://example.org/schema.json")
        assert "Failed to decode" in exc.value.detail


# --------------------------------------------------------------------------
# operation_to_partial_item
# --------------------------------------------------------------------------
def _op(**kwargs) -> PatchOperation:
    from pydantic import TypeAdapter

    return TypeAdapter(PatchOperation).validate_python(kwargs)


class TestOperationToPartialItem:
    def test_add_nested_property(self):
        item = utils.operation_to_partial_item(
            "CMIP6", [_op(op="add", path="/properties/title", value="hello")]
        )
        assert item.properties["title"] == "hello"

    def test_replace_nested_property(self):
        item = utils.operation_to_partial_item(
            "CMIP6", [_op(op="replace", path="/properties/title", value="new")]
        )
        assert item.properties["title"] == "new"

    def test_remove_becomes_null(self):
        item = utils.operation_to_partial_item(
            "CMIP6", [_op(op="remove", path="/properties/title")]
        )
        assert item.properties["title"] is None

    def test_multiple_operations_merge(self):
        item = utils.operation_to_partial_item(
            "CMIP6",
            [
                _op(op="add", path="/properties/title", value="t"),
                _op(op="add", path="/bbox", value=[0, 0, 1, 1]),
            ],
        )
        assert item.properties["title"] == "t"
        assert list(item.bbox) == [0, 0, 1, 1]

    @pytest.mark.parametrize("op", ["move", "copy"])
    def test_move_and_copy_not_permitted(self, op):
        operation = _op(op=op, path="/properties/a", **{"from": "/properties/b"})
        with pytest.raises(OperationNotPermittedException):
            utils.operation_to_partial_item("CMIP6", [operation])

    @BUG_STRICT_PRECEDENCE
    def test_stac_extensions_op_is_validated_strictly(self):
        # Missing the default alternate-assets / file extensions -> strict error
        with pytest.raises(ExpectedExtensionsMissingException):
            utils.operation_to_partial_item(
                "CMIP6",
                [_op(op="replace", path="/stac_extensions", value=[CMIP6.format("2.0.0")])],
            )

    def test_stac_extensions_op_with_all_extensions_ok(self):
        item = utils.operation_to_partial_item(
            "CMIP6",
            [_op(op="replace", path="/stac_extensions", value=list(ALL_CMIP6))],
        )
        assert sorted(item.stac_extensions) == sorted(ALL_CMIP6)


# --------------------------------------------------------------------------
# get_null_keys
# --------------------------------------------------------------------------
class TestGetNullKeys:
    def test_no_nulls(self):
        item = PartialItem.model_validate({"properties": {"a": 1}})
        result, nulls = utils.get_null_keys(item)
        assert nulls == set()
        assert result.properties["a"] == 1

    @BUG_NULL_KEYS_MUTATION
    def test_nested_null_removed_and_reported(self):
        item = PartialItem.model_validate({"properties": {"a": 1, "b": None}})
        result, nulls = utils.get_null_keys(item)
        assert "b" in nulls
        assert "b" not in (result.properties or {})
        assert result.properties["a"] == 1


# --------------------------------------------------------------------------
# validate_post
# --------------------------------------------------------------------------
def _item(**overrides) -> Item:
    data = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": "item-1",
        "collection": "CMIP6",
        "geometry": POLYGON,
        "bbox": [0, 0, 10, 10],
        "properties": {"datetime": "2024-01-01T00:00:00Z", "title": "x"},
        "links": [],
        "assets": {},
        "stac_extensions": [],
    }
    data.update(overrides)
    return Item.model_validate(data)


class TestValidatePost:
    def test_valid_item_passes(self, schema_get):
        schema_get.return_value = _response({"type": "object"})
        utils.validate_post("item-1", _item(), ["https://example.org/ext.json"])

    def test_no_extensions_passes(self):
        utils.validate_post("item-1", _item(), [])

    def test_invalid_geometry_raises(self):
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
        }
        with pytest.raises(STACValidationException):
            utils.validate_post("item-1", _item(geometry=bowtie), [])

    def test_invalid_bbox_raises(self):
        with pytest.raises(STACValidationException):
            utils.validate_post("item-1", _item(bbox=[0, 0, 500, 10]), [])

    def test_schema_failure_has_helpful_detail(self, schema_get):
        schema_get.return_value = _response(
            {
                "type": "object",
                "properties": {
                    "properties": {"type": "object", "required": ["experiment_id"]}
                },
            }
        )
        with pytest.raises(STACValidationException) as exc:
            utils.validate_post("item-1", _item(), ["https://example.org/ext.json"])
        detail = exc.value.detail
        assert "item-1" in detail
        assert "https://example.org/ext.json" in detail
        assert "experiment_id" in detail

    def test_oneof_failure_reports_root_cause(self, schema_get):
        schema_get.return_value = _response(
            {"oneOf": [{"required": ["nope1"]}, {"required": ["nope2"]}]}
        )
        with pytest.raises(STACValidationException) as exc:
            utils.validate_post("item-1", _item(), ["https://example.org/ext.json"])
        assert "nope1" in exc.value.detail


# --------------------------------------------------------------------------
# validate_patch
# --------------------------------------------------------------------------
class TestValidatePatch:
    def test_valid_patch_passes(self, schema_get):
        schema_get.return_value = _response({"type": "object"})
        patch = PartialItem.model_validate({"properties": {"title": "t"}})
        utils.validate_patch("item-1", patch, ["https://example.org/ext.json"])

    def test_invalid_geometry_raises(self):
        bowtie = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]],
        }
        patch = PartialItem.model_validate({"geometry": bowtie})
        with pytest.raises(STACValidationException):
            utils.validate_patch("item-1", patch, [])

    def test_invalid_bbox_raises(self):
        patch = PartialItem.model_validate({"bbox": [0, 0, 500, 10]})
        with pytest.raises(STACValidationException):
            utils.validate_patch("item-1", patch, [])

    def test_type_error_in_schema_raises(self, schema_get):
        schema_get.return_value = _response(
            {
                "type": "object",
                "properties": {
                    "properties": {
                        "type": "object",
                        "properties": {"title": {"type": "integer"}},
                    }
                },
            }
        )
        patch = PartialItem.model_validate({"properties": {"title": "not-an-int"}})
        with pytest.raises(STACValidationException):
            utils.validate_patch("item-1", patch, ["https://example.org/ext.json"])

    def test_missing_required_not_enforced_on_partial_item(self, schema_get):
        # A patch need not contain every required property.
        schema_get.return_value = _response(
            {
                "type": "object",
                "properties": {
                    "properties": {"type": "object", "required": ["experiment_id"]}
                },
            }
        )
        patch = PartialItem.model_validate({"properties": {"title": "t"}})
        utils.validate_patch("item-1", patch, ["https://example.org/ext.json"])

    @BUG_NULL_KEYS_MUTATION
    def test_removing_required_property_raises(self, schema_get):
        schema_get.return_value = _response(
            {
                "type": "object",
                "properties": {
                    "properties": {"type": "object", "required": ["experiment_id"]}
                },
            }
        )
        patch = PartialItem.model_validate({"properties": {"experiment_id": None}})
        with pytest.raises(STACValidationException):
            utils.validate_patch("item-1", patch, ["https://example.org/ext.json"])
