"""OAuth/SSO authentication handlers for Duo Universal SDK v4 and Microsoft Entra ID."""

import logging
from typing import Any

from authlib.integrations.starlette_client import OAuth

from app.config import get_settings

logger = logging.getLogger(__name__)

# OAuth client for Entra ID (Duo uses its own SDK)
oauth = OAuth()

# Global Duo client (initialized on app startup)
_duo_client = None


def init_oauth() -> None:
    """Initialize OAuth providers based on configuration."""
    settings = get_settings()
    
    if not settings.enable_oauth:
        logger.info("OAuth is disabled")
        return
    
    if settings.oauth_provider == "duo":
        init_duo_universal()
    elif settings.oauth_provider == "entra":
        init_entra_oauth()
    else:
        logger.warning(f"Unknown OAuth provider: {settings.oauth_provider}")


def init_duo_universal() -> None:
    """Initialize Duo Universal SDK v4 (OIDC-based).
    
    Uses the official Duo Universal Python SDK with Universal Prompt support.
    See: https://duo.com/docs/duoweb
    """
    global _duo_client
    settings = get_settings()
    
    if not all([settings.duo_client_id, settings.duo_client_secret, settings.duo_api_hostname]):
        logger.error("Duo Universal enabled but missing required configuration")
        return
    
    try:
        import duo_universal
        
        # Create Duo client with Web SDK v4
        _duo_client = duo_universal.Client(
            client_id=settings.duo_client_id,
            client_secret=settings.duo_client_secret,
            host=settings.duo_api_hostname,
            redirect_uri=settings.oauth_callback_url,
        )
        
        # Health check to verify Duo is accessible
        _duo_client.health_check()
        
        logger.info("Duo Universal SDK v4 initialized successfully")
        
    except ImportError:
        logger.error("duo_universal package not installed. Install with: pip install duo-universal")
        raise
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid Duo configuration: {e}")
        raise ValueError(f"Failed to initialize Duo: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error initializing Duo: {e}")
        raise RuntimeError(f"Duo initialization failed: {e}") from e


def get_duo_client():
    """Get the initialized Duo Universal client."""
    if _duo_client is None:
        raise RuntimeError("Duo Universal client not initialized. Call init_oauth() first.")
    return _duo_client


def init_entra_oauth() -> None:
    """Initialize Microsoft Entra ID (Azure AD) OAuth 2.0 integration."""
    settings = get_settings()
    
    if not all([settings.entra_client_id, settings.entra_client_secret, settings.entra_tenant_id]):
        logger.error("Entra ID OAuth enabled but missing required configuration")
        return
    
    # Microsoft Entra ID endpoints
    tenant_id = settings.entra_tenant_id
    
    oauth.register(
        name="entra",
        client_id=settings.entra_client_id,
        client_secret=settings.entra_client_secret,
        server_metadata_url=f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
        },
    )
    
    logger.info("Microsoft Entra ID OAuth initialized")


async def get_oauth_user_info(provider: str, token: dict[str, Any]) -> dict[str, Any]:
    """Get user information from OAuth provider.
    
    Args:
        provider: OAuth provider name ("duo" or "entra")
        token: OAuth access token response (for Entra) or decoded token (for Duo)
        
    Returns:
        User information dictionary with standardized fields:
        - email: User email address
        - name: User full name
        - sub: Unique user identifier
    """
    try:
        if provider == "duo":
            # Duo Universal SDK returns decoded ID token directly
            # The token parameter here is actually the decoded_token from exchange_authorization_code_for_2fa_result
            return {
                "email": token.get("email", token.get("preferred_username", "")),
                "name": token.get("name", ""),
                "sub": token.get("sub", token.get("preferred_username", "")),
                "provider": "duo",
            }
            
        elif provider == "entra":
            client = oauth.create_client("entra")
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                token=token,
            )
            user_data = resp.json()
            
            return {
                "email": user_data.get("mail") or user_data.get("userPrincipalName", ""),
                "name": user_data.get("displayName", ""),
                "sub": user_data.get("id", ""),
                "provider": "entra",
            }
            
        else:
            raise ValueError(f"Unknown OAuth provider: {provider}")
            
    except (KeyError, ValueError) as e:
        logger.error(f"Invalid response from {provider}: {e}")
        raise ValueError(f"Failed to get user info: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error getting user info from {provider}: {e}")
        raise RuntimeError(f"OAuth user info retrieval failed: {e}") from e
