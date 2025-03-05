import json
import uuid
from datetime import datetime
from typing import Optional, Union

from esgf_playground_utils.models.item import CMIP6Item, ESGFItemProperties
from esgf_playground_utils.models.kafka import (
    Auth,
    CreatePayload,
    Data,
    KafkaEvent,
    Metadata,
    Publisher,
    RequesterData,
    RevokePayload,
    UpdatePayload,
)
from fastapi import HTTPException, Request, Response, status
from pydantic import HttpUrl
from stac_fastapi.types.core import BaseTransactionsClient, Collection, Item

from settings.transaction import event_stream

from .types import Authorizer


class ESGFItemPropertiesEdited(ESGFItemProperties):
    citation_url: Optional[HttpUrl] = None


class CMIP6ItemEdited(CMIP6Item):
    properties: ESGFItemPropertiesEdited


class TransactionClient(BaseTransactionsClient):

    def __init__(self, producer, acl):
        self.producer = producer
        self.acl = acl

    def allowed_groups(self, properties, acp) -> list:
        if isinstance(acp, list):
            return acp
        for facet, subpolicy in acp.items():
            if hasattr(properties, facet):
                property_value = getattr(properties, facet)
                if isinstance(property_value, str):
                    property_value = [property_value]
                matches = list(set(property_value) & set(subpolicy.keys()))
                for match in matches:
                    groups = self.allowed_groups(properties, subpolicy[match])
                    if groups:
                        return groups
        return []

    def authorize(self, item: Item, request: Request, collection_id: str) -> dict:
        properties = item.properties
        if item.collection != collection_id:
            raise ValueError("Item collection must match path collection_id")
        if getattr(properties, "project", None) != collection_id:
            raise ValueError("Item project must match path collection_id")

        allowed_groups = self.allowed_groups(properties, self.acl)
        # print("allowed groups", json.dumps(allowed_groups))

        allowed_groups_uuid = [g.get("uuid") for g in allowed_groups]
        # print("allowed groups uuid", json.dumps(allowed_groups_uuid))

        authorizer = request.state.authorizer
        access_token_json = authorizer["context"].get("access_token")
        user_groups_json = authorizer["context"].get("groups")
        # print("access token json", access_token_json)
        # print("user groups json", user_groups_json)

        token_info = json.loads(access_token_json)
        user_groups = json.loads(user_groups_json)

        authorized_identities = []
        for group in user_groups:
            if group.get("group_id") in allowed_groups_uuid:
                authorized_identities.append(
                    {
                        "group_id": group.get("group_id"),
                        "identity_id": group.get("identity_id"),
                    }
                )
        if not authorized_identities:
            raise HTTPException(status_code=403, detail="Forbidden")
        print("authorized_identities", json.dumps(authorized_identities))

        identity_set_detail = token_info.get("identity_set_detail", [])
        for identity in identity_set_detail:
            for authorized_identity in authorized_identities:
                if identity.get("sub") == authorized_identity.get("identity_id"):
                    authorized_identity |= {
                        "username": identity.get("username"),
                        "name": identity.get("name"),
                        "email": identity.get("email"),
                        "identity_provider": identity.get("identity_provider"),
                        "identity_provider_display_name": identity.get(
                            "identity_provider_display_name"
                        ),
                        "last_authentication": identity.get("last_authentication"),
                    }
        print("authorized_identities", json.dumps(authorized_identities))

        requester_data = RequesterData(
            sub=token_info.get("sub"),
            user_id=token_info.get("username"),
            identity_provider=identity.get("identity_provider"),
            identity_provider_display_name=identity.get(
                "identity_provider_display_name"
            ),
        )

        auth = Auth(
            auth_policy_id="ESGF-Publish-00012",
            client_id=token_info.get("client_id"),
            requester_data=requester_data,
        )

        return auth

    def egi_authorize(self, item: Item, role: str, request: Request) -> Auth:
        """_summary_

        Args:
            item (Item): item to check authorization for
            role (str): role to check authorization for
            request (Request): current request

        Returns:
            Auth: Auth object if successful
        """
        authorizer: Authorizer = request.state.authorizer
        authorizer.authorize(item, role)

        return Auth(
            client_id=authorizer.client_id,
            requester_data=authorizer.requester_data,
        )

    async def create_item(
        self,
        item: Item,
        request: Request,
        collection_id: str,
    ) -> Optional[Union[Item, Response, None]]:

        auth = self.egi_authorize(item=item, role="CREATE", request=request)

        headers = request.headers.get("headers", {})
        user_agent = headers.get("User-Agent", "/").split("/")

        payload = CreatePayload(method="POST", collection_id=collection_id, item=item)
        data = Data(type="STAC", payload=payload)

        publisher = Publisher(
            package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else ""
        )

        metadata = Metadata(
            auth=auth,
            publisher=publisher,
            schema_version="1.0.0",
            event_id=uuid.uuid4(),
            request_id=headers.get("X-Request-ID", uuid.uuid4()),
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item.id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for publication",
        )

    async def update_item(
        self,
        item: Item,
        request: Request,
        collection_id: str,
        item_id: str,
    ) -> Optional[Union[Item, Response]]:

        auth = self.egi_authorize(item=item, role="UPDATE", request=request)
        headers = request.headers.get("headers", {})
        user_agent = headers.get("User-Agent", "/").split("/")

        payload = UpdatePayload(
            method="PUT", collection_id=collection_id, item_id=item_id, item=item
        )
        data = Data(type="STAC", version="1.0.0", payload=payload)
        publisher = Publisher(
            package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else ""
        )
        metadata = Metadata(
            auth=auth,
            publisher=publisher,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
            event_id=uuid.uuid4(),
            request_id=headers.get("X-Request-ID", uuid.uuid4()),
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item_id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for update",
        )

    async def delete_item(
        self,
        request: Request,
        collection_id: str,
        item_id: str,
    ) -> Optional[Union[Item, Response]]:
        event = request.scope.get("aws.event")
        # Get the item from the database
        # item = await self.get_item(collection_id, item_id)
        # auth = self.authorize(item, event, collection_id)

        user_agent = event.get("headers", {}).get("User-Agent", "/").split("/")

        payload = RevokePayload(
            method="DELETE", collection_id=collection_id, item_id=item_id
        )
        data = Data(type="STAC", version="1.0.0", payload=payload)
        publisher = Publisher(
            package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else ""
        )
        metadata = Metadata(
            auth=Auth(),
            publisher=publisher,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
            event_id="dummy",
            request_id="dummy",
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item_id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for deletion",
        )

    async def create_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("create_collection is not implemented")

    async def update_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("update_collection is not implemented")

    async def delete_collection(self, collection_id: str, **kwargs) -> None:
        raise NotImplementedError("delete_collection is not implemented")
