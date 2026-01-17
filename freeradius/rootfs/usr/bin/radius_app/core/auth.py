"""Authentication and authorization."""

import logging
import os

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


def verify_token(authorization: str = Header(None)) -> bool:
    """Verify API token from header.
    
    Security: API_AUTH_TOKEN MUST be configured. No bypass allowed.
    This enforces authentication for all API endpoints.
    
    Args:
        authorization: Authorization header value
    
    Returns:
        True if token is valid
        
    Raises:
        HTTPException:
            - 500: If API_AUTH_TOKEN is not configured (server misconfigured)
            - 401: If authorization header is missing or invalid
    """
    api_token = os.getenv("API_AUTH_TOKEN", "")
    if not api_token:
        logger.error("API_AUTH_TOKEN not configured - rejecting request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_AUTH_TOKEN not configured - server misconfigured. "
                   "Administrator must set API_AUTH_TOKEN environment variable."
        )
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use: Bearer <token>"
        )
    
    token = authorization.replace("Bearer ", "")
    if token != api_token:
        logger.warning("Invalid token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    return True
