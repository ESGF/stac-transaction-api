import os

# Set required env vars before any src imports happen.
# These match the TRANSACTION_ prefix and __ delimiter used by Settings.
os.environ.setdefault("TRANSACTION_AUTHORIZER", "globus")
os.environ.setdefault("TRANSACTION_CLIENT__CLIENT_ID", "test-client-id")
os.environ.setdefault("TRANSACTION_CLIENT__CLIENT_SECRET", "test-secret")
os.environ.setdefault("TRANSACTION_CLIENT__ISSUER", "https://auth.globus.org")
os.environ.setdefault("TRANSACTION_CLIENT__SCOPE_STRING", "test-scope")
os.environ.setdefault("TRANSACTION_CLIENT__POLICY_PATH", "file:///dev/null")
os.environ.setdefault("KAFKA_PRODUCER_CONFIG__BOOTSTRAP_SERVERS", "localhost:9092")
os.environ.setdefault("KAFKA_PRODUCER_SUCCESS_TOPIC", "test-topic")
