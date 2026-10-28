"""FastAPI dependency providers. Tests override get_gateway with a fake."""

from functools import lru_cache
from typing import Annotated

import openstack
from fastapi import Depends

from aura_api.cloud import CloudGateway
from aura_api.cloud.openstack import OpenStackGateway
from aura_api.config import Settings, get_settings
from aura_api.services.tenants import TenantPolicy, TenantService


@lru_cache
def _openstack_gateway(cloud: str, domain_id: str) -> OpenStackGateway:
    # Created on first use rather than at import, so the app can start (and
    # report not-ready) while Keystone is unreachable.
    return OpenStackGateway(openstack.connect(cloud=cloud), domain_id=domain_id)


def get_gateway(settings: Annotated[Settings, Depends(get_settings)]) -> CloudGateway:
    return _openstack_gateway(settings.os_cloud, settings.domain_id)


def get_tenant_service(
    settings: Annotated[Settings, Depends(get_settings)],
    gateway: Annotated[CloudGateway, Depends(get_gateway)],
) -> TenantService:
    policy = TenantPolicy(
        external_network=settings.external_network,
        dns_nameservers=settings.dns_nameservers,
        member_role=settings.member_role,
    )
    return TenantService(gateway, policy)


GatewayDep = Annotated[CloudGateway, Depends(get_gateway)]
TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
