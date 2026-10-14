from pydantic import BaseModel


class TimeoutSettings(BaseModel):
    """
    Timeout settings
    """

    connect: float = 5.0
    read: float = 15.0


class ScopeSettings(BaseModel):
    """
    Scope settings
    """

    default: str = "offline_access"

    client_id: str = ""
    client_secret: str = ""

    token_url: str = "https://aai.egi.eu/auth/realms/id/protocol/openid-connect/token"
    group_url: str = "https://aai.egi.eu/auth/realms/id/agm/account/group-admin/groups"

    template: str = "entitlements:urn:mace:egi.eu:group{group}:role={role}#aai.egi.eu"

    roles: set[str] = ("CREATE", "REPLICATE")


class CEDAClientSettings(BaseModel):
    """
    CEDA settings
    """

    client_id: str
    client_secret: str
    token_url: str = "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/token"
    introspection_endpoint: str = (
        "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/token/introspect"
    )
    timeout: TimeoutSettings = TimeoutSettings()

    regex: str = (
        r"urn\:mace\:egi\.eu\:group\:esgf.vo.egi.eu\:(?P<type>[^:]*)\:(?P<id>[^:]*)"
        r"(\:institution\:(?P<institution>[^:]*))?\:role=(?P<role>[^:]*)#aai\.egi\.eu"
    )
    scope: ScopeSettings = ScopeSettings()
