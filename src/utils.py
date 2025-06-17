import json
import logging
from typing import Optional

import boto3
import jsonschema
import pystac
import urllib3
import urllib3.util
from esgf_playground_utils.models.item import CMIP6Item, ESGFItemProperties
from esgvoc.apps.drs.validator import DrsValidator
from fastapi import HTTPException
from pydantic import HttpUrl, ValidationError
from pystac.validation import stac_validator
from stac_fastapi.types.stac import PartialItem, PatchAddReplaceTest

from settings.transaction import default_extensions

# Setup logger
logger = logging.getLogger(__name__)

# esgvoc CV validator
validator = DrsValidator(project_id="cmip6")


class ESGFItemPropertiesEdited(ESGFItemProperties):
    citation_url: Optional[HttpUrl] = None


class CMIP6ItemEdited(CMIP6Item):
    properties: ESGFItemPropertiesEdited


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


def load_access_control_policy(url):
    parsed = urllib3.util.parse_url(url)
    if parsed.scheme == "file":
        with open(parsed.path) as file:
            print("Access Control Policy loaded")
            return json.load(file)

    http = urllib3.PoolManager()
    response = http.request("GET", url)
    if response.status == 200:
        print("Access Control Policy loaded")
        return json.loads(response.data.decode("utf-8"))
    else:
        return {}


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
        CMIP6ItemEdited(**stac_item)
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
        raise HTTPException(status_code=400, detail=str(error_detail))


def operation_to_partial_item(operations):
    item = {}

    for operation in operations:
        if operation.op == "remove":
            operation = PatchAddReplaceTest(op="add", path=operation.path, value=None)

        if operation.op in ["add", "replace"]:
            path_parts = operation.path.split("/")

            nest = [operation.value] if isinstance(int, path_parts[-1]) else operation.value
            for path_part in reversed(path_parts[1:-1]):
                nest = {path_part: nest}

            item[path_parts[0]] = nest

        if operation.op in ["move", "copy"]:
            # May need to update this for alternat asset updates
            raise HTTPException(status_code=400, detail=f"Operation {operation.op} not permitted")

    return item


def validate_extensions(collection_id: str, item_extensions: list[str]) -> list[str]:
    expected_extensions = default_extensions[collection_id]

    for item_extesion in item_extensions:

        for expected_extension_name, expected_extension in expected_extensions.items():

            if any(regex.match(item_extesion) for regex in expected_extension["regex"]):
                expected_extensions.pop(expected_extension_name)

        raise HTTPException(status_code=400, detail=f"Unexpected extensions: {item_extesion}")

    item_extensions.extend([expected_extension["default"] for expected_extension in expected_extension])

    return item_extensions


def get_null_keys(item: dict) -> tuple[dict, list[str]]:

    null_keys = []
    for k, v in item.model_dump().items():

        if v is None:
            del item[k]
            null_keys.append(k)

        if isinstance(v, dict):
            sub_dict, sub_null_keys = get_null_keys(v)
            null_keys.extend(sub_null_keys)
            item[k] = sub_dict

    return item, null_keys


def validate_patch(event_id: str, request_id: str, item_id: str, item: PartialItem, entensions: list[str]):
    item_dict, null_keys = get_null_keys(item.model_dump())
    item = PartialItem.model_validate(item_dict)

    for extension in entensions:
        try:
            schema = json.loads(pystac.StacIO.default().read_text(extension))
            # This block is cribbed (w/ change in error handling) from
            # jsonschema.validate
            cls = jsonschema.validators.validator_for(schema)
            cls.check_schema(schema)
            extension_validator = cls(schema)

            required_errors = []
            other_errors = []
            for error in extension_validator.iter_errors(item):
                if error.validator != "required":
                    required_errors.append(error)

                else:
                    other_errors.append(error)

        except Exception as e:
            logger.exception(e)
            raise HTTPException(status_code=400, detail=str(e))

        null_key_errors = []
        for required_error in required_errors:
            if required_error.validator_value in null_keys:
                null_key_errors.append(f"Variable {required_error.validator_value} is required and cannot be removed")

        if other_errors or null_key_errors:
            error_detail = {
                "errors": other_errors + null_key_errors,
                "event_id": event_id,
                "item_id": item_id,
                "request_id": request_id,
                "status_code": 400,
                "type": "validation_error",
            }

            logger.error(error_detail)
            raise HTTPException(status_code=400, detail=str(error_detail))
