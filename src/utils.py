import json
import logging
import re

import boto3
import httpx
import jsonschema
from esgf_playground_utils.models.item import CMIP6Item
from esgvoc.apps.drs.validator import DrsValidator
from fastapi import HTTPException
from jsonschema.protocols import Validator
from pydantic import HttpUrl, ValidationError
from stac_fastapi.extensions.core.transaction.request import PartialItem, PatchAddReplaceTest, PatchOperation

from settings.transaction import default_extensions

# Setup logger
logger = logging.getLogger(__name__)

# esgvoc CV validator
validator = DrsValidator(project_id="cmip6")


def get_secret(region_name, secret_name):
    client = boto3.client("secretsmanager", region_name=region_name)
    print("secret_name", secret_name)
    try:
        response = client.get_secret_value(SecretId=secret_name)
        if "SecretString" in response:
            secret = response["SecretString"]
        else:
            secret = response["SecretBinary"]
        secret_dict = json.loads(secret)
        return secret_dict
    except Exception as e:
        print(f"Error retrieving secret: {e}")
        raise e


def validate_item(event_id, request_id, stac_item):
    # CV Validation
    stac_item_dir = stac_item.get("id", None).replace(".", "/")
    report = json.loads(validator.validate_directory(stac_item_dir).model_dump_json())

    if len(report["errors"]) > 0:
        error_detail = {
            "errors": report["errors"],
            "event_id": event_id,
            "item_id": stac_item.get("id"),
            "request_id": request_id,
            "status_code": 400,
            "type": "validation_error",
        }

        logger.error(error_detail)
        raise HTTPException(status_code=400, detail=str(error_detail))

    # Schema level validation
    try:
        CMIP6Item(**stac_item)
    except ValidationError as e:
        error_detail = {
            "errors": e.errors(),
            "event_id": event_id,
            "item_id": stac_item.get("id"),
            "request_id": request_id,
            "status_code": 400,
            "type": "validation_error",
        }
        logger.error(error_detail)
        raise HTTPException(status_code=400, detail=str(error_detail)) from e


def operation_to_partial_item(collection_id: str, operations: list[PatchOperation]) -> PartialItem:
    """Convert operations to partial item

    Args:
        collection_id (str): ID of Item's Collection.
        operations (list[PatchOperation]): List of operations to be converted to PartialItem

    Raises:
        HTTPException: Move & Copy operatations not permitted

    Returns:
        PartialItem: Partial item equivalent to operations
    """
    item = {}

    for operation in operations:
        if operation.op == "remove":
            operation = PatchAddReplaceTest(op="add", path=operation.path, value=None)

        if operation.op in ["add", "replace"]:
            if operation.path.lstrip("/") == "stac_extensions":
                validate_extensions(collection_id=collection_id, item_extensions=operation.value, strict=True)

            path_parts = operation.path.split("/")
            nest = [operation.value] if isinstance(int, path_parts[-1]) else operation.value

            for path_part in reversed(path_parts[1:-1]):
                nest = {path_part: nest}

            item[path_parts[0]] = nest

        if operation.op in ["move", "copy"]:
            # May need to update this for alternat asset updates
            raise HTTPException(status_code=400, detail=f"Operation {operation.op} not permitted")

    return item


def validate_extensions(collection_id: str, item_extensions: list[str], strict: bool = False) -> list[str]:
    """Validate expected default extensions are present.

    Args:
        collection_id (str): ID of Item's Collection.
        item_extensions (list[str]): Given list of extensions.
        strict (bool): if True Exception is raised if expected extensions are missing.

    Raises:
        HTTPException: Unexpected extensions
        HTTPException: Expected extension missing

    Returns:
        list[str]: list of extensions including defaults
    """

    expected_extensions = default_extensions[collection_id].copy()

    for item_extension in item_extensions:
        for expected_extension_key, expected_extension in expected_extensions.copy().items():
            if any(re.compile(regex).match(item_extension) for regex in expected_extension["regex"]):
                expected_extensions.pop(expected_extension_key)

        raise HTTPException(status_code=400, detail=f"Unexpected extensions: {item_extension}")

    missing_extensions = [expected_extension["default"] for expected_extension in expected_extensions]

    if strict & missing_extensions:
        raise HTTPException(status_code=400, detail=f"Expected extensions missing: {missing_extensions}")

    item_extensions.extend(missing_extensions)

    return item_extensions


