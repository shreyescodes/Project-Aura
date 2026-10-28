"""In-memory CloudGateway for tests, with failure injection."""

import itertools
from collections.abc import Sequence
from dataclasses import replace
from ipaddress import IPv4Address, IPv4Network

from aura_api.domain import NetworkTopology, Project, QuotaSet, ResourceUsage
from aura_api.errors import CloudError, TenantAlreadyExistsError


class FakeCloudGateway:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.quotas: dict[str, QuotaSet] = {}
        self.networks: dict[str, NetworkTopology] = {}
        self.network_tags: dict[str, list[str]] = {}
        self.users: dict[str, str] = {}
        self.role_grants: set[tuple[str, str, str]] = set()
        self.usage: dict[str, ResourceUsage] = {}
        self.calls: list[str] = []
        self.fail_on: set[str] = set()
        self.reachable = True
        self._ids = itertools.count(1)

    # --- test helpers -----------------------------------------------------------

    def add_user(self, name: str) -> str:
        user_id = f"user-{next(self._ids)}"
        self.users[name] = user_id
        return user_id

    def add_project(self, name: str, tags: Sequence[str] = ()) -> Project:
        project = Project(f"proj-{next(self._ids)}", name, "", True, list(tags))
        self.projects[project.id] = project
        return project

    def _record(self, operation: str) -> None:
        self.calls.append(operation)
        if operation in self.fail_on:
            raise CloudError(f"injected failure in {operation}")

    # --- CloudGateway -----------------------------------------------------------

    def check_connection(self) -> None:
        if not self.reachable:
            raise CloudError("OpenStack request failed while trying to authenticate.")

    def find_project(self, name: str) -> Project | None:
        return next((p for p in self.projects.values() if p.name == name), None)

    def list_projects(self, tag: str) -> list[Project]:
        return [p for p in self.projects.values() if tag in p.tags]

    def create_project(self, name: str, description: str, tags: Sequence[str]) -> Project:
        self._record("create_project")
        if self.find_project(name):
            raise TenantAlreadyExistsError(name)
        project = Project(f"proj-{next(self._ids)}", name, description, True, list(tags))
        self.projects[project.id] = project
        return project

    def update_project(
        self, project_id: str, *, description: str | None = None, tags: Sequence[str] | None = None
    ) -> Project:
        self._record("update_project")
        project = self.projects[project_id]
        if description is not None:
            project = replace(project, description=description)
        if tags is not None:
            project = replace(project, tags=list(tags))
        self.projects[project_id] = project
        return project

    def delete_project(self, project_id: str) -> None:
        self._record("delete_project")
        self.projects.pop(project_id, None)
        self.quotas.pop(project_id, None)
        self.role_grants = {g for g in self.role_grants if g[0] != project_id}

    def apply_quotas(self, project_id: str, quotas: QuotaSet) -> None:
        self._record("apply_quotas")
        self.quotas[project_id] = quotas

    def find_user_id(self, name: str) -> str | None:
        return self.users.get(name)

    def grant_role(self, project_id: str, user_id: str, role_name: str) -> None:
        self._record("grant_role")
        self.role_grants.add((project_id, user_id, role_name))

    def create_network(
        self,
        project_id: str,
        name: str,
        cidr: IPv4Network,
        dns_nameservers: Sequence[IPv4Address],
        external_network: str,
        tags: Sequence[str],
    ) -> NetworkTopology:
        self._record("create_network")
        topology = NetworkTopology(f"net-{name}", f"subnet-{name}", f"router-{name}", str(cidr))
        self.networks[project_id] = topology
        self.network_tags[project_id] = list(tags)
        return topology

    def find_network(self, project_id: str, tag: str) -> NetworkTopology | None:
        if tag not in self.network_tags.get(project_id, []):
            return None
        return self.networks.get(project_id)

    def delete_networks(self, project_id: str) -> None:
        self._record("delete_networks")
        self.networks.pop(project_id, None)
        self.network_tags.pop(project_id, None)

    def count_resources(self, project_id: str) -> ResourceUsage:
        return self.usage.get(project_id, ResourceUsage(servers=0, volumes=0))
