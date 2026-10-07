"""Shared pytest configuration.

Settings are populated with fake values *before* any application module is
imported, and the Kafka producer is mocked, so tests never touch real
credentials, ``.env`` files, or the network.
"""

import os
import sys
from pathlib import Path
from unittest import mock

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

_TEST_ENV = {
    "TRANSACTION_AUTHORIZER": "globus",
    "TRANSACTION_CLIENT__CLIENT_ID": "test-client-id",
    "TRANSACTION_CLIENT__CLIENT_SECRET": "test-client-secret",
    "TRANSACTION_CLIENT__ISSUER": "https://auth.example.org",
    "TRANSACTION_CLIENT__SCOPE_STRING": "test-scope",
    "TRANSACTION_CLIENT__POLICY_PATH": f"file://{SRC}/settings/config/access_control_policy.txt",
    "KAFKA_PRODUCER_CONFIG__BOOTSTRAP_SERVERS": "localhost:9092",
    "KAFKA_PRODUCER_CONFIG__SASL_USERNAME": "test-user",
    "KAFKA_PRODUCER_CONFIG__SASL_PASSWORD": "test-password",
    "KAFKA_PRODUCER_SUCCESS_TOPIC": "esgf.test",
}
os.environ.update(_TEST_ENV)

# Never create a real Kafka connection when KafkaProducer() is instantiated.
mock.patch("esgf_core_utils.models.kafka.producer.Producer", mock.MagicMock()).start()


# --- async test support: run `async def` tests on a fresh event loop -------------
import asyncio  # noqa: E402
import inspect  # noqa: E402

import pytest  # noqa: E402


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    if inspect.iscoroutinefunction(pyfuncitem.obj):
        kwargs = {name: pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
        asyncio.run(pyfuncitem.obj(**kwargs))
        return True
