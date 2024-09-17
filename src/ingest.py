from fastapi import FastAPI
from mangum import Mangum
from stac_fastapi.extensions.core.transaction import TransactionExtension
from stac_fastapi.types.config import ApiSettings
from client import Producer


app = FastAPI(debug=True)


core_client = Producer()

settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.1.0",
    openapi_url="/openapi.json",
)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=settings)
transaction_extension.register(app)

api = Mangum(app, lifespan="off")
