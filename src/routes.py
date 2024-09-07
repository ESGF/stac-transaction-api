import json
import urllib3
from datetime import datetime
from api import api
import api_settings as settings

http = urllib3.PoolManager()


def load_access_control_policy(url):
    response = http.request("GET", url)
    if response.status == 200:
        return json.loads(response.data.decode("utf-8"))
    else:
        return {}


access_control_policy = load_access_control_policy(settings.api.get("access_control_policy"))
admins = load_access_control_policy(settings.api.get("admins"))


def match_policy(properties, acp):
    if isinstance(acp, list):
        return acp
    for facet, subpolicy in acp.items():
        if facet in properties:
            property_value = properties.get(facet)
            if isinstance(property_value, str):
                property_value = [property_value]
            matches = list(set(property_value) & set(subpolicy.keys()))
            for match in matches:
                groups = match_policy(properties, subpolicy[match])
                if groups:
                    return groups
    return []


@api.route("/collections/{collection_id}/items")
def _(event, token_info, groups, payload, collection_id):
    properties = payload.get("properties", {})
    if payload.get("collection") != collection_id:
        return api.response(400, {"error": "Item collection must match path collection_id"})
    if properties.get("project") != collection_id:
        return api.response(400, {"error": "Item project must match path collection_id"})
    matched_groups = match_policy(properties, access_control_policy)
    print("matched_groups")
    print(json.dumps(matched_groups))
    matched_groups_uuid = [g.get("uuid") for g in matched_groups]
    print("matched_groups_uuid")
    print(json.dumps(matched_groups_uuid))

    authorized_identities = []
    for group in groups:
        if group.get("group_id") in matched_groups_uuid:
            authorized_identities.append(
                {
                    "group_id": group.get("group_id"),
                    "identity_id": group.get("identity_id"),
                }
            )
    if not authorized_identities:
        return api.response(403, {"error": "Forbidden"})

    print("authorized_identities")
    print(json.dumps(authorized_identities))

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
    print("authorized_identities")
    print(json.dumps(authorized_identities))

    user_agent = event.get("headers", {}).get("User-Agent", "/").split("/")

    message = {
        "metadata": {
            "auth": {
                "requester_data": {
                    "client_id": settings.publisher.get("client_id"),
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
            },
            "publisher": {
                "package": user_agent[0],
                "version": user_agent[1],
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
                "item": payload,
            },
        },
    }

    # Send the message to the event stream service
    settings.publish(message)

    return api.response(202, {"message": "Queued for publication"})
