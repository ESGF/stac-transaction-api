import json
import urllib3
from datetime import datetime
from api import api
import api_settings as settings

http = urllib3.PoolManager()


def load_access_control_policy(url):
    response = http.request('GET', url)
    if response.status == 200:
        return json.loads(response.data.decode('utf-8'))
    else:
        return {}


access_control_policy = load_access_control_policy(settings.api.get("access_control_policy"))
admins = load_access_control_policy(settings.api.get("admins"))


def match_policy(payload, acp):
    if isinstance(acp, list):
        return acp
    for facet, subpolicy in acp.items():
        if facet in payload:
            payload_value = payload.get(facet)
            if isinstance(payload_value, str):
                payload_value = [payload_value]
            matches = list(set(payload_value) & set(subpolicy.keys()))
            for match in matches:
                groups = match_policy(payload, subpolicy[match])
                if groups:
                    return groups
    return []


@api.route("/collections/{collection_id}/items")
def _(event, token_info, groups, payload, collection_id):

    matched_groups = match_policy(payload, access_control_policy)
    matched_groups_uuid = [g.get("uuid") for g in matched_groups]

    group_id = None
    identity_id = None
    for group in groups:
        if group.get("group_id") in matched_groups_uuid:
            group_id = group.get("group_id")
            identity_id = group.get("identity_id")
            break
    if group_id is None:
        return api.response(403, {"error": "Forbidden"})

    print("group_id", group_id)
    print("identity_id", identity_id)

    identity_detail = None
    identity_set_detail = token_info.get("identity_set_detail", [])
    for identity in identity_set_detail:
        if identity.get("sub") == identity_id:
            identity_detail = identity
            break

    print(identity_detail)

    message = {
        "metadata": {
            "auth": {
                "client_id": settings.publisher.get("client_id"),
                "iss": token_info.get("iss"),
                "sub": identity_id,
                "username": identity_detail.get("username"),
                "name": identity_detail.get("name"),
                "identity_provider": identity_detail.get("identity_provider"),
                "identity_provider_display_name": identity_detail.get("identity_provider_display_name"),
                "email": identity_detail.get("email"),
                "authorization_basis_type": "group",
                "authorization_basis_service": "groups.globus.org",
                "authorization_basis": group_id
            },
            "publisher": {
                "package": "esgf_publisher",
                "version": "1.1.1"
            },
            "time": datetime.now().isoformat(),
            "schema_version": "1.0.0"
        },
        "data": {
            "type": "STAC",
            "version": "1.0.0",
            "payload": {
                "method": "POST",
                "collection_id": collection_id,
                "item": payload
            }
        }
    }

    # Send the message to the event stream service
    settings.publish(message)

    return api.response(200, {"message": "Published"})
