"""Tenant lifecycle endpoints.

Handlers are plain `def`: openstacksdk is blocking, so FastAPI runs them in its
thread pool instead of on the event loop.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Response, status

from aura_api.dependencies import TenantServiceDep
from aura_api.schemas import TENANT_NAME_PATTERN, Tenant, TenantCreate, TenantUpdate
from aura_api.security import require_api_key

PathName = Annotated[str, Path(pattern=TENANT_NAME_PATTERN)]

_PROBLEM: dict[str, Any] = {"content": {"application/problem+json": {}}}

router = APIRouter(
    prefix="/v1/tenants",
    tags=["tenants"],
    dependencies=[Depends(require_api_key)],
    responses={
        401: {"description": "Missing or invalid API key"},
        502: {"description": "OpenStack request failed", **_PROBLEM},
    },
)


@router.get("")
def list_tenants(service: TenantServiceDep) -> list[Tenant]:
    """List tenants managed by this service."""
    return service.list_tenants()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "A project with this name already exists", **_PROBLEM},
        422: {"description": "Invalid request or unknown member", **_PROBLEM},
    },
)
def create_tenant(body: TenantCreate, response: Response, service: TenantServiceDep) -> Tenant:
    """Onboard a tenant: project, tier quotas, routed network and member grants."""
    tenant = service.create_tenant(body)
    response.headers["Location"] = f"{router.prefix}/{tenant.name}"
    return tenant


@router.get("/{name}", responses={404: {"description": "Unknown tenant", **_PROBLEM}})
def get_tenant(name: PathName, service: TenantServiceDep) -> Tenant:
    return service.get_tenant(name)


@router.patch("/{name}", responses={404: {"description": "Unknown tenant", **_PROBLEM}})
def update_tenant(name: PathName, body: TenantUpdate, service: TenantServiceDep) -> Tenant:
    """Change a tenant's description or tier. A tier change re-applies quotas."""
    return service.update_tenant(name, body)


@router.delete(
    "/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Unknown tenant", **_PROBLEM},
        409: {"description": "Tenant still owns servers or volumes", **_PROBLEM},
    },
)
def delete_tenant(name: PathName, service: TenantServiceDep) -> None:
    """Offboard a tenant. Refused while it still owns servers or volumes."""
    service.delete_tenant(name)
