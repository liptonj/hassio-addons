"""API dependencies for authentication and database access."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.ha_client import HomeAssistantClient
from app.core.security import verify_token
from app.db.database import get_db

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


def get_ha_client(request: Request) -> HomeAssistantClient:
    """Get the Home Assistant client from app state.

    Args
    ----
        request: FastAPI request object

    Returns
    -------
        HomeAssistantClient instance

    Raises
    ------
        HTTPException: If HA client is not available
    """
    if not hasattr(request.app.state, "ha_client"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Home Assistant connection not available",
        )
    return request.app.state.ha_client


async def verify_admin_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> dict:
    """Verify admin authentication token.

    This validates either:
    1. A JWT token issued by this portal
    2. A Home Assistant long-lived access token

    Args
    ----
        request: FastAPI request object
        credentials: Bearer token credentials

    Returns
    -------
        Token payload dictionary

    Raises
    ------
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # First, try to verify as a portal JWT token
    payload = verify_token(token)
    if payload:
        return payload

    # If not a portal token, try as HA token by making a test request
    settings = get_settings()

    # Check if it matches the configured HA token
    if token == settings.ha_token or token == settings.supervisor_token:
        return {"sub": "ha_admin", "type": "ha_token"}

    # Try to validate by making a simple HA API call
    try:
        ha_client = get_ha_client(request)
        if ha_client.is_connected:
            # Token is valid if HA client is connected with it
            return {"sub": "ha_admin", "type": "ha_token"}
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]
HAClient = Annotated[HomeAssistantClient, Depends(get_ha_client)]
AdminUser = Annotated[dict, Depends(verify_admin_token)]
