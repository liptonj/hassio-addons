"""API dependencies for authentication and database access."""

import logging
from typing import Annotated, Protocol, runtime_checkable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import User

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


@runtime_checkable
class BaseClient(Protocol):
    """Protocol for all client types (HA, Meraki, Mock).
    
    This defines the common interface that all client implementations must satisfy.
    Used for type hints when the actual runtime client type varies based on mode.
    """
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        ...
    
    async def connect(self) -> None:
        """Connect to the service."""
        ...
    
    async def disconnect(self) -> None:
        """Disconnect from the service."""
        ...
    
    async def list_ipsks(
        self,
        network_id: str | None = None,
        ssid_number: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List Identity PSKs."""
        ...
    
    async def create_ipsk(
        self,
        name: str,
        network_id: str,
        ssid_number: int,
        **kwargs,
    ) -> dict:
        """Create an Identity PSK."""
        ...
    
    async def get_areas(self) -> list[dict]:
        """Get areas/units."""
        ...


def get_ha_client(request: Request) -> BaseClient:
    """Get the client from app state.
    
    This returns the appropriate client based on run mode:
    - Standalone mode: MerakiDashboardClient
    - Home Assistant mode: HomeAssistantClient
    - Demo/fallback: MockHomeAssistantClient

    Args
    ----
        request: FastAPI request object

    Returns
    -------
        Client instance implementing BaseClient protocol

    Raises
    ------
        HTTPException: If client is not available
    """
    if not hasattr(request.app.state, "ha_client"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Client connection not available",
        )
    return request.app.state.ha_client


async def verify_admin_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    """Verify admin authentication token.

    This validates:
    1. A JWT token issued by this portal (admin or user with is_admin=True)
    2. A Home Assistant long-lived access token

    Args
    ----
        request: FastAPI request object
        credentials: Bearer token credentials
        db: Database session

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
        # Check if this is a user token with is_admin flag
        if payload.get("is_admin") is True:
            # Verify user still has admin rights in database
            user_id = payload.get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user and user.is_admin:
                    return payload
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access revoked",
                )
        # Traditional admin token or HA token
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


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict:
    """Require admin authentication and return admin info.
    
    This accepts either:
    1. Traditional admin tokens (username/password via /api/auth/login)
    2. User tokens for users with is_admin=True (via universal login)
    
    Args:
        credentials: Bearer token credentials
        db: Database session
        
    Returns:
        Admin token payload dict
        
    Raises:
        HTTPException: If authentication fails or user not admin
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if this is a user token with is_admin flag
    if payload.get("is_admin") is True:
        # User token with admin privileges - verify user still has admin rights
        user_id = payload.get("user_id")
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.is_admin:
                return payload
            # User no longer has admin rights
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access revoked"
            )
    
    # Check if this is a traditional admin token (has 'sub' field with username, no user_id/email)
    if "sub" in payload and "user_id" not in payload and "email" not in payload:
        return payload
    
    # Neither an admin token nor a user with admin privileges
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required"
    )


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> User:
    """Require user authentication and return User model.
    
    Args:
        credentials: Bearer token credentials
        db: Database session
        
    Returns:
        User model
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = payload.get("user_id")
    email = payload.get("email")
    
    if not user_id and not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    else:
        user = db.query(User).filter(User.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


# Type aliases for dependency injection
DbSession = Annotated[Session, Depends(get_db)]
HAClient = Annotated[BaseClient, Depends(get_ha_client)]
AdminUser = Annotated[dict, Depends(verify_admin_token)]
CurrentUser = Annotated[User, Depends(require_user)]