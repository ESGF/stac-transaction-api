import json
import logging
from typing import Optional

import boto3
import urllib3
import urllib3.util
from esgf_playground_utils.models.item import CMIP6Item, ESGFItemProperties
from esgvoc.apps.drs.validator import DrsValidator
from fastapi import HTTPException
from pydantic import HttpUrl, ValidationError

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
    report = json.loads(
        validator.validate_dataset_id(stac_item.get("id", None)).model_dump_json()
    )
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