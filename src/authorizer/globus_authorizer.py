import json
import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from globus_sdk import AccessTokenAuthorizer, GroupsClient
from globus_sdk.scopes import GroupsScopes
from starlette.middleware.base import BaseHTTPMiddleware

from settings import settings

logger = logging.getLogger("uvicorn.error")

"""
FastAPI Middleware Authorizer
    Authorizer type: FastAPI Middleware
    Event payload: Token
    Token source: Authorization
    Token validation: ^Bearer\\s[^\\s]+$ # noqa: W605
                      ^Bearer\\s[0-9A-Za-z]+$ for access tokens issued by Globus Auth (?)  # noqa: W605
    Authorization caching: 300 seconds
"""


class GlobusAuthorizer(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Health check endpoint for AWS ALB target group
        # Need to bypass authorization for this endpoint
        if request.url.path == "/healthcheck":
            return await call_next(request)

        authorization_header = request.headers.get("authorization")

        # Set API Gateway token validation correctly to avoid IndexError exception
        access_token = authorization_header[7:]
        response = settings.client.confidential_client.oauth2_token_introspect(
            access_token, include="identity_set_detail"
        )
        token_info = response.data

        # Verify the access token
        if not token_info.get("active", False):
            return JSONResponse(
                content={"message": "Unauthorized - Inactive token"}, 
                status_code=401
            )

        if settings.client.client_id not in token_info.get("aud", []):
            return JSONResponse(
                content={"message": "Unauthorized - Invalid token audience"}, 
                status_code=401
            )

        if settings.client.scope_string != token_info.get("scope", ""):
            return JSONResponse(
                content={"message": "Unauthorized - Invalid token scope"}, 
                status_code=401
            )

        if settings.client.issuer != token_info.get("iss", ""):
            return JSONResponse(
                content={"message": "Unauthorized - Invalid token issuer"}, 
                status_code=401
            )

        # Get the user's groups
        groups = self.get_groups(access_token)
        if not groups:
            return JSONResponse(
                content={"message": "Unauthorized - No active group memberships found"}, 
                status_code=401
            )

        auth = self.generate_auth(
            token_info.get("sub"),
            token_info=token_info,
            groups=groups,
        )
        request.state.authorizer = auth
        return await call_next(request)

    def get_groups(self, token):
        """
        As https://docs.globus.org/api/auth/specification/#performance states,
        Failure to reuse these tokens can harm performance on both the resource server
        doing the grant and any downstream resource servers it uses.
        Amazon API Gateway Authorization caching setting can be use to cache the authorizer response,
        and if the a new request with the same bearer token
        """

        tokens = settings.client.confidential_client.oauth2_get_dependent_tokens(
            token, scope=GroupsScopes.view_my_groups_and_memberships
        )
        groups_token = tokens.by_resource_server[GroupsClient.resource_server]
        authorizer = AccessTokenAuthorizer(groups_token["access_token"])
        groups_client = GroupsClient(authorizer=authorizer)
        groups_response = groups_client.get_my_groups()
        groups = []
        for group in groups_response:
            group_id = group.get("id")
            memberships = group.get("my_memberships", [])
            for membership in memberships:
                if membership.get("status") == "active":
                    groups.append(
                        {
                            "group_id": group_id,
                            "identity_id": membership.get("identity_id"),
                        }
                    )
        return groups

    def generate_auth(self, user, token_info=None, groups=None):
        auth_response = {}
        if token_info:
            auth_response["context"] = {
                "access_token": json.dumps(token_info),
            }
            if groups:
                auth_response["context"]["groups"] = json.dumps(groups)

        return auth_response
