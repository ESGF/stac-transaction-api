from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.settings.ceda import CEDAClientSettings
from src.settings.globus import GlobusClientSettings

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

    model_config = SettingsConfigDict(env_prefix="TRANSACTION_")

    authorizer: Literal["egi", "globus"] = "globus"
    client: CEDAClientSettings | GlobusClientSettings

    debug: bool = False


settings = Settings()
