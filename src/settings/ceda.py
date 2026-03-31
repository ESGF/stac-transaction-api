from pydantic_settings import BaseSettings, SettingsConfigDict


class CEDAClientSettings(BaseSettings):
    """
    CEDA settings
    """

    model_config = SettingsConfigDict(env_prefix="CEDA_")

    client_id: str
    client_secret: str
    token_url: str = "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/token"
    introspection_endpoint: str = (
        "https://aai.egi.eu/auth/realms/egi/protocol/openid-connect/token/introspect"
    )
    regex: str = (
        r"urn\:mace\:egi\.eu\:group\:esgf.vo.egi.eu\:(?P<type>.*)\:(?P<id>.*)\:role=(?P<role>.*)#aai.egi.eu"
    )
