ESGF_SEARCH_URL = "https://esgf-node.llnl.gov/esg-search/search"
DATA_NODE = "aims3.llnl.gov,esgf-data1.llnl.gov,esgf-data2.llnl.gov"

# ESGF_SEARCH_URL = "https://esgf-node.cels.anl.gov/esg-search/search"
# DATA_NODE = "eagle.alcf.anl.gov"

STAC_CLIENT = {
    "client_id": "ec5f07c0-7ed8-4f2b-94f2-ddb6f8fc91a3",
    "redirect_uri": "https://auth.globus.org/v2/web/auth-code",
}

TOKEN_STORAGE_FILE = "~/.esgf2-publisher.json"

STAC_TRANSACTION_API = {
    "client_id": "6fa3b827-5484-42b9-84db-f00c7a183a6a",
    "access_control_policy": "https://esgf2.s3.amazonaws.com/access_control_policy.json",
    "scope_string": "https://auth.globus.org/scopes/6fa3b827-5484-42b9-84db-f00c7a183a6a/ingest",
    "base_url": "https://stac-transaction-api.esgf-west.org",
}

STAC_API = "https://api.stac.esgf-west.org"
