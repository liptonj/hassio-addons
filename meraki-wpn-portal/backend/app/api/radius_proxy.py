"""RADIUS API Proxy Router.

Proxies requests from the frontend to the FreeRADIUS API.
This allows the frontend to call /api/radius/* which gets forwarded
to the internal FreeRADIUS service.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.deps import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_radius_client() -> httpx.AsyncClient:
    """Get an async HTTP client for RADIUS API calls."""
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=settings.radius_api_url,
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {settings.radius_api_token}",
            "Content-Type": "application/json",
        }
    )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False
)
async def proxy_to_radius(
    request: Request,
    path: str,
    _user: Any = Depends(require_admin),
) -> Response:
    """Proxy requests to the FreeRADIUS API.
    
    This allows the frontend to call /api/radius/* endpoints
    which get forwarded to the internal FreeRADIUS service.
    """
    settings = get_settings()
    
    if not settings.radius_enabled:
        raise HTTPException(status_code=503, detail="RADIUS integration is not enabled")
    
    if not settings.radius_api_url:
        raise HTTPException(status_code=503, detail="RADIUS API URL is not configured")
    
    if not settings.radius_api_token:
        raise HTTPException(status_code=503, detail="RADIUS API token is not configured")
    
    # Build the target URL
    # The path may already contain /api/ or /api/v1/, so we normalize it
    clean_path = path
    use_v1_prefix = False
    
    if clean_path.startswith("api/v1/"):
        clean_path = clean_path[7:]  # Remove api/v1/
        use_v1_prefix = True
    elif clean_path.startswith("api/"):
        clean_path = clean_path[4:]  # Remove api/
    
    # Endpoints that use /api/v1/ prefix
    v1_endpoints = ["unlang-policies", "eap", "mac-bypass", "psk"]
    
    # Check if this endpoint needs /api/v1/ prefix
    needs_v1 = use_v1_prefix or any(clean_path.startswith(ep) for ep in v1_endpoints)
    
    # Handle special endpoints that don't have /api prefix
    if clean_path == "health":
        target_url = f"{settings.radius_api_url.rstrip('/')}/health"
    elif needs_v1:
        target_url = f"{settings.radius_api_url.rstrip('/')}/api/v1/{clean_path}"
    else:
        target_url = f"{settings.radius_api_url.rstrip('/')}/api/{clean_path}"
    
    # Forward query parameters
    if request.query_params:
        target_url += f"?{request.query_params}"
    
    logger.debug(f"Proxying {request.method} to {target_url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get request body if present
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Forward the request
            response = await client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers={
                    "Authorization": f"Bearer {settings.radius_api_token}",
                    "Content-Type": "application/json",
                }
            )
            
            # Return the response
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type", "application/json"),
            )
            
    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to RADIUS API: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Unable to connect to RADIUS server. Please check that FreeRADIUS is running."
        )
    except httpx.TimeoutException as e:
        logger.error(f"RADIUS API request timed out: {e}")
        raise HTTPException(
            status_code=504, 
            detail="RADIUS API request timed out"
        )
    except Exception as e:
        logger.error(f"RADIUS API proxy error: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"RADIUS API error: {str(e)}"
        )


# Convenience endpoints for common operations with proper OpenAPI documentation

@router.get("/profiles", tags=["RADIUS Profiles"])
async def list_profiles(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """List all RADIUS authorization profiles."""
    return await proxy_to_radius(request, "policies", _user)


@router.get("/authorization-policies", tags=["RADIUS Authorization Policies"])
async def list_authorization_policies(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """List all RADIUS authorization policies (unlang policies)."""
    return await proxy_to_radius(request, "unlang-policies", _user)


@router.get("/eap/config", tags=["RADIUS EAP"])
async def get_eap_config(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """Get EAP configuration."""
    return await proxy_to_radius(request, "eap/config", _user)


@router.get("/eap/methods", tags=["RADIUS EAP"])
async def list_eap_methods(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """List EAP methods."""
    return await proxy_to_radius(request, "eap/methods", _user)


@router.get("/mac-bypass/config", tags=["RADIUS MAC Bypass"])
async def get_mac_bypass_config(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """Get MAC bypass configuration."""
    return await proxy_to_radius(request, "mac-bypass/config", _user)


@router.get("/psk/config", tags=["RADIUS PSK"])
async def get_psk_config(
    request: Request,
    _user: Any = Depends(require_admin),
) -> Response:
    """Get PSK configuration."""
    return await proxy_to_radius(request, "psk/config", _user)
