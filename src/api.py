import logging

from esgf_core_utils.models.exceptions import RFC9457Exception
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from stac_fastapi.extensions import TransactionExtension
from stac_fastapi.types.config import ApiSettings

from authorizer import Authorizer
from client import TransactionClient
from settings import settings

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

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
        return JSONResponse(
            content={"scope": settings.client.scope},
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


core_client = TransactionClient()

api_settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.1.0",
    openapi_url="/openapi.json",
)


app.add_middleware(Authorizer)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=api_settings)
transaction_extension.register(app)
