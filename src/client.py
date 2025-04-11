import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Union

from fastapi import HTTPException, Request, Response, status
from stac_fastapi.types.core import BaseTransactionsClient, Collection, Item

from settings.transaction import event_stream
from utils import validate_item

# Setup logger
logger = logging.getLogger(__name__)


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
        allowed_groups_uuid = [g.get("uuid") for g in allowed_groups]

        authorizer = request.state.authorizer
        access_token_json = authorizer["context"].get("access_token")
        user_groups_json = authorizer["context"].get("groups")

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

        auth = {
            "requester_data": {
                "client_id": token_info.get("client_id"),
                "iss": token_info.get("iss"),
                "sub": token_info.get("sub"),
            },
            "auth_basis_data": {
                "authorization_basis_type": "group",
                "authorization_basis_service": "groups.globus.org",
                "authorization_basis": authorized_identities,
            },
        }

        return auth

    async def create_item(
        self,
        item: Item,
        request: Request,
        collection_id: str,
    ) -> Optional[Union[Item, Response, None]]:
        # Authz/Authn
        auth = self.authorize(item, request, collection_id)

        # Make sure the item passes validation
        event_id = uuid.uuid4()
        request_id = uuid.uuid4()
        stac_item = await request.json()
        validate_item(event_id, request_id, stac_item)

        # Move on if auth and validation pass
        user_agent = (
            request.headers.get("headers", {}).get("User-Agent", "/").split("/")
        )

        message = {
            "metadata": {
                "auth": auth,
                "event_id": event_id,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "request_id": request_id,
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "payload": {
                    "method": "POST",
                    "collection_id": collection_id,
                    "item": stac_item,
                },
            },
        }

        try:
            self.producer.produce(
                topic=event_stream.get("topic", "esgf-local"),
                key=item.id.encode("utf-8"),
                value=json.dumps(message, default=str).encode("utf-8"),
            )
        except Exception as e:
            logger.error(f"Error producing message: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for publication",
        )

    async def update_item(
        self,
        item: Item,
        request: Request,
        collection_id: str
    ) -> Optional[Union[Item, Response]]:
        # Authz/Authn
        auth = self.authorize(item, request, collection_id)

        # Make sure the item passes validation
        event_id = uuid.uuid4()
        request_id = uuid.uuid4()
        stac_item = await request.json()
        validate_item(event_id, request_id, stac_item)

        # Move on if auth and validation pass
        user_agent = (
            request.headers.get("headers", {}).get("User-Agent", "/").split("/")
        )

        message = {
            "metadata": {
                "auth": auth,
                "event_id": event_id,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "request_id": request_id,
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "version": "1.0.0",
                "payload": {
                    "method": "PUT",
                    "collection_id": collection_id,
                    "item": stac_item,
                },
            },
        }

        try:
            self.producer.produce(
                topic=event_stream.get("topic", "esgf-local"),
                key=item.id.encode("utf-8"),
                value=json.dumps(message, default=str).encode("utf-8"),
            )
        except Exception as e:
            logger.error(f"Error producing message: {e}")
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for update",
        )

    async def delete_item(
        self,
        request: Request,
        collection_id: str,
        item: str,
    ) -> Optional[Union[Item, Response]]:
        # Authz/Authn
        self.authorize(item, request, collection_id)

        # Make sure the item passes validation
        event_id = uuid.uuid4()
        request_id = uuid.uuid4()

        # Move on if auth and validation pass
        user_agent = (
            request.headers.get("headers", {}).get("User-Agent", "/").split("/")
        )

        message = {
            "metadata": {
                "auth": None,  # auth,
                "event_id": event_id,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "request_id": request_id,
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "version": "1.0.0",
                "payload": {
                    "method": "DELETE",
                    "collection_id": collection_id,
                    "item_id": item.id,
                },
            },
        }

        self.producer.produce(
            None,
            json.dumps(message, default=str).encode("utf-8"),
        )
        return Response(
            content="Item queued for deletion",
            status_code=status.HTTP_202_ACCEPTED,
        )

    async def create_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("create_collection is not implemented")

    async def update_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("update_collection is not implemented")

    async def delete_collection(self, collection_id: str, **kwargs) -> None:
        raise NotImplementedError("delete_collection is not implemented")
