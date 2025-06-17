import json
import logging
import os
import socket

import urllib3
from dotenv import load_dotenv


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


# Load the .env file
load_dotenv()

# Suppress some kafka message streams
logger = logging.getLogger("kafka")
logger.setLevel(logging.WARN)

run_environment = os.environ.get("RUN_ENVIRONMENT", None)

# Path to the local authorization policy file
if run_environment == "local":
    file_path = os.path.dirname(__file__)
    policy_path = os.path.join(file_path, "config", "access_control_policy.json")
    policy_path = "file://" + policy_path
else:
    policy_path = "https://esgf2.s3.amazonaws.com/access_control_policy.json"

# ESGF2 STAC Transaction API service
stac_api = {
    "client_id": os.environ.get("GLOBUS_CLIENT_ID"),
    "client_secret": os.environ.get("GLOBUS_CLIENT_SECRET"),
    "issuer": "https://auth.globus.org",
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
    "authorizer": "globus",
}

access_control_policy = load_access_control_policy(url=policy_path)

# Kafka connection details
if run_environment == "local":
    event_stream = {
        "config": {
            "bootstrap.servers": "host.docker.internal:9092",
            "client.id": socket.gethostname(),
        },
        "topic": "esgf-local",
    }
else:
    event_stream = {
        "config": {
            "bootstrap.servers": os.environ.get("BOOTSTRAP_SERVERS"),
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": os.environ.get("CONFLUENT_CLOUD_USERNAME"),
            "sasl.password": os.environ.get("CONFLUENT_CLOUD_PASSWORD"),
        },
        "topic": os.environ.get("TOPIC", "esgf.ng"),
    }

default_extensions = {
    "CMIP6": {
        "CMIP6": {
            "regex": ["https://stac-extensions.github.io/cmip6/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/cmip6/v1.0.0/schema.json",
        },
        "alternate_assets": {
            "regex": ["https://stac-extensions.github.io/alternate-assets/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
        },
        "file": {
            "regex": ["https://stac-extensions.github.io/file/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
        },
    },
    "CMIP7": {
        "CMIP7": {
            "regex": ["https://stac-extensions.github.io/cmip7/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/cmip7/v1.0.0/schema.json",
        },
        "alternate_assets": {
            "regex": ["https://stac-extensions.github.io/alternate-assets/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
        },
        "file": {
            "regex": ["https://stac-extensions.github.io/file/v[0-9].[0-9].[0-9]/schema.json"],
            "default": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
        },
    },
}
