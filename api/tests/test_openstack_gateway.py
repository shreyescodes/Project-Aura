from ipaddress import IPv4Address, IPv4Network
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from keystoneauth1 import exceptions as ksa_exceptions
from openstack import exceptions as sdk_exceptions

from aura_api.cloud.openstack import ROUTER_INTERFACE_OWNER, OpenStackGateway
from aura_api.domain import TIER_QUOTAS, Tier
from aura_api.errors import CloudError, TenantAlreadyExistsError


@pytest.fixture
def conn() -> MagicMock:
    return MagicMock()


@pytest.fixture
def gateway(conn: MagicMock) -> OpenStackGateway:
    return OpenStackGateway(conn, domain_id="default")


def _project(**attrs: object) -> SimpleNamespace:
    defaults = {"id": "p1", "name": "acme", "description": None, "is_enabled": True, "tags": None}
    return SimpleNamespace(**{**defaults, **attrs})


class TestIdentity:
    def test_find_project_scopes_lookup_to_domain(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.find_project.return_value = _project(tags=["aura-managed"])

        project = gateway.find_project("acme")

        conn.identity.find_project.assert_called_once_with(
            "acme", ignore_missing=True, domain_id="default"
        )
        assert project is not None
        assert project.description == ""
        assert project.tags == ["aura-managed"]

    def test_find_project_returns_none_when_missing(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.find_project.return_value = None

        assert gateway.find_project("acme") is None

    def test_create_project_conflict_maps_to_already_exists(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.create_project.side_effect = sdk_exceptions.ConflictException("dup")

        with pytest.raises(TenantAlreadyExistsError):
            gateway.create_project("acme", "", ["aura-managed"])

    def test_other_create_failures_are_cloud_errors(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.create_project.side_effect = sdk_exceptions.ForbiddenException("no")

        with pytest.raises(CloudError) as excinfo:
            gateway.create_project("acme", "", [])

        assert not isinstance(excinfo.value, TenantAlreadyExistsError)

    def test_update_project_sends_only_given_fields(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.update_project.return_value = _project()

        gateway.update_project("p1", tags=("a", "b"))

        conn.identity.update_project.assert_called_once_with("p1", tags=["a", "b"])

    def test_find_user_id_is_scoped_to_domain(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.identity.users.return_value = iter([SimpleNamespace(id="u1")])

        assert gateway.find_user_id("alice") == "u1"
        conn.identity.users.assert_called_once_with(domain_id="default", name="alice")

    def test_grant_role_resolves_role_by_name(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        role = SimpleNamespace(id="r1")
        conn.identity.find_role.return_value = role

        gateway.grant_role("p1", "u1", "member")

        conn.identity.assign_project_role_to_user.assert_called_once_with("p1", "u1", role)


class TestQuotas:
    def test_applies_compute_volume_and_network_quotas(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        quotas = TIER_QUOTAS[Tier.SMALL]

        gateway.apply_quotas("p1", quotas)

        conn.set_compute_quotas.assert_called_once_with(
            "p1", instances=quotas.instances, cores=quotas.cores, ram=quotas.ram_mb
        )
        conn.set_volume_quotas.assert_called_once()
        network_quotas = conn.set_network_quotas.call_args.kwargs
        assert network_quotas["floating_ips"] == quotas.floating_ips


class TestNetworking:
    def test_create_network_builds_routed_topology(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        net = conn.network
        net.find_network.return_value = SimpleNamespace(id="ext")
        net.create_network.return_value = SimpleNamespace(id="n1")
        net.create_subnet.return_value = SimpleNamespace(id="s1")
        net.create_router.return_value = SimpleNamespace(id="r1")

        topology = gateway.create_network(
            "p1", "acme", IPv4Network("10.1.0.0/24"), [IPv4Address("1.1.1.1")], "public", ["t"]
        )

        assert topology.network_id == "n1"
        assert topology.router_id == "r1"
        assert net.create_subnet.call_args.kwargs["dns_nameservers"] == ["1.1.1.1"]
        assert net.create_router.call_args.kwargs["external_gateway_info"] == {"network_id": "ext"}
        net.add_interface_to_router.assert_called_once_with(
            net.create_router.return_value, subnet="s1"
        )

    def test_find_network_returns_none_without_tagged_network(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.network.networks.return_value = iter([])

        assert gateway.find_network("p1", "aura-managed") is None

    def test_find_network_reads_subnet_cidr(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.network.networks.return_value = iter([SimpleNamespace(id="n1", subnet_ids=["s1"])])
        conn.network.routers.return_value = iter([])
        conn.network.get_subnet.return_value = SimpleNamespace(cidr="10.1.0.0/24")

        topology = gateway.find_network("p1", "aura-managed")

        assert topology is not None
        assert topology.cidr == "10.1.0.0/24"
        assert topology.router_id is None

    def test_delete_networks_detaches_router_ports_before_deleting(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        net = conn.network
        router = SimpleNamespace(id="r1")
        net.routers.return_value = [router]
        net.ports.return_value = [SimpleNamespace(id="port1")]
        net.ips.return_value = [SimpleNamespace(id="fip1")]
        net.networks.return_value = [SimpleNamespace(id="n1")]
        net.security_groups.return_value = [SimpleNamespace(id="sg1")]

        gateway.delete_networks("p1")

        net.ports.assert_called_once_with(device_id="r1", device_owner=ROUTER_INTERFACE_OWNER)
        ordered = [c for c in net.mock_calls if c[0].startswith(("remove_", "delete_"))]
        assert [c[0] for c in ordered] == [
            "remove_interface_from_router",
            "delete_router",
            "delete_ip",
            "delete_network",
            "delete_security_group",
        ]
        assert ordered[0] == call.remove_interface_from_router(router, port="port1")


class TestUsageAndHealth:
    def test_count_resources_spans_all_projects(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.compute.servers.return_value = iter([object(), object()])
        conn.block_storage.volumes.return_value = iter([object()])

        usage = gateway.count_resources("p1")

        assert (usage.servers, usage.volumes) == (2, 1)
        conn.compute.servers.assert_called_once_with(
            details=False, all_projects=True, project_id="p1"
        )

    def test_transport_failures_become_cloud_errors(
        self, gateway: OpenStackGateway, conn: MagicMock
    ) -> None:
        conn.authorize.side_effect = ksa_exceptions.ConnectFailure("unreachable")

        with pytest.raises(CloudError, match="authenticate"):
            gateway.check_connection()
