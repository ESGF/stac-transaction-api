import logging
import os
import socket
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Suppress some kafka message streams
logger = logging.getLogger("kafka")
logger.setLevel(logging.WARN)

run_environment = os.environ.get("RUN_ENVIRONMENT", None)

# Path to the local authorization policy file
if run_environment == "local":
    file_path = os.path.dirname(__file__)
    policy_path = os.path.join(
        file_path,
        "config",
        "access_control_policy.json"
    )
    policy_path = "file://" + policy_path
else:
    policy_path = "https://esgf2.s3.amazonaws.com/access_control_policy.json"

# ESGF2 STAC Transaction API service
stac_api = {
    "client_id": os.environ.get("GLOBUS_CLIENT_ID"),
    "client_secret": os.environ.get("GLOBUS_CLIENT_SECRET"),
    "issuer": "https://auth.globus.org",
    "access_control_policy": policy_path,
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
}

# Kafka connection details
if run_environment == "local":
    event_stream = {
        "config": {
            "bootstrap.servers": "host.docker.internal:9092",
            "client.id": socket.gethostname()
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
            "sasl.password": os.environ.get("CONFLUENT_CLOUD_PASSWORD")
        },
        "topic": os.environ.get("TOPIC", "ESGF-NG")
    }
