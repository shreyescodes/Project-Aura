"""Liveness, readiness and metrics endpoints (unauthenticated, for probes and scrapers)."""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from aura_api.dependencies import GatewayDep
from aura_api.schemas import HealthStatus

router = APIRouter(tags=["operations"])


@router.get("/healthz", response_model=HealthStatus)
def liveness() -> HealthStatus:
    """The process is up. Deliberately checks nothing else."""
    return HealthStatus(status="ok")


@router.get(
    "/readyz",
    response_model=HealthStatus,
    responses={502: {"description": "OpenStack is unreachable"}},
)
def readiness(gateway: GatewayDep) -> HealthStatus:
    """Ready to serve: Keystone accepts our credentials."""
    gateway.check_connection()
    return HealthStatus(status="ready")


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
