"""CloudGateway implementation backed by openstacksdk."""

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from ipaddress import IPv4Address, IPv4Network
from typing import Any, cast

from keystoneauth1 import exceptions as ksa_exceptions
from openstack import exceptions as sdk_exceptions
from openstack.connection import Connection
from openstack.identity.v3._proxy import Proxy as IdentityV3

from aura_api.domain import NetworkTopology, Project, QuotaSet, ResourceUsage
from aura_api.errors import CloudError, TenantAlreadyExistsError

logger = logging.getLogger(__name__)

ROUTER_INTERFACE_OWNER = "network:router_interface"


@contextmanager
def _translate_errors(operation: str) -> Iterator[None]:
    """Turn SDK and transport failures into CloudError, keeping the cause chained."""
    try:
        yield
    except (sdk_exceptions.SDKException, ksa_exceptions.ClientException) as exc:
        logger.warning("OpenStack call failed", extra={"operation": operation, "error": str(exc)})
        raise CloudError(f"OpenStack request failed while trying to {operation}.") from exc


def _to_project(project: Any) -> Project:
    return Project(
        id=project.id,
        name=project.name,
        description=project.description or "",
        enabled=bool(project.is_enabled),
        tags=list(project.tags or []),
    )


class OpenStackGateway:
    """Calls OpenStack APIs as an admin.

    The underlying keystoneauth session is shared by request threads; it is
    safe for concurrent use.
    """

    def __init__(self, conn: Connection, domain_id: str) -> None:
        self._conn = conn
        # The SDK types identity as v2 | v3; Kolla deploys Keystone v3 only.
        self._identity = cast(IdentityV3, conn.identity)
        self._domain_id = domain_id

    def check_connection(self) -> None:
        with _translate_errors("authenticate"):
            self._conn.authorize()

    # --- Identity ---------------------------------------------------------------

    def find_project(self, name: str) -> Project | None:
        with _translate_errors("look up a project"):
            project = self._identity.find_project(
                name, ignore_missing=True, domain_id=self._domain_id
            )
        return _to_project(project) if project else None

    def list_projects(self, tag: str) -> list[Project]:
        with _translate_errors("list projects"):
            projects = self._identity.projects(domain_id=self._domain_id, tags=tag)
            return [_to_project(p) for p in projects]

    def create_project(self, name: str, description: str, tags: Sequence[str]) -> Project:
        try:
            with _translate_errors("create a project"):
                project = self._identity.create_project(
                    name=name,
                    description=description,
                    domain_id=self._domain_id,
                    tags=list(tags),
                    is_enabled=True,
                )
        except CloudError as exc:
            # Keystone enforces unique names per domain, which also settles
            # two concurrent requests for the same tenant.
            if isinstance(exc.__cause__, sdk_exceptions.ConflictException):
                raise TenantAlreadyExistsError(name) from exc.__cause__
            raise
        return _to_project(project)

    def update_project(
        self, project_id: str, *, description: str | None = None, tags: Sequence[str] | None = None
    ) -> Project:
        attrs: dict[str, Any] = {}
        if description is not None:
            attrs["description"] = description
        if tags is not None:
            attrs["tags"] = list(tags)
        with _translate_errors("update a project"):
            return _to_project(self._identity.update_project(project_id, **attrs))

    def delete_project(self, project_id: str) -> None:
        with _translate_errors("delete a project"):
            self._identity.delete_project(project_id, ignore_missing=True)

    def find_user_id(self, name: str) -> str | None:
        with _translate_errors("look up a user"):
            users = self._identity.users(domain_id=self._domain_id, name=name)
            user = next(iter(users), None)
        return user.id if user else None

    def grant_role(self, project_id: str, user_id: str, role_name: str) -> None:
        with _translate_errors("grant a role"):
            role = self._identity.find_role(role_name, ignore_missing=False)
            self._identity.assign_project_role_to_user(project_id, user_id, role)

    # --- Quotas -----------------------------------------------------------------

    def apply_quotas(self, project_id: str, quotas: QuotaSet) -> None:
        with _translate_errors("set quotas"):
            self._conn.set_compute_quotas(
                project_id, instances=quotas.instances, cores=quotas.cores, ram=quotas.ram_mb
            )
            self._conn.set_volume_quotas(
                project_id,
                volumes=quotas.volumes,
                gigabytes=quotas.gigabytes,
                snapshots=quotas.snapshots,
            )
            self._conn.set_network_quotas(
                project_id,
                networks=quotas.networks,
                subnets=quotas.subnets,
                routers=quotas.routers,
                floating_ips=quotas.floating_ips,
                ports=quotas.ports,
                security_groups=quotas.security_groups,
            )

    # --- Networking -------------------------------------------------------------

    def create_network(
        self,
        project_id: str,
        name: str,
        cidr: IPv4Network,
        dns_nameservers: Sequence[IPv4Address],
        external_network: str,
        tags: Sequence[str],
    ) -> NetworkTopology:
        net = self._conn.network
        with _translate_errors("create the tenant network"):
            external = net.find_network(external_network, ignore_missing=False)
            network = net.create_network(name=f"{name}-net", project_id=project_id)
            net.set_tags(network, list(tags))
            subnet = net.create_subnet(
                name=f"{name}-subnet",
                network_id=network.id,
                project_id=project_id,
                ip_version=4,
                cidr=str(cidr),
                dns_nameservers=[str(ns) for ns in dns_nameservers],
            )
            router = net.create_router(
                name=f"{name}-router",
                project_id=project_id,
                external_gateway_info={"network_id": external.id},
            )
            net.set_tags(router, list(tags))
            net.add_interface_to_router(router, subnet=subnet.id)
        return NetworkTopology(
            network_id=network.id, subnet_id=subnet.id, router_id=router.id, cidr=str(cidr)
        )

    def find_network(self, project_id: str, tag: str) -> NetworkTopology | None:
        net = self._conn.network
        with _translate_errors("look up the tenant network"):
            network = next(iter(net.networks(project_id=project_id, tags=tag)), None)
            if network is None:
                return None
            router = next(iter(net.routers(project_id=project_id, tags=tag)), None)
            subnet_id = network.subnet_ids[0] if network.subnet_ids else None
            cidr = net.get_subnet(subnet_id).cidr if subnet_id else None
        return NetworkTopology(
            network_id=network.id,
            subnet_id=subnet_id,
            router_id=router.id if router else None,
            cidr=cidr,
        )

    def delete_networks(self, project_id: str) -> None:
        net = self._conn.network
        with _translate_errors("delete tenant networking"):
            # Routers first: a subnet can't be deleted while a router port uses it.
            for router in list(net.routers(project_id=project_id)):
                ports = net.ports(device_id=router.id, device_owner=ROUTER_INTERFACE_OWNER)
                for port in list(ports):
                    net.remove_interface_from_router(router, port=port.id)
                net.delete_router(router, ignore_missing=True)
            for floating_ip in list(net.ips(project_id=project_id)):
                net.delete_ip(floating_ip, ignore_missing=True)
            # Deleting a network also removes its subnets and DHCP/metadata ports.
            for network in list(net.networks(project_id=project_id)):
                net.delete_network(network, ignore_missing=True)
            for group in list(net.security_groups(project_id=project_id)):
                net.delete_security_group(group, ignore_missing=True)

    # --- Usage ------------------------------------------------------------------

    def count_resources(self, project_id: str) -> ResourceUsage:
        with _translate_errors("count tenant resources"):
            servers = self._conn.compute.servers(
                details=False, all_projects=True, project_id=project_id
            )
            volumes = self._conn.block_storage.volumes(
                details=False, all_projects=True, project_id=project_id
            )
            return ResourceUsage(servers=sum(1 for _ in servers), volumes=sum(1 for _ in volumes))
