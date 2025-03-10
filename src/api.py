from fastapi import FastAPI
from fastapi.responses import JSONResponse
from stac_fastapi.extensions.core.transaction import TransactionExtension
from stac_fastapi.types.config import ApiSettings

from authorizer import EGIAuthorizer, GlobusAuthorizer
from client import TransactionClient
from producer import KafkaProducer
from settings.transaction import event_stream, stac_api

app = FastAPI(debug=True)


# Health Check for AWS
@app.get("/healthcheck")
async def healthcheck():
    return JSONResponse(
        content={"healthcheck": True},
        media_type="application/json",
        status_code=200,
    )


producer = KafkaProducer(config=event_stream.get("config"))
core_client = TransactionClient(producer=producer)

settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.1.0",
    openapi_url="/openapi.json",
)

if stac_api.get("authorizer", "globus") == "globus":
    Authorizer = GlobusAuthorizer
else:
    Authorizer = EGIAuthorizer

app.add_middleware(Authorizer)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=settings)
transaction_extension.register(app)
