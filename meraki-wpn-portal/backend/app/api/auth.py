"""Authentication endpoints."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.api.deps import DbSession, HAClient
from app.core.oauth import get_oauth_user_info, oauth
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.database import get_db
from app.db.models import User
from app.schemas.auth import LoginRequest, Token

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBasic()


# ============================================================================
# Schemas for User Authentication
# ============================================================================

class UserSignupRequest(BaseModel):
    """Request body for user signup."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)
    unit: str | None = None


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Response with user info."""

    id: int
    email: str
    name: str
    unit: str | None = None
    is_admin: bool = False
    has_ipsk: bool = False
    ipsk_name: str | None = None
    ssid_name: str | None = None


class UserToken(BaseModel):
    """JWT token response with user info."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/auth/login", response_model=Token)
async def local_admin_login(credentials: LoginRequest) -> Token:
    """Local admin login with username and password.
    
    Default credentials: admin/admin (CHANGE IN PRODUCTION!)
    
    Args:
        credentials: Username and password
        
    Returns:
        JWT access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    settings = get_settings()
    
    # Check username
    if credentials.username != settings.admin_username:
        logger.warning(f"Failed login attempt for username: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check password
    password_valid = False
    if settings.admin_password_hash:
        # Use hashed password if available
        password_valid = verify_password(credentials.password, settings.admin_password_hash)
    else:
        # Fall back to plain text comparison (for initial setup)
        password_valid = credentials.password == settings.admin_password
    
    if not password_valid:
        logger.warning(f"Failed login attempt for username: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": credentials.username,
            "type": "admin",
            "auth_method": "local",
        },
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    
    logger.info(f"Local admin login successful for: {credentials.username}")
    
    return Token(access_token=access_token)


# ============================================================================
# User Authentication (Local)
# ============================================================================

@router.post("/auth/user/signup", response_model=UserToken)
async def user_signup(
    request: UserSignupRequest,
    db: Session = Depends(get_db),
) -> UserToken:
    """Register a new user account.

    Users can create an account to authenticate for device registration
    and to retrieve their WiFi credentials later.

    Args:
        request: User signup details (email, password, name)
        db: Database session

    Returns:
        JWT token and user info

    Raises:
        HTTPException: If email already exists
    """
    # Check if email already exists
    existing = db.execute(
        select(User).where(User.email == request.email)
    ).scalar_one_or_none()

    if existing:
        if existing.password_hash:
            # User already has an account
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email already exists. Please login instead.",
            )
        # User exists from previous registration without password - update them
        existing.password_hash = hash_password(request.password)
        existing.name = request.name
        if request.unit:
            existing.unit = request.unit
        db.commit()
        db.refresh(existing)
        user = existing
        logger.info(f"Existing user updated with password: {user.email}")
    else:
        # Create new user
        user = User(
            email=request.email,
            name=request.name,
            password_hash=hash_password(request.password),
            unit=request.unit,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"New user registered: {user.email}")

    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "type": "user",
            "is_admin": user.is_admin,
        },
    )

    return UserToken(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            unit=user.unit,
            is_admin=user.is_admin,
            has_ipsk=bool(user.ipsk_id),
            ipsk_name=user.ipsk_name,
            ssid_name=user.ssid_name,
        ),
    )


@router.post("/auth/user/login", response_model=UserToken)
async def user_login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> UserToken:
    """Login with email and password.

    Args:
        request: Login credentials (email, password)
        db: Database session

    Returns:
        JWT token and user info

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    user = db.execute(
        select(User).where(User.email == request.email)
    ).scalar_one_or_none()

    if not user or not user.password_hash:
        logger.warning(f"Login failed - user not found: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(request.password, user.password_hash):
        logger.warning(f"Login failed - invalid password: {request.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # Create JWT token
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "type": "user" if not user.is_admin else "admin",
            "is_admin": user.is_admin,
        },
    )

    logger.info(f"User login successful: {user.email}")

    return UserToken(
        access_token=access_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            unit=user.unit,
            is_admin=user.is_admin,
            has_ipsk=bool(user.ipsk_id),
            ipsk_name=user.ipsk_name,
            ssid_name=user.ssid_name,
        ),
    )


