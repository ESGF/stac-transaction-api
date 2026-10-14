import logging
import uuid

import requests
from esgf_core_utils.models.exceptions import (
    InvalidTokenAudienceException,
    RFC9457Exception,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from stac_fastapi.extensions import TransactionExtension
from stac_fastapi.types.config import ApiSettings

from authorizer import Authorizer
from client import TransactionClient
from settings import settings

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)


class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        return "/healthcheck" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())

app = FastAPI(debug=settings.debug)


# Health Check for AWS
@app.get("/healthcheck")
async def healthcheck():
    return JSONResponse(
        content={"healthcheck": True},
        media_type="application/json",
        status_code=200,
    )


if settings.authorizer == "egi":

    @app.get("/scope")
    async def scope():
        scope_settings = settings.client.scope
        scopes = scope_settings.default

        if scope_settings.client_id:
            with requests.Session() as session:
                token_response = session.post(
                    scope_settings.token_url,
                    auth=(scope_settings.client_id, scope_settings.client_secret),
                    data={"grant_type": "client_credentials"},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                token_response.raise_for_status()
                token = token_response.json()

                group_response = session.get(
                    scope_settings.group_url,
                    headers={"Authorization": f"Bearer {token['access_token']}"},
                )

                group_response.raise_for_status()
                groups = group_response.json()

            esgf_vo = next(
                g for g in groups["results"] if g["name"] == "esgf.vo.egi.eu"
            )

            subgroups = {
                g["name"]: g["extraSubGroups"] for g in esgf_vo["extraSubGroups"]
            }

            groups = subgroups["node"] + subgroups["project"]

            scopes = ["offline"] + [
                scope_settings.template.format(
                    group=g["path"].replace("/", ":"), role=r
                )
                for g in groups
                if g["name"] != "*"
                for r in ("CREATE", "REPLICATE")
            ]

        return JSONResponse(
            content={"scope": scopes},
            media_type="application/json",
            status_code=200,
        )


@app.exception_handler(RFC9457Exception)
async def rfc9457_handler(request: Request, exc: RFC9457Exception):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "type": exc.type,
            "title": exc.title,
            "detail": exc.detail,
            "instance": exc.instance,
        },
    )


@app.exception_handler(InvalidTokenAudienceException)
async def invalid_token_audience_handler(
    request: Request, exc: InvalidTokenAudienceException
):
    event_id = uuid.uuid4().hex
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status_code": exc.status_code,
            "type": exc.type,
            "title": exc.title,
            "detail": exc.detail,
            "instance": f"{request_id}:{event_id}",
        },
    )


core_client = TransactionClient()

api_settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.2.0",
    openapi_url="/openapi.json",
)


app.add_middleware(Authorizer)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=api_settings)
transaction_extension.register(app)
