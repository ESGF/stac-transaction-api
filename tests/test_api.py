import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestAPI(unittest.TestCase):
    def test_api__healthcheck(self):
        with patch("client.KafkaProducer", MagicMock()):
            from api import app
            client = TestClient(app)
            response = client.get("/healthcheck")
            content = json.loads(response.content.decode("utf-8"))

            assert response.status_code == 200
            assert response.headers["Content-Type"] == "application/json"
            assert content == {"healthcheck": True}
