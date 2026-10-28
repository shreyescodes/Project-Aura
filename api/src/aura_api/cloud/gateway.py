"""The operations the service layer needs from the cloud.

Keeping this a narrow Protocol lets the service be tested against an in-memory
fake, and confines openstacksdk specifics to one module.
"""

from collections.abc import Sequence
from ipaddress import IPv4Address, IPv4Network
from typing import Protocol

from aura_api.domain import NetworkTopology, Project, QuotaSet, ResourceUsage


class CloudGateway(Protocol):
    def check_connection(self) -> None:
        """Authenticate against Keystone. Raises CloudError on failure."""

    def find_project(self, name: str) -> Project | None: ...

    def list_projects(self, tag: str) -> list[Project]: ...

    def create_project(self, name: str, description: str, tags: Sequence[str]) -> Project:
        """Raises TenantAlreadyExistsError if the name is taken."""

    def update_project(
        self, project_id: str, *, description: str | None = None, tags: Sequence[str] | None = None
    ) -> Project: ...

    def delete_project(self, project_id: str) -> None: ...

    def apply_quotas(self, project_id: str, quotas: QuotaSet) -> None: ...

    def find_user_id(self, name: str) -> str | None: ...

    def grant_role(self, project_id: str, user_id: str, role_name: str) -> None: ...

    def create_network(
        self,
        project_id: str,
        name: str,
        cidr: IPv4Network,
        dns_nameservers: Sequence[IPv4Address],
        external_network: str,
        tags: Sequence[str],
    ) -> NetworkTopology:
        """Create a network, subnet and router uplinked to external_network."""

    def find_network(self, project_id: str, tag: str) -> NetworkTopology | None: ...

    def delete_networks(self, project_id: str) -> None:
        """Delete every router, floating IP, network and security group the project owns."""

    def count_resources(self, project_id: str) -> ResourceUsage: ...
