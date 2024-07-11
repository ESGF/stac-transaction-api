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


@api.route("/publish")
def _(event, token_info, groups, payload):

    matched_groups = match_policy(payload, access_control_policy)
    matched_groups_uuid = [g.get("uuid") for g in matched_groups]
    intersection = list(set(groups) & set(matched_groups_uuid))
    if not intersection:
        return api.response(403, {"message": "Forbidden"})
    message = {
        "authorization_server": token_info.get("iss"),
        "created": datetime.now().isoformat(),
        "event": "publish",
        "username": token_info.get("username"),
        "sub": token_info.get("sub"),
        "metadata": payload
    }

    # Send the message to the event stream service
    settings.publish(message)

    return api.response(200, {"message": "Published"})
