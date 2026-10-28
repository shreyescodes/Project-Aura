"""Core types shared by the service layer and the cloud gateway."""

from dataclasses import dataclass
from enum import StrEnum

# Every project this service creates carries MANAGED_TAG, plus a tier tag, so
# the service never lists or modifies projects it doesn't own.
MANAGED_TAG = "aura-managed"
TIER_TAG_PREFIX = "aura-tier:"


class Tier(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    @property
    def tag(self) -> str:
        return f"{TIER_TAG_PREFIX}{self.value}"

    @classmethod
    def from_tags(cls, tags: list[str]) -> "Tier | None":
        for tag in tags:
            if tag.startswith(TIER_TAG_PREFIX):
                try:
                    return cls(tag.removeprefix(TIER_TAG_PREFIX))
                except ValueError:
                    return None
        return None


@dataclass(frozen=True, slots=True)
class QuotaSet:
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


TIER_QUOTAS: dict[Tier, QuotaSet] = {
    Tier.SMALL: QuotaSet(
        instances=10, cores=20, ram_mb=40_960,
        volumes=10, gigabytes=500, snapshots=10,
        networks=2, subnets=4, routers=1, floating_ips=2, ports=50, security_groups=10,
    ),
    Tier.MEDIUM: QuotaSet(
        instances=25, cores=50, ram_mb=102_400,
        volumes=25, gigabytes=2_000, snapshots=25,
        networks=5, subnets=10, routers=2, floating_ips=5, ports=150, security_groups=25,
    ),
    Tier.LARGE: QuotaSet(
        instances=100, cores=200, ram_mb=409_600,
        volumes=100, gigabytes=10_000, snapshots=100,
        networks=10, subnets=20, routers=5, floating_ips=20, ports=500, security_groups=50,
    ),
}  # fmt: skip


@dataclass(frozen=True, slots=True)
class Project:
    id: str
    name: str
    description: str
    enabled: bool
    tags: list[str]


@dataclass(frozen=True, slots=True)
class NetworkTopology:
    network_id: str
    subnet_id: str | None
    router_id: str | None
    cidr: str | None


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    servers: int
    volumes: int

    @property
    def is_empty(self) -> bool:
        return self.servers == 0 and self.volumes == 0
