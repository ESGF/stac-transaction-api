import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Union

from esgf_playground_utils.models.item import CMIP6Item
from esgf_playground_utils.models.kafka import (
    Auth,
    CreatePayload,
    Data,
    KafkaEvent,
    Metadata,
    PatchPayload,
    Publisher,
    RequesterData,
    RevokePayload,
    UpdatePayload,
)
from fastapi import HTTPException, Request, Response, status
from stac_fastapi.extensions.core.transaction import BaseTransactionsClient
from stac_fastapi.extensions.core.transaction.request import PartialItem, PatchOperation
from stac_fastapi.types.stac import Collection

from models import Authorizer
from settings.transaction import access_control_policy, event_stream, stac_api
from utils import operation_to_partial_item, validate_extensions, validate_patch, validate_post

# Setup logger
logger = logging.getLogger(__name__)


class TransactionClient(BaseTransactionsClient):

    def __init__(self, producer):
        self.producer = producer

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

    def globus_authorize(self, item: CMIP6Item, request: Request, collection_id: str) -> dict:
        properties = item.properties

        if item.collection != collection_id:
            raise ValueError("Item collection must match path collection_id")
        if getattr(properties, "project", None) != collection_id:
            raise ValueError("Item project must match path collection_id")

        allowed_groups = self.allowed_groups(properties, access_control_policy)
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
                        "identity_provider_display_name": identity.get("identity_provider_display_name"),
                        "last_authentication": identity.get("last_authentication"),
                    }

        requester_data = RequesterData(
            client_id=token_info.get("client_id"),
            sub=token_info.get("sub"),
            iss=token_info.get("username"),
        )

        auth = Auth(
            requester_data=requester_data,
        )
        # "auth_basis_data": {
        #     "authorization_basis_type": "group",
        #     "authorization_basis_service": "groups.globus.org",
        #     "authorization_basis": authorized_identities,
        # },

        return auth

    def egi_authorize(self, collection_id: str, item: CMIP6Item, role: str, request: Request) -> Auth:
        """_summary_

        Args:
            item (CMIP6Item): item to check authorization for
            role (str): role to check authorization for
            request (Request): current request

        Returns:
            Auth: Auth object if successful
        """
        authorizer: Authorizer = request.state.authorizer
        authorizer.authorize(collection_id, item, role)

        return Auth(
            requester_data=authorizer.requester_data,
        )

    def authorize(self, item: CMIP6Item | PartialItem, role: str, request: Request, collection_id: str) -> Auth:

        if stac_api.get("authorizer", "globus") == "globus":
            return self.globus_authorize(collection_id=collection_id, item=item, request=request)
        else:
            return self.egi_authorize(collection_id=collection_id, item=item, role=role, request=request)

    async def create_item(
        self,
        item: CMIP6Item,
        request: Request,
        collection_id: str,
    ) -> Optional[Union[CMIP6Item, Response, None]]:

        auth = self.authorize(item=item, role="CREATE", request=request, collection_id=collection_id)

        headers = request.headers.get("headers", {})

        event_id = uuid.uuid4().hex
        request_id = headers.get("X-Request-ID", uuid.uuid4().hex)

        item_extensions = item.stac_extensions if item.stac_extensions else []

        item_extensions = validate_extensions(collection_id=collection_id, item_extensions=item_extensions)

        validate_post(event_id=event_id, request_id=request_id, item_id=item.id, item=item, extensions=item_extensions)

        user_agent = headers.get("User-Agent", "/").split("/")

        payload = CreatePayload(
            method="POST",
            collection_id=collection_id,
            item=item.model_dump(),
        )

        data = Data(type="STAC", payload=payload)

        publisher = Publisher(package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else "")

        metadata = Metadata(
            auth=auth,
            event_id=event_id,
            publisher=publisher,
            request_id=request_id,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item.id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )

        except Exception as e:
            logger.error(f"Error producing message: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for publication",
        )

    async def update_item(
        self,
        item: CMIP6Item,
        request: Request,
        collection_id: str,
        item_id: str,
    ) -> Optional[Union[CMIP6Item, Response]]:

        auth = self.authorize(collection_id=collection_id, item=item, role="UPDATE", request=request)

        headers = request.headers.get("headers", {})

        event_id = uuid.uuid4().hex
        request_id = headers.get("X-Request-ID", uuid.uuid4().hex)
        item_extensions = item.stac_extensions if item.stac_extensions else []

        item_extensions = validate_extensions(collection_id=collection_id, item_extensions=item_extensions)

        validate_post(event_id=event_id, request_id=request_id, item_id=item.id, item=item, extensions=item_extensions)

        user_agent = headers.get("User-Agent", "/").split("/")

        payload = UpdatePayload(
            method="PUT",
            collection_id=collection_id,
            item_id=item_id,
            item=item.model_dump(),
        )

        data = Data(type="STAC", payload=payload)

        publisher = Publisher(package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else "")
        metadata = Metadata(
            auth=auth,
            event_id=event_id,
            publisher=publisher,
            request_id=request_id,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item_id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )
        except Exception as e:
            logger.error(f"Error producing message: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for update",
        )

    async def patch_item(
        self,
        collection_id: str,
        item_id: str,
        patch: Union[PartialItem, list[PatchOperation]],
        request: Request,
    ) -> Optional[Union[CMIP6Item, Response]]:

        item = operation_to_partial_item(patch) if isinstance(patch, list) else patch
        auth = self.authorize(collection_id=collection_id, item=item, role="UPDATE", request=request)

        headers = request.headers.get("headers", {})

        event_id = uuid.uuid4().hex
        request_id = headers.get("X-Request-ID", uuid.uuid4().hex)

        item_extensions = item.stac_extensions if item.stac_extensions else []

        item_extensions = validate_extensions(collection_id=collection_id, item_extensions=item_extensions)

        validate_patch(event_id=event_id, request_id=request_id, item_id=item_id, item=item, extensions=item_extensions)

        user_agent = headers.get("User-Agent", "/").split("/")

        payload = PatchPayload(
            method="PATCH",
            collection_id=collection_id,
            item_id=item_id,
            patch=json.dumps(patch),
        )

        data = Data(type="STAC", payload=payload)

        publisher = Publisher(package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else "")
        metadata = Metadata(
            auth=auth,
            event_id=event_id,
            publisher=publisher,
            request_id=request_id,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item_id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )
        except Exception as e:
            logger.error(f"Error producing message: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for update",
        )

    async def delete_item(
        self,
        request: Request,
        collection_id: str,
        item_id: str,
    ) -> Optional[Union[CMIP6Item, Response]]:
        auth = self.authorize(collection_id=collection_id, item=item_id, role="UPDATE", request=request)

        headers = request.headers.get("headers", {})

        event_id = uuid.uuid4().hex
        request_id = headers.get("X-Request-ID", uuid.uuid4().hex)

        user_agent = headers.get("User-Agent", "/").split("/")

        payload = RevokePayload(
            method="DELETE",
            collection_id=collection_id,
            item_id=item_id,
        )

        data = Data(type="STAC", payload=payload)

        publisher = Publisher(package=user_agent[0], version=user_agent[1] if len(user_agent) > 1 else "")

        metadata = Metadata(
            auth=auth,
            event_id=event_id,
            publisher=publisher,
            request_id=request_id,
            time=datetime.now().isoformat(),
            schema_version="1.0.0",
        )
        event = KafkaEvent(metadata=metadata, data=data)

        try:
            self.producer.produce(
                topic=event_stream.get("topic"),
                key=item_id.encode("utf-8"),
                value=event.model_dump_json().encode("utf8"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content="Item queued for deletion",
        )

    async def create_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("create_collection is not implemented")

    async def patch_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("patch_collection is not implemented")

    async def update_collection(self, collection: Collection, **kwargs) -> Collection:
        raise NotImplementedError("update_collection is not implemented")

    async def delete_collection(self, collection_id: str, **kwargs) -> None:
        raise NotImplementedError("delete_collection is not implemented")
