import json
import unittest

from fastapi.testclient import TestClient

from api import app


class TestAPI(unittest.TestCase):
    def test_api__healthcheck(self):
        client = TestClient(app)
        response = client.get("/healthcheck")
        content = json.loads(response.content.decode("utf-8"))

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"
        assert content == {"healthcheck": True}


class TestExceptionHandlers(unittest.TestCase):
    """Call the registered exception handlers directly (no auth middleware)."""

    @staticmethod
    def _request(headers=None):
        from unittest import mock

        req = mock.MagicMock()
        req.headers = headers or {}
        return req

    def test_rfc9457_handler(self):
        import asyncio

        from esgf_core_utils.models.exceptions import RFC9457Exception

        import api

        exc = RFC9457Exception()
        exc.status_code = 400
        exc.type = "https://example.org/problem"
        exc.title = "Bad"
        exc.detail = "details"
        exc.instance = "req:evt"

        response = asyncio.run(api.rfc9457_handler(self._request(), exc))

        assert response.status_code == 400
        assert json.loads(response.body) == {
            "status_code": 400,
            "type": "https://example.org/problem",
            "title": "Bad",
            "detail": "details",
            "instance": "req:evt",
        }

    def test_invalid_token_audience_handler_uses_request_id(self):
        import asyncio

        from esgf_core_utils.models.exceptions import InvalidTokenAudienceException

        import api

        exc = InvalidTokenAudienceException(token_audience="a", expected_audience="b")
        response = asyncio.run(api.invalid_token_audience_handler(self._request({"x-request-id": "req-9"}), exc))

        body = json.loads(response.body)
        assert response.status_code == 401
        assert body["instance"].startswith("req-9:")
        assert body["detail"] == exc.detail

    def test_invalid_token_audience_handler_generates_request_id(self):
        import asyncio

        from esgf_core_utils.models.exceptions import InvalidTokenAudienceException

        import api

        exc = InvalidTokenAudienceException(token_audience="a", expected_audience="b")
        response = asyncio.run(api.invalid_token_audience_handler(self._request(), exc))

        request_id, event_id = json.loads(response.body)["instance"].split(":")
        assert len(request_id) == len(event_id) == 32

    def test_healthcheck_filter_hides_healthcheck_access_logs(self):
        import logging

        import api

        f = api.HealthCheckFilter()
        make = lambda msg: logging.LogRecord("n", logging.INFO, "p", 1, msg, None, None)  # noqa: E731
        assert f.filter(make('GET /healthcheck HTTP/1.1" 200')) is False
        assert f.filter(make('GET /collections HTTP/1.1" 200')) is True
