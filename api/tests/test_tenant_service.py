from ipaddress import IPv4Network

import pytest

from aura_api.domain import MANAGED_TAG, TIER_QUOTAS, ResourceUsage, Tier
from aura_api.errors import (
    ProvisioningError,
    TenantAlreadyExistsError,
    TenantNotEmptyError,
    TenantNotFoundError,
    UnknownUsersError,
)
from aura_api.schemas import TenantCreate, TenantUpdate
from aura_api.services.tenants import TenantService
from tests.fakes import FakeCloudGateway


def _request(**overrides: object) -> TenantCreate:
    return TenantCreate.model_validate({"name": "acme", **overrides})


class TestCreateTenant:
    def test_provisions_project_quotas_network_and_grants(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        alice = gateway.add_user("alice")

        tenant = service.create_tenant(
            _request(tier="medium", members=["alice"], network_cidr="10.20.0.0/24")
        )

        project = gateway.projects[tenant.id]
        assert project.tags == [MANAGED_TAG, "aura-tier:medium"]
        assert gateway.quotas[tenant.id] == TIER_QUOTAS[Tier.MEDIUM]
        assert gateway.role_grants == {(tenant.id, alice, "member")}
        assert tenant.network is not None
        assert tenant.network.cidr == "10.20.0.0/24"
        assert tenant.tier is Tier.MEDIUM

    def test_unknown_members_are_rejected_before_anything_is_created(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.add_user("alice")

        with pytest.raises(UnknownUsersError, match="bob, carol"):
            service.create_tenant(_request(members=["alice", "carol", "bob"]))

        assert gateway.calls == []

    def test_existing_name_is_a_conflict_without_rollback(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        existing = gateway.add_project("acme")

        with pytest.raises(TenantAlreadyExistsError):
            service.create_tenant(_request())

        assert existing.id in gateway.projects
        assert "delete_project" not in gateway.calls

    @pytest.mark.parametrize("failing_step", ["apply_quotas", "create_network", "grant_role"])
    def test_failure_rolls_back_completed_steps(
        self, service: TenantService, gateway: FakeCloudGateway, failing_step: str
    ) -> None:
        gateway.add_user("alice")
        gateway.fail_on.add(failing_step)

        with pytest.raises(ProvisioningError, match="rolled back"):
            service.create_tenant(_request(members=["alice"]))

        assert gateway.projects == {}
        assert gateway.networks == {}
        assert gateway.role_grants == set()

    def test_rollback_undoes_newest_step_first(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.add_user("alice")
        gateway.fail_on.add("grant_role")

        with pytest.raises(ProvisioningError):
            service.create_tenant(_request(members=["alice"]))

        undo = [c for c in gateway.calls if c.startswith("delete_")]
        assert undo == ["delete_networks", "delete_project"]

    def test_rollback_continues_when_an_undo_step_fails(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.fail_on.update({"create_network", "delete_networks"})

        with pytest.raises(ProvisioningError):
            service.create_tenant(_request())

        assert gateway.projects == {}

    def test_unexpected_errors_also_roll_back(
        self, service: TenantService, gateway: FakeCloudGateway, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_: object, **__: object) -> None:
            raise RuntimeError("bug")

        monkeypatch.setattr(gateway, "apply_quotas", boom)

        with pytest.raises(ProvisioningError, match="unexpected error"):
            service.create_tenant(_request())

        assert gateway.projects == {}


class TestReadTenants:
    def test_list_returns_only_managed_projects_sorted_by_name(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.add_project("zeta", [MANAGED_TAG, Tier.SMALL.tag])
        gateway.add_project("admin")
        gateway.add_project("alpha", [MANAGED_TAG, Tier.LARGE.tag])

        names = [t.name for t in service.list_tenants()]

        assert names == ["alpha", "zeta"]

    def test_unmanaged_project_is_reported_as_missing(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.add_project("admin")

        with pytest.raises(TenantNotFoundError):
            service.get_tenant("admin")

    def test_unrecognised_tier_tag_yields_no_tier_or_quotas(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        gateway.add_project("acme", [MANAGED_TAG, "aura-tier:platinum"])

        tenant = service.get_tenant("acme")

        assert tenant.tier is None
        assert tenant.quotas is None


class TestUpdateTenant:
    def test_tier_change_reapplies_quotas_and_replaces_tier_tag(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        tenant = service.create_tenant(_request(tier="small"))

        updated = service.update_tenant("acme", TenantUpdate(tier=Tier.LARGE))

        assert updated.tier is Tier.LARGE
        assert gateway.quotas[tenant.id] == TIER_QUOTAS[Tier.LARGE]
        assert gateway.projects[tenant.id].tags == [MANAGED_TAG, "aura-tier:large"]

    def test_description_only_change_leaves_quotas_alone(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        service.create_tenant(_request())
        gateway.calls.clear()

        updated = service.update_tenant("acme", TenantUpdate(description="Data team"))

        assert updated.description == "Data team"
        assert gateway.calls == ["update_project"]

    def test_empty_update_changes_nothing(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        service.create_tenant(_request())
        gateway.calls.clear()

        service.update_tenant("acme", TenantUpdate())

        assert gateway.calls == []


class TestDeleteTenant:
    def test_removes_networking_then_project(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        service.create_tenant(_request())
        gateway.calls.clear()

        service.delete_tenant("acme")

        assert gateway.calls == ["delete_networks", "delete_project"]
        assert gateway.projects == {}

    def test_refuses_while_servers_or_volumes_remain(
        self, service: TenantService, gateway: FakeCloudGateway
    ) -> None:
        tenant = service.create_tenant(_request())
        gateway.usage[tenant.id] = ResourceUsage(servers=2, volumes=1)

        with pytest.raises(TenantNotEmptyError, match="2 server"):
            service.delete_tenant("acme")

        assert tenant.id in gateway.projects


class TestTenantCreateValidation:
    @pytest.mark.parametrize("name", ["Acme", "a", "-acme", "acme-", "acme_corp", "x" * 64])
    def test_rejects_invalid_names(self, name: str) -> None:
        with pytest.raises(ValueError, match="name"):
            _request(name=name)

    @pytest.mark.parametrize("cidr", ["8.8.8.0/24", "10.0.0.0/8", "192.168.1.0/30"])
    def test_rejects_public_or_badly_sized_cidrs(self, cidr: str) -> None:
        with pytest.raises(ValueError, match="network_cidr"):
            _request(network_cidr=cidr)

    def test_deduplicates_members_preserving_order(self) -> None:
        request = _request(members=["bob", "alice", "bob"])

        assert request.members == ["bob", "alice"]
        assert request.network_cidr == IPv4Network("192.168.100.0/24")
