import os
from dotenv import load_dotenv


load_dotenv()

region_name = "us-east-1"

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
    "access_control_policy": "https://esgf2.s3.amazonaws.com/access_control_policy.json",
    "admins": "https://esgf2.s3.amazonaws.com/admins.json",
    "scope_id": "ca49f459-a4f8-420c-b55f-194df11abc0f",
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
    "url": "https://n08bs7a0hc.execute-api.us-east-1.amazonaws.com/dev",
}

event_stream = {
    "config": {
        "bootstrap.servers": "localhost:9092",
        "debug": "all"
    },
    "topic": "esgf2",
}
