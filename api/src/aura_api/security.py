"""API key authentication for the /v1 routes."""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from aura_api.config import Settings, get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    api_key: Annotated[str | None, Depends(_api_key_header)],
) -> None:
    # Compare against every key in constant time so the response time doesn't
    # reveal how much of a guess matched, or which key slot it hit.
    presented = (api_key or "").encode()
    matched = False
    for key in settings.api_keys:
        matched |= secrets.compare_digest(presented, key.get_secret_value().encode())
    if not api_key or not matched:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid X-API-Key header is required.",
        )