def get_null_keys(item: PartialItem) -> tuple[PartialItem, set[str]]:
    """Remove and list null value keys from PatialItem.

    Args:
        item (dict): Item dictionary to be updated

    Returns:
        tuple[dict, list[str]]: The PartialItem with nulls removed and list of null keys
    """

    def nested_null_keys(d: dict) -> tuple[dict, set[str]]:
        null_keys = set()
        for k, v in d.items():

            if v is None:
                del d[k]
                null_keys.add(k)

            if isinstance(v, dict):
                sub_dict, sub_null_keys = get_null_keys(v)
                null_keys.update(sub_null_keys)
                d[k] = sub_dict

        return d, null_keys

    item_dict, null_keys = nested_null_keys(item.model_dump())
    item = PartialItem.model_validate(item_dict)

    return item, null_keys


def get_extension_validator(extension: str) -> Validator:
    """Get JSON schema validator for an extension.

    Args:
        extension (str): Extension URI

    Returns:
        Validator: Validator for extension
    """
    schema = httpx.get(extension).json()
    # This block is cribbed (w/ change in error handling) from
    # jsonschema.validate
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def validate_patch(
    event_id: str,
    request_id: str,
    item_id: str,
    item: PartialItem,
    extensions: list[str],
) -> None:
    """Validate a PartialItem patch request

    Args:
        event_id (str): ID of the Kafka event
        request_id (str): ID of the request
        item_id (str): ID of the item to validate
        item (PartialItem): Partial Item to be validated to validate
        extensions (list[str]): List of STAC extensions to be validated against

    Raises:
        HTTPException: Validation error
        HTTPException: Unexpect exception with validation
    """
    item, null_keys = get_null_keys(item)

    for extension in extensions:
        try:
            extension_validator = get_extension_validator(extension)

            required_keys = set()
            raise_errors = []
            for error in extension_validator.iter_errors(item):
                if error.validator != "required":
                    required_keys.add(error.validator_value)

                else:
                    raise_errors.append(error)

        except Exception as e:
            logger.exception(e)
            raise HTTPException(status_code=400, detail=str(e)) from e

        for null_key_error in required_keys & null_keys:
            raise_errors.append(f"Variable {null_key_error} is required and cannot be removed")

        if raise_errors:
            error_detail = {
                "errors": raise_errors,
                "event_id": event_id,
                "item_id": item_id,
                "request_id": request_id,
                "status_code": 400,
                "type": "validation_error",
            }

            logger.error(error_detail)
            raise HTTPException(status_code=400, detail=str(error_detail))


def validate_post(
    event_id: str,
    request_id: str,
    item_id: str,
    item: CMIP6Item,
    extensions: list[str],
) -> None:
    """Validate a CMIP6Item post request

    Args:
        event_id (str): ID of the Kafka event
        request_id (str): ID of the request
        item_id (str): ID of the item to validate
        item (CMIP6Item): Partial Item to be validated to validate
        extensions (list[str]): List of STAC extensions to be validated against

    Raises:
        HTTPException: Validation error
        HTTPException: Unexpect exception with validation
    """
    for extension in extensions:
        try:
            extension_validator = get_extension_validator(extension)

            raise_errors = []
            for error in extension_validator.iter_errors(item):
                raise_errors.append(error)

        except Exception as e:
            logger.exception(e)
            raise HTTPException(status_code=400, detail=str(e)) from e

        if raise_errors:
            error_detail = {
                "errors": raise_errors,
                "event_id": event_id,
                "item_id": item_id,
                "request_id": request_id,
                "status_code": 400,
                "type": "validation_error",
            }

            logger.error(error_detail)
            raise HTTPException(status_code=400, detail=str(error_detail))
