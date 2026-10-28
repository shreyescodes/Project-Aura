"""Application factory. Run with: uvicorn aura_api.main:app"""

import logging

from fastapi import FastAPI

from aura_api import __version__
from aura_api.config import Settings, get_settings
from aura_api.errors import register_exception_handlers
from aura_api.observability import configure_logging, install_request_middleware
from aura_api.routes import health, tenants

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    if not settings.api_keys:
        logger.warning("AURA_API_KEYS is empty; every /v1 request will be rejected")

    app = FastAPI(
        title="Aura Platform API",
        version=__version__,
        description="Tenant onboarding and lifecycle management for the Aura OpenStack cloud.",
    )
    register_exception_handlers(app)
    install_request_middleware(app)
    app.include_router(health.router)
    app.include_router(tenants.router)
    return app


app = create_app()