@router.get("/auth/user/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Get current authenticated user info.

    Args:
        request: Request with Authorization header
        db: Database session

    Returns:
        Current user info

    Raises:
        HTTPException: If not authenticated
    """
    from app.core.security import verify_token

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = auth_header.split(" ")[1]
    payload = verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("user_id")
    if not user_id:
        # Might be an admin token without user_id
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User token required",
        )

    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        unit=user.unit,
        is_admin=user.is_admin,
        has_ipsk=bool(user.ipsk_id),
        ipsk_name=user.ipsk_name,
        ssid_name=user.ssid_name,
    )


@router.post("/auth/user/create-ipsk", response_model=dict)
async def create_user_ipsk(
    request: Request,
    db: DbSession,
    ha_client: HAClient,
) -> dict:
    """Automatically create an iPSK for the logged-in user.
    
    This streamlined endpoint creates an iPSK for users who already have an account,
    eliminating the need to re-enter their information.
    
    Args:
        request: Request with Authorization header
        db: Database session
    
    Returns:
        WiFi credentials including SSID, passphrase, and QR code
    
    Raises:
        HTTPException: If not authenticated or iPSK creation fails
    """
    from app.core.security import verify_token, generate_passphrase
    from app.api.registration import sanitize_name_for_ipsk, generate_wifi_qr_code, encrypt_passphrase
    
    # Verify user authentication
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User token required",
        )
    
    user = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    # Check if user already has an iPSK
    if user.ipsk_id:
        logger.info(f"User {user.email} already has iPSK {user.ipsk_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an iPSK. Visit /my-network to view your credentials.",
        )
    
    settings = get_settings()
    try:
        # Generate IPSK name
        sanitized_name = sanitize_name_for_ipsk(user.name)
        if user.unit:
            ipsk_name = f"Unit-{user.unit}-{sanitized_name}"
        else:
            ipsk_name = f"User-{sanitized_name}"
        
        # Generate passphrase
        passphrase = generate_passphrase(settings.passphrase_length)
        
        # Create IPSK via Home Assistant/Meraki
        ipsk_result = await ha_client.create_ipsk(
            name=ipsk_name,
            network_id=settings.default_network_id,
            ssid_number=settings.default_ssid_number,
            passphrase=passphrase,
            duration_hours=settings.default_ipsk_duration_hours or None,
            group_policy_id=settings.default_group_policy_id or None,
            associated_user=user.name,
            associated_unit=user.unit,
        )
        
        # Get SSID name from result or use default
        ssid_name = ipsk_result.get("ssid_name", settings.standalone_ssid_name or "WiFi")
        
        # Generate QR code
        qr_code = generate_wifi_qr_code(ssid_name, passphrase)
        wifi_config_string = f"WIFI:T:WPA;S:{ssid_name};P:{passphrase};;"
        
        # Encrypt passphrase for storage
        encrypted_passphrase = encrypt_passphrase(passphrase)
        
        # Update user record with iPSK info
        user.ipsk_id = ipsk_result.get("id")
        user.ipsk_name = ipsk_name
        user.ssid_name = ssid_name
        user.ipsk_passphrase_encrypted = encrypted_passphrase
        db.commit()
        
        logger.info(f"Auto-created iPSK for user {user.email} (IPSK: {ipsk_name})")
        
        return {
            "success": True,
            "ipsk_id": ipsk_result.get("id"),
            "ipsk_name": ipsk_name,
            "ssid_name": ssid_name,
            "passphrase": passphrase,
            "qr_code": qr_code,
            "wifi_config_string": wifi_config_string,
        }
        
    except Exception as e:
        logger.exception(f"Failed to create iPSK for user {user.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create iPSK. Please try again or contact support.",
        ) from e


@router.post("/auth/token", response_model=Token)
async def get_admin_token(ha_token: str) -> Token:
    """Exchange a Home Assistant token for a portal admin token.

    This endpoint allows admin users to authenticate using their
    Home Assistant long-lived access token.

    Args:
        ha_token: Home Assistant long-lived access token

    Returns:
        JWT token for portal admin access

    Raises:
        HTTPException: If token validation fails
    """
    settings = get_settings()

    # Validate the HA token
    if ha_token != settings.ha_token and ha_token != settings.supervisor_token:
        # In a full implementation, we would validate against HA API
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Home Assistant token",
        )

    # Create a portal JWT token
    access_token = create_access_token(
        data={"sub": "ha_admin", "type": "admin"},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )

    logger.info("Admin token issued")
    return Token(access_token=access_token)


@router.get("/auth/verify")
async def verify_authentication() -> dict:
    """Verify current authentication status and available auth methods.

    Returns:
        Authentication status and configuration
    """
    settings = get_settings()
    
    auth_methods = {
        "local": True,  # Always available
        "oauth": settings.enable_oauth,
        "homeassistant": settings.is_homeassistant,
    }
    
    oauth_config = None
    if settings.enable_oauth:
        oauth_config = {
            "provider": settings.oauth_provider,
            "admin_only": settings.oauth_admin_only,
        }
    
    return {
        "authenticated": False,
        "auth_methods": auth_methods,
        "oauth_config": oauth_config,
        "message": "Use POST /api/auth/login for local auth or GET /api/auth/login/{provider} for OAuth",
    }


# OAuth endpoints
@router.get("/auth/login/{provider}")
async def oauth_login(provider: str, request: Request, username: str):
    """Initiate OAuth login flow.
    
    For Duo Universal SDK v4, this generates the authorization URL and redirects
    the user to Duo's Universal Prompt.
    
    Args:
        provider: OAuth provider ("duo" or "entra")
        request: FastAPI request object
        username: Username for Duo authentication
        
    Returns:
        Redirect to OAuth provider authorization page
    """
    settings = get_settings()
    
    if not settings.enable_oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth is not enabled",
        )
    
    if provider != settings.oauth_provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider {provider} is not configured",
        )
    
    if provider == "duo":
        from app.core.oauth import get_duo_client
        
        try:
            duo_client = get_duo_client()
            
            # Generate state for CSRF protection
            state = duo_client.generate_state()
            
            # Store state in session for validation
            request.session["duo_state"] = state
            request.session["duo_username"] = username
            
            # Create authorization URL
            auth_url = duo_client.create_auth_url(username, state)
            
            logger.info(f"Duo Universal login initiated for user: {username}")
            
            # Redirect to Duo Universal Prompt
            return RedirectResponse(url=auth_url)
            
        except (ValueError, KeyError) as e:
            logger.error(f"Duo configuration error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Duo authentication configuration error: {str(e)}",
            ) from e
        except Exception as e:
            logger.error(f"Unexpected Duo login error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initiate Duo authentication: {str(e)}",
            ) from e
    
    elif provider == "entra":
        # Get the Entra OAuth client
        client = oauth.create_client(provider)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OAuth client for {provider} not initialized",
            )
        
        # Redirect to OAuth provider
        redirect_uri = settings.oauth_callback_url
        return await client.authorize_redirect(request, redirect_uri)
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown OAuth provider: {provider}",
        )


@router.get("/auth/callback")
async def oauth_callback(request: Request, state: str | None = None, duo_code: str | None = None):
    """Handle OAuth callback from provider.
    
    For Duo Universal SDK v4, this exchanges the authorization code for an
    ID token and validates the authentication.
    
    Args:
        request: FastAPI request object with OAuth response
        state: State parameter for CSRF protection
        duo_code: Authorization code from Duo (Duo only)
        
    Returns:
        Redirect to admin dashboard with token in URL fragment
    """
    settings = get_settings()
    
    if not settings.enable_oauth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth is not enabled",
        )
    
    provider = settings.oauth_provider
    
    try:
        if provider == "duo":
            from app.core.oauth import get_duo_client
            
            # Validate state parameter
            saved_state = request.session.get("duo_state")
            username = request.session.get("duo_username")
            
            if not saved_state or not username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid session. Please try logging in again.",
                )
            
            if state != saved_state:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid state parameter. Possible CSRF attack.",
                )
            
            duo_client = get_duo_client()
            
            # Exchange authorization code for 2FA result
            decoded_token = duo_client.exchange_authorization_code_for_2fa_result(
                duo_code,
                username,
            )
            
            # Extract user info from decoded token
            user_info = await get_oauth_user_info("duo", decoded_token)
            
            # Clear session data
            request.session.pop("duo_state", None)
            request.session.pop("duo_username", None)
            
            # Create portal JWT token
            access_token = create_access_token(
                data={
                    "sub": user_info["email"] or username,
                    "name": user_info["name"],
                    "type": "oauth",
                    "provider": "duo",
                    "duo_username": username,
                },
                expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            )
            
            logger.info(f"Duo Universal authentication successful for {username}")
            
            # Redirect to admin dashboard with token
            return RedirectResponse(
                url=f"/admin#token={access_token}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        
        elif provider == "entra":
            # Get the OAuth client
            client = oauth.create_client(provider)
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"OAuth client for {provider} not initialized",
                )
            
            # Exchange authorization code for access token
            token = await client.authorize_access_token(request)
            
            # Get user information from OAuth provider
            user_info = await get_oauth_user_info(provider, token)
            
            # Create portal JWT token
            access_token = create_access_token(
                data={
                    "sub": user_info["email"],
                    "name": user_info["name"],
                    "type": "oauth",
                    "provider": provider,
                },
                expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            )
            
            logger.info(f"OAuth login successful for {user_info['email']} via {provider}")
            
            # Redirect to admin dashboard with token
            return RedirectResponse(
                url=f"/admin#token={access_token}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown OAuth provider: {provider}",
            )
        
    except (ValueError, KeyError) as e:
        logger.error(f"OAuth configuration or response error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authentication configuration error: {str(e)}",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected OAuth callback error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth authentication failed: {str(e)}",
        ) from e


# ============================================================================
# Universal Login
# ============================================================================

class EmailLookupRequest(BaseModel):
    """Request to lookup email for universal login."""
    
    email: EmailStr


class EmailLookupResponse(BaseModel):
    """Response for email lookup."""
    
    found: bool
    auth_method: str  # 'local', 'oauth', 'none'
    oauth_provider: str | None = None
    has_account: bool
    has_ipsk: bool
    is_admin: bool = False
    suggested_action: str  # 'login', 'signup', 'sso_redirect'


@router.post("/auth/lookup-email", response_model=EmailLookupResponse)
async def lookup_email(
    data: EmailLookupRequest,
    db: Session = Depends(get_db),
) -> EmailLookupResponse:
    """Determine authentication method for an email address.
    
    This endpoint supports the universal login flow where users enter
    their email first, and the system determines how they should authenticate.
    
    Args:
        data: Email lookup request
        db: Database session
        
    Returns:
        Email lookup response with auth method and suggested action
    """
    settings = get_settings()
    
    # Check if user exists
    user = db.query(User).filter(User.email == data.email).first()
    
    if user:
        # Determine auth method
        if user.auth_type == "oauth":
            return EmailLookupResponse(
                found=True,
                auth_method="oauth",
                oauth_provider=user.oauth_provider or settings.oauth_provider,
                has_account=True,
                has_ipsk=bool(user.ipsk_id),
                is_admin=user.is_admin,
                suggested_action="sso_redirect"
            )
        # Local authentication
        return EmailLookupResponse(
            found=True,
            auth_method="local",
            oauth_provider=None,
            has_account=bool(user.password_hash),
            has_ipsk=bool(user.ipsk_id),
            is_admin=user.is_admin,
            suggested_action="login" if user.password_hash else "signup"
        )
    
    # User not found - suggest signup
    return EmailLookupResponse(
        found=False,
        auth_method="none",
        oauth_provider=None,
        has_account=False,
        has_ipsk=False,
        is_admin=False,
        suggested_action="signup"
    )
