import logging
import os
import socket
from dotenv import load_dotenv


# Suppress some kafka message streams
logger = logging.getLogger("kafka")
logger.setLevel(logging.WARN)

# Paths to the .env.local and local authorization policy file
file_path = os.path.dirname(__file__)
env_path = os.path.join(file_path, ".env.local")
policy_path = os.path.join(
    file_path,
    "config",
    "access_control_policy.json"
)
policy_path = "file://" + policy_path

# Load the .env file
load_dotenv(env_path)

# ESGF2 Globus Project
project_id = "cae45630-2a4b-47b9-b704-d870e341da67"

# ESGF2 STAC Transaction API client
publisher = {
    "client_id": "ec5f07c0-7ed8-4f2b-94f2-ddb6f8fc91a3",
    "redirect_uri": "https://auth.globus.org/v2/web/auth-code",
}

# ESGF2 STAC Transaction API service
stac_api = {
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET"),
    "issuer": "https://auth.globus.org",
    "access_control_policy": policy_path,
    "scope_id": "ca49f459-a4f8-420c-b55f-194df11abc0f",
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
    "url": "0.0.0.0:9000",
}

event_stream = {
    "config": {
        "bootstrap.servers": "host.docker.internal:9092",
        "client.id": socket.gethostname()
    },
    "topic": "esgfng",
}
