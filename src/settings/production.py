import os
from dotenv import load_dotenv
from utils import get_secret


load_dotenv()

region_name = "us-east-1"

# ESGF2 Globus Project
project_id = "cae45630-2a4b-47b9-b704-d870e341da67"

# ESGF2 STAC Transaction API client
publisher = {
    "client_id": "ec5f07c0-7ed8-4f2b-94f2-ddb6f8fc91a3",
    "redirect_uri": "https://auth.globus.org/v2/web/auth-code",
}

globus_auth_secret_name = os.environ.get("GLOBUS_AUTH_SECRET_NAME")
globus_auth_secret = get_secret(region_name, globus_auth_secret_name)

# ESGF2 STAC Transaction API service
stac_api = {
    "client_id": "6fa3b827-5484-42b9-84db-f00c7a183a6a",
    "client_secret": globus_auth_secret.get("client_secret"),
    "issuer": "https://auth.globus.org",
    "access_control_policy": "https://esgf2.s3.amazonaws.com/access_control_policy.json",
    "admins": "https://esgf2.s3.amazonaws.com/admins.json",
    "scope_id": "ca49f459-a4f8-420c-b55f-194df11abc0f",
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
    "url": "https://n08bs7a0hc.execute-api.us-east-1.amazonaws.com/dev",
}

# ESGF2 Event Stream Service
amazon_msk_secret_name = os.environ.get("CONFLUENT_CLOUD_SECRET_NAME")
sasl_secret = get_secret(region_name, amazon_msk_secret_name)

event_stream = {
    "config": {
        "bootstrap.servers": "pkc-p11xm.us-east-1.aws.confluent.cloud:9092",
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "SCRAM-SHA-512",
        "sasl.username": sasl_secret.get("username"),
        "sasl.password": sasl_secret.get("password")
    },
    "topic": "esgfng"
}

if os.environ.get("PRODUCER_DEBUG").lower() == "true":
    event_stream["config"]["debug"] = "all"
    event_stream["config"]["log_level"] = 7
