from collections.abc import Iterator
from ipaddress import IPv4Address

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aura_api.config import Settings, get_settings
from aura_api.dependencies import get_gateway
from aura_api.main import create_app
from aura_api.services.tenants import TenantPolicy, TenantService
from tests.fakes import FakeCloudGateway

API_KEY = "test-key"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        api_keys=[SecretStr(API_KEY), SecretStr("rotated-key")],
        external_network="public",
        dns_nameservers=[IPv4Address("10.0.10.1")],
    )


@pytest.fixture
def gateway() -> FakeCloudGateway:
    return FakeCloudGateway()


@pytest.fixture
def service(gateway: FakeCloudGateway, settings: Settings) -> TenantService:
    policy = TenantPolicy(
        external_network=settings.external_network,
        dns_nameservers=settings.dns_nameservers,
        member_role=settings.member_role,
    )
    return TenantService(gateway, policy)


@pytest.fixture
def client(settings: Settings, gateway: FakeCloudGateway) -> Iterator[TestClient]:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_gateway] = lambda: gateway
    with TestClient(app, headers={"X-API-Key": API_KEY}) as test_client:
        yield test_client
