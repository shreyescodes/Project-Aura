"""Request and response models for the public API."""

from ipaddress import IPv4Network
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aura_api.domain import QuotaSet, Tier

# Lowercase DNS-label style keeps names safe to reuse in resource names
# ("<tenant>-net", "<tenant>-router") and in hostnames.
TENANT_NAME_PATTERN = r"^[a-z][a-z0-9-]{1,61}[a-z0-9]$"

TenantName = Annotated[
    str,
    Field(pattern=TENANT_NAME_PATTERN, examples=["acme-analytics"]),
]


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: TenantName
    description: str = Field(default="", max_length=255)
    tier: Tier = Tier.SMALL
    network_cidr: IPv4Network = Field(
        default=IPv4Network("192.168.100.0/24"),
        description="Private CIDR for the tenant's first subnet.",
    )
    members: list[Annotated[str, Field(min_length=1, max_length=255)]] = Field(
        default_factory=list,
        max_length=50,
        description="Existing Keystone users to grant the member role.",
    )

    @field_validator("network_cidr")
    @classmethod
    def _check_cidr(cls, value: IPv4Network) -> IPv4Network:
        if not value.is_private:
            raise ValueError("network_cidr must be a private (RFC 1918) range")
        if not 16 <= value.prefixlen <= 28:
            raise ValueError("network_cidr prefix length must be between /16 and /28")
        return value

    @field_validator("members")
    @classmethod
    def _dedupe_members(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=255)
    tier: Tier | None = None


class Quotas(BaseModel):
    instances: int
    cores: int
    ram_mb: int
    volumes: int
    gigabytes: int
    snapshots: int
    networks: int
    subnets: int
    routers: int
    floating_ips: int
    ports: int
    security_groups: int

    @classmethod
    def from_domain(cls, quotas: QuotaSet) -> "Quotas":
        return cls.model_validate(quotas, from_attributes=True)


class TenantNetwork(BaseModel):
    network_id: str
    subnet_id: str | None
    router_id: str | None
    cidr: str | None


class Tenant(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    tier: Tier | None = Field(description="Null if the tier tag was removed or edited by hand.")
    quotas: Quotas | None
    network: TenantNetwork | None = None


class HealthStatus(BaseModel):
    status: str
