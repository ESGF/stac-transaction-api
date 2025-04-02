from fastapi import FastAPI
from fastapi.responses import JSONResponse
from stac_fastapi.extensions.core.transaction import TransactionExtension
from stac_fastapi.types.config import ApiSettings

from authorizer import Authorizer
from client import TransactionClient
from producer import KafkaProducer
from settings.transaction import event_stream, stac_api
from utils import load_access_control_policy

app = FastAPI(debug=True)


# Health Check for AWS
@app.get("/healthcheck")
async def healthcheck():
    return JSONResponse(
        content={"healthcheck": True}, media_type="application/json", status_code=200
    )


access_control_policy = load_access_control_policy(
    url=stac_api.get("access_control_policy")
)
producer = KafkaProducer(config=event_stream.get("config"))
core_client = TransactionClient(producer=producer, acl=access_control_policy)

settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.1.0",
    openapi_url="/openapi.json",
)
app.add_middleware(Authorizer)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=settings)
transaction_extension.register(app)
