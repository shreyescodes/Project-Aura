"""Runtime configuration, read from AURA_* environment variables."""

from functools import lru_cache
from ipaddress import IPv4Address
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AURA_", env_file=".env", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Accepted values of the X-API-Key header, as a JSON list so keys can be
    # rotated without downtime: AURA_API_KEYS='["new-key", "old-key"]'.
    # With no keys configured every request to /v1 is rejected.
    api_keys: list[SecretStr] = Field(default_factory=list)

    # Entry in clouds.yaml holding admin credentials. Kolla's post-deploy step
    # writes one to /etc/kolla/clouds.yaml.
    os_cloud: str = "kolla-admin"

    # Keystone domain that tenant projects and users live in.
    domain_id: str = "default"

    # Provider network that tenant routers use as their gateway.
    external_network: str = "public"
    dns_nameservers: list[IPv4Address] = Field(
        default_factory=lambda: [IPv4Address("1.1.1.1"), IPv4Address("9.9.9.9")]
    )
    member_role: str = "member"


@lru_cache
def get_settings() -> Settings:
    return Settings()
