from fastapi import FastAPI
from mangum import Mangum
from stac_fastapi.extensions.core.transaction import TransactionExtension
from stac_fastapi.types.config import ApiSettings
from client import TransactionClient
from producer import KafkaProducer
from utils import load_access_control_policy

from settings.local import event_stream, stac_api
# from settings.production import event_stream, stac_api


app = FastAPI(debug=True)

access_control_policy = load_access_control_policy(url=stac_api.get("access_control_policy"))
producer = KafkaProducer(config=event_stream.get("config"))
core_client = TransactionClient(producer=producer, acl=access_control_policy)

settings = ApiSettings(
    api_title="STAC Transaction API",
    api_version="0.1.0",
    openapi_url="/openapi.json",
)
app.state.router_prefix = ""
transaction_extension = TransactionExtension(client=core_client, settings=settings)
transaction_extension.register(app)

handler = Mangum(app, lifespan="off")
