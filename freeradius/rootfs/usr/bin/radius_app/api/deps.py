"""API dependencies for authentication and database access."""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.database import get_db as get_database_session

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


async def verify_admin_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Verify admin authentication token.
    
    Args
    ----
        request: FastAPI request object
        credentials: Bearer token credentials
    
    Returns
    -------
        Token payload dictionary with user info
    
    Raises
    ------
        HTTPException: If authentication fails
    """
    settings = get_settings()
    
    # Check if token is required
    if not settings.api_auth_token:
        logger.error("API_AUTH_TOKEN not configured - authentication required")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not credentials:
        logger.warning(
            f"Missing authentication from {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Verify token matches configured token
    if token != settings.api_auth_token:
        logger.warning(
            f"Invalid token from {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(
        f"Authenticated request from {request.client.host if request.client else 'unknown'}"
    )
    
    return {
        "sub": "radius_admin",
        "type": "api_token",
        "ip": request.client.host if request.client else None
    }


# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_database_session)]
AdminUser = Annotated[dict, Depends(verify_admin_token)]
