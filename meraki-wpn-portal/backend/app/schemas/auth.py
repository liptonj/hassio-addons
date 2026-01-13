"""Pydantic schemas for authentication."""

from pydantic import BaseModel


class Token(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Local admin login request."""

    username: str
    password: str


class OAuthSettings(BaseModel):
    """OAuth configuration settings."""

    enable_oauth: bool = False
    oauth_provider: str = "none"
    oauth_admin_only: bool = False
    oauth_auto_provision: bool = True
    
    # Duo settings
    duo_client_id: str = ""
    duo_client_secret: str = ""
    duo_api_hostname: str = ""
    
    # Entra ID settings
    entra_client_id: str = ""
    entra_client_secret: str = ""
    entra_tenant_id: str = ""
    
    oauth_callback_url: str = ""
