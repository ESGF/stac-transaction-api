import json
from settings.config.CMIP6ItemModel import CMIP6Item
from datetime import datetime
from fastapi import HTTPException, Request, Response, status
from pydantic import ValidationError
from stac_fastapi.types.core import BaseTransactionsClient
from stac_fastapi.types.core import Collection, Item
from typing import Optional, Union


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
            raise ValueError("Item project must match path collection_id")\

        allowed_groups = self.allowed_groups(properties, self.acl)
        print("allowed groups", json.dumps(allowed_groups))

        allowed_groups_uuid = [g.get("uuid") for g in allowed_groups]
        allowed_groups_uuid.append("8a290d6e-8262-11ef-9fa6-6f9995a83a2e")
        print("allowed groups uuid", json.dumps(allowed_groups_uuid))

        authorizer = request.state.authorizer
        access_token_json = authorizer["context"].get("access_token")
        user_groups_json = authorizer["context"].get("groups")
        print("access token json", access_token_json)
        print("user groups json", user_groups_json)

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
                        "identity_provider_display_name": identity.get("identity_provider_display_name"),
                        "last_authentication": identity.get("last_authentication"),
                    }
        print("authorized_identities", json.dumps(authorized_identities))

        auth = {
            "requester_data": {
                "client_id": token_info.get("client_id"),
                "iss": token_info.get("iss"),
                "sub": token_info.get("sub"),
                "username": token_info.get("username"),
                "name": token_info.get("name"),
                "email": token_info.get("email"),
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
        # Get the item from the database to verify that it does not exist
        # item = await self.get_item(item.id, collection_id)
        # if item:
        #     raise HTTPException(status_code=409, detail="Item already exists")

        auth = self.authorize(item, request, collection_id)
        user_agent = request.headers.get("headers", {}).get("User-Agent", "/").split("/")

        stac_item = await request.json()
        try:
            CMIP6Item(**stac_item)
        except ValidationError as e:
            print(e.errors())
            raise HTTPException(status_code=400, detail=str(e.errors()))

        message = {
            "metadata": {
                "auth": auth,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "version": "1.0.0",
                "payload": {
                    "method": "POST",
                    "collection_id": collection_id,
                    "item": stac_item,
                },
            },
        }

        try:
            self.producer.produce(
                topic="esgfng",
                key=item.id.encode("utf-8"),
                value=json.dumps(message, default=str).encode("utf-8"),
            )
        except Exception as e:
            print(f"Error producing message: {e}")
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
        event = request.scope.get("aws.event")
        # Get the item from the database to verify that it exists
        # item = await self.get_item(item_id, collection_id)
        # if not item:
        #     raise HTTPException(status_code=404, detail="Item not found")
        auth = self.authorize(item, event, collection_id)
        user_agent = event.get("headers", {}).get("User-Agent", "/").split("/")

        message = {
            "metadata": {
                "auth": auth,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "version": "1.0.0",
                "payload": {
                    "method": "PUT",
                    "collection_id": collection_id,
                    "item": await request.json(),
                },
            },
        }

        try:
            self.producer.produce(
                topic="esgfng",
                key=item.id.encode("utf-8"),
                value=json.dumps(message, default=str).encode("utf-8"),
            )
        except Exception as e:
            print(f"Error producing message: {e}")
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

        message = {
            "metadata": {
                "auth": None,  # auth,
                "publisher": {
                    "package": user_agent[0],
                    "version": user_agent[1] if len(user_agent) > 1 else "",
                },
                "time": datetime.now().isoformat(),
                "schema_version": "1.0.0",
            },
            "data": {
                "type": "STAC",
                "version": "1.0.0",
                "payload": {
                    "method": "DELETE",
                    "collection_id": collection_id,
                    "item_id": item_id,
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
