"""Tenant lifecycle: onboarding, tier changes and offboarding."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from ipaddress import IPv4Address

from aura_api.cloud import CloudGateway
from aura_api.domain import (
    MANAGED_TAG,
    TIER_QUOTAS,
    TIER_TAG_PREFIX,
    NetworkTopology,
    Project,
    Tier,
)
from aura_api.errors import (
    AuraError,
    ProvisioningError,
    TenantNotEmptyError,
    TenantNotFoundError,
    UnknownUsersError,
)
from aura_api.schemas import Quotas, Tenant, TenantCreate, TenantNetwork, TenantUpdate

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TenantPolicy:
    """Platform-wide settings applied to every tenant."""

    external_network: str
    dns_nameservers: Sequence[IPv4Address]
    member_role: str


class _Rollback:
    """Collects undo steps while provisioning and runs them newest-first on failure."""

    def __init__(self) -> None:
        self._steps: list[tuple[str, Callable[[], None]]] = []

    def __bool__(self) -> bool:
        return bool(self._steps)

    def push(self, description: str, step: Callable[[], None]) -> None:
        self._steps.append((description, step))

    def run(self) -> None:
        for description, step in reversed(self._steps):
            try:
                step()
            except Exception:
                # Keep unwinding: one failed undo shouldn't strand the rest.
                logger.exception("Rollback step failed", extra={"step": description})


class TenantService:
    def __init__(self, gateway: CloudGateway, policy: TenantPolicy) -> None:
        self._gateway = gateway
        self._policy = policy

    def list_tenants(self) -> list[Tenant]:
        projects = self._gateway.list_projects(MANAGED_TAG)
        return [self._to_tenant(p) for p in sorted(projects, key=lambda p: p.name)]

    def get_tenant(self, name: str) -> Tenant:
        project = self._get_managed_project(name)
        network = self._gateway.find_network(project.id, MANAGED_TAG)
        return self._to_tenant(project, network)

    def create_tenant(self, request: TenantCreate) -> Tenant:
        """Create a project with quotas, a routed network and member grants.

        Inputs are validated before anything is created. If a later step fails,
        the steps already done are undone so a retry starts clean.
        """
        user_ids = self._resolve_users(request.members)
        rollback = _Rollback()
        try:
            project = self._gateway.create_project(
                request.name, request.description, [MANAGED_TAG, request.tier.tag]
            )
            rollback.push("delete project", lambda: self._gateway.delete_project(project.id))

            self._gateway.apply_quotas(project.id, TIER_QUOTAS[request.tier])

            # Registered before creation so a half-built network is still cleaned up.
            rollback.push("delete networks", lambda: self._gateway.delete_networks(project.id))
            network = self._gateway.create_network(
                project_id=project.id,
                name=request.name,
                cidr=request.network_cidr,
                dns_nameservers=self._policy.dns_nameservers,
                external_network=self._policy.external_network,
                tags=[MANAGED_TAG],
            )

            for user_id in user_ids:
                self._gateway.grant_role(project.id, user_id, self._policy.member_role)
        except Exception as exc:
            if not rollback:
                # Nothing was created (for example the name is taken): surface as-is.
                raise
            logger.exception("Onboarding failed; rolling back", extra={"tenant": request.name})
            rollback.run()
            reason = exc.detail if isinstance(exc, AuraError) else "unexpected error"
            raise ProvisioningError(
                f"Onboarding '{request.name}' failed and was rolled back: {reason}"
            ) from exc

        logger.info("Tenant onboarded", extra={"tenant": request.name, "tier": request.tier.value})
        return self._to_tenant(project, network)

    def update_tenant(self, name: str, update: TenantUpdate) -> Tenant:
        project = self._get_managed_project(name)
        tags = None
        if update.tier is not None:
            self._gateway.apply_quotas(project.id, TIER_QUOTAS[update.tier])
            tags = [t for t in project.tags if not t.startswith(TIER_TAG_PREFIX)]
            tags.append(update.tier.tag)
        if tags is not None or update.description is not None:
            project = self._gateway.update_project(
                project.id, description=update.description, tags=tags
            )
        logger.info("Tenant updated", extra={"tenant": name})
        return self.get_tenant(project.name)

    def delete_tenant(self, name: str) -> None:
        """Offboard a tenant. Refuses while it still has servers or volumes."""
        project = self._get_managed_project(name)
        usage = self._gateway.count_resources(project.id)
        if not usage.is_empty:
            raise TenantNotEmptyError(name, usage.servers, usage.volumes)
        self._gateway.delete_networks(project.id)
        self._gateway.delete_project(project.id)
        logger.info("Tenant offboarded", extra={"tenant": name})

    def _get_managed_project(self, name: str) -> Project:
        project = self._gateway.find_project(name)
        # Unmanaged projects are reported as missing so this API can't touch them.
        if project is None or MANAGED_TAG not in project.tags:
            raise TenantNotFoundError(name)
        return project

    def _resolve_users(self, names: Sequence[str]) -> list[str]:
        resolved = {name: self._gateway.find_user_id(name) for name in names}
        missing = [name for name, user_id in resolved.items() if user_id is None]
        if missing:
            raise UnknownUsersError(missing)
        return [user_id for user_id in resolved.values() if user_id is not None]

    @staticmethod
    def _to_tenant(project: Project, network: NetworkTopology | None = None) -> Tenant:
        tier = Tier.from_tags(project.tags)
        return Tenant(
            id=project.id,
            name=project.name,
            description=project.description,
            enabled=project.enabled,
            tier=tier,
            quotas=Quotas.from_domain(TIER_QUOTAS[tier]) if tier else None,
            network=TenantNetwork(
                network_id=network.network_id,
                subnet_id=network.subnet_id,
                router_id=network.router_id,
                cidr=network.cidr,
            )
            if network
            else None,
        )
