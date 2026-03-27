from pydantic_settings import BaseSettings

from settings.ceda import CEDAClientSettings
from settings.globus import GlobusClientSettings

DEFAULT_EXTENSIONS = {
    "CMIP6": {
        "CMIP6": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/cmip6\/v[0-9]\.[0-9]\.[0-9]/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/cmip6/v1.0.0/schema.json",
        },
        "alternate_assets": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/alternate-assets\/v[0-9]\.[0-9]\.[0-9]\/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
        },
        "file": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/file\/v[0-9]\.[0-9]\.[0-9]/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
        },
    },
    "CMIP7": {
        "CMIP7": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/cmip7\/v[0-9]\.[0-9]\.[0-9]\/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/cmip7/v1.0.0/schema.json",
        },
        "alternate_assets": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/alternate-assets\/v[0-9]\.[0-9]\.[0-9]\/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json",
        },
        "file": {
            "regex": [
                r"https:\/\/stac-extensions\.github\.io\/file\/v[0-9]\.[0-9]\.[0-9]/schema\.json"
            ],
            "default": "https://stac-extensions.github.io/file/v2.1.0/schema.json",
        },
    },
}

class Settings(BaseSettings):
    """
    Event Stream Settings
    """

    class Config:
        env_prefix = "TRANSACTION_"

    authorizer: Literal["ceda","globus"] = "globus"
    client: CEDAClientSettings | GlobusClientSettings

    kafka_topic: str

    debug: bool = False


settings = Settings()
