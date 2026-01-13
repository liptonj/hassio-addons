"""Public registration endpoints."""

import base64
import io
import logging
from datetime import datetime, timezone

import qrcode
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.api.deps import DbSession, HAClient
from app.config import get_settings
from app.core.invite_codes import InviteCodeManager
from app.core.security import (
    decrypt_passphrase,
    encrypt_passphrase,
    generate_passphrase,
)
from app.db.database import get_session_local
from app.db.models import Registration, SplashAccess, User
from app.schemas.registration import (
    MyNetworkResponse,
    RegistrationRequest,
    RegistrationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/splash")
async def splash_landing(
    request: Request,
    client_mac: str | None = None,
    client_ip: str | None = None,
    node_mac: str | None = None,
    ap_mac: str | None = None,
    ap_name: str | None = None,
    ap_tags: str | None = None,
    base_grant_url: str | None = None,
    user_continue_url: str | None = None,
    login_url: str | None = None,
    continue_url: str | None = None,
) -> RedirectResponse:
    """Handle Meraki captive portal splash page redirect.

    Meraki sends users here with device information. We capture the MAC
    address and grant URL, then redirect to a splash landing page where
    users can either register (new) or retrieve credentials (returning).

    Meraki URL Parameters (all optional)
    ------------------------------------
    client_mac : str
        MAC address of the connecting device
    client_ip : str
        IP address assigned to device
    node_mac : str
        MAC address of the access point (older param)
    ap_mac : str
        MAC address of the access point
    ap_name : str
        Name of the access point
    ap_tags : str
        Tags associated with the access point
    base_grant_url : str
        URL to call to grant network access
    user_continue_url : str
        URL user wanted to visit originally
    login_url : str
        Meraki login URL for captive portal
    continue_url : str
        Alternative continue URL parameter

    Returns
    -------
    RedirectResponse
        Redirect to /splash-landing (or /register) with parameters
    """
    import urllib.parse

    # Use continue_url if user_continue_url not provided
    final_continue_url = user_continue_url or continue_url

    logger.info(
        f"Splash page access: MAC={client_mac}, IP={client_ip}, "
        f"AP={ap_mac or node_mac}, AP_Name={ap_name}, "
        f"grant_url={base_grant_url}"
    )

    # Save splash access to database for tracking
    try:
        SessionLocal = get_session_local()
        with SessionLocal() as db:
            splash_access = SplashAccess(
                client_mac=client_mac,
                client_ip=client_ip,
                ap_mac=ap_mac or node_mac,
                ap_name=ap_name,
                ap_tags=ap_tags,
                node_mac=node_mac,
                login_url=login_url,
                continue_url=final_continue_url,
                user_agent=request.headers.get("user-agent"),
                request_ip=request.client.host if request.client else None,
            )
            db.add(splash_access)
            db.commit()
            logger.debug(f"Saved splash access record for MAC: {client_mac}")
    except Exception as e:
        # Don't fail the splash redirect if logging fails
        logger.warning(f"Failed to save splash access: {e}")

    # Build redirect URL with parameters for frontend
    # Pass through the Meraki authentication parameters
    params = []
    if client_mac:
        params.append(f"mac={client_mac}")
    if login_url:
        # Sign-on splash: contains mauth token for POST authentication
        encoded_login = urllib.parse.quote(login_url, safe='')
        params.append(f"login_url={encoded_login}")
    if base_grant_url:
        # Click-through splash: simple GET to grant access
        encoded_grant = urllib.parse.quote(base_grant_url, safe='')
        params.append(f"grant_url={encoded_grant}")
    if final_continue_url:
        encoded_continue = urllib.parse.quote(final_continue_url, safe='')
        params.append(f"continue_url={encoded_continue}")

    # Redirect to splash landing page with captured parameters
    # This page gives users options: Register (new) or Retrieve (returning)
    redirect_url = "/splash-landing"
    if params:
        redirect_url += "?" + "&".join(params)

    logger.info(f"Redirecting splash to: {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/grant-access")
async def grant_network_access(
    request: Request,
    login_url: str | None = None,
    base_grant_url: str | None = None,
    client_mac: str | None = None,
    continue_url: str | None = None,
) -> dict:
    """Grant network access via Meraki's Captive Portal API.

    Supports two modes based on Meraki ExCAP examples:

    1. Click-through Splash (base_grant_url):
       - Simply GET the base_grant_url to grant access
       - No authentication required
       - Used with "Click-through splash page" setting

    2. Sign-on Splash (login_url):
       - POST username/password to login_url
       - Used with "Sign-on splash page" setting

    See: https://github.com/meraki/js-splash (click-through)
    See: https://github.com/dexterlabora/excap (sign-on)

    Parameters
    ----------
    login_url : str | None
        The login URL from Meraki (for sign-on splash)
    base_grant_url : str | None
        The grant URL from Meraki (for click-through splash)
    client_mac : str | None
        MAC address of the device
    continue_url : str | None
        URL to redirect user after granting access

    Returns
    -------
    dict
        Grant result with redirect URL
    """
    import httpx

    # Determine which grant method to use
    grant_url = base_grant_url or login_url
    if not grant_url:
        return {
            "success": False,
            "error": "No grant URL provided (need login_url or base_grant_url)",
        }

    logger.info(
        f"Granting network access for MAC {client_mac} via "
        f"{'base_grant_url' if base_grant_url else 'login_url'}"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if base_grant_url:
                # Click-through: Simple GET to grant URL
                # Per js-splash example: just redirect to base_grant_url
                final_url = base_grant_url
                if continue_url:
                    separator = "&" if "?" in base_grant_url else "?"
                    final_url = f"{base_grant_url}{separator}continue_url={continue_url}"

                response = await client.get(final_url, follow_redirects=False)

                logger.info(
                    f"Click-through grant response: {response.status_code}, "
                    f"Location: {response.headers.get('Location', 'N/A')}"
                )

            else:
                # Sign-on: POST credentials to login_url
                # Per excap example: POST with username, password, success_url
                base_url = str(request.base_url).rstrip('/')
                success_url = f"{base_url}/api/splash-success"

                response = await client.post(
                    login_url,  # type: ignore[arg-type]
                    data={
                        "username": client_mac or "guest",
                        "password": "wifi-guest-access",
                        "success_url": success_url,
                        "continue_url": continue_url or "https://google.com",
                    },
                    follow_redirects=False,
                )

                logger.info(
                    f"Sign-on grant response: {response.status_code}, "
                    f"Location: {response.headers.get('Location', 'N/A')}"
                )

            # Success is typically a 302 redirect to success_url or continue_url
            if response.status_code in (200, 302, 303):
                redirect_location = response.headers.get("Location")
                return {
                    "success": True,
                    "message": "Network access granted",
                    "redirect_url": redirect_location,
                    "continue_url": continue_url or "https://google.com",
                }
            else:
                return {
                    "success": False,
                    "error": f"Grant failed: HTTP {response.status_code}",
                    "body": response.text[:500] if response.text else None,
                }

    except httpx.TimeoutException:
        logger.warning("Grant request timed out - may still have succeeded")
        return {
            "success": True,
            "message": "Network access request sent (timeout, but may have succeeded)",
            "continue_url": continue_url or "https://google.com",
        }
    except Exception as e:
        logger.error(f"Failed to grant access: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/splash-success")
async def splash_success_page(
    logout_url: str | None = None,
) -> dict:
    """Handle Meraki success redirect after authentication.

    Meraki redirects here after successful login with the logout_url parameter.

    Parameters
    ----------
    logout_url : str | None
        URL to call to logout (end session)

    Returns
    -------
    dict
        Success status with logout URL
    """
    logger.info(f"Splash success - logout_url: {logout_url}")
    return {
        "success": True,
        "message": "You are now connected to WiFi",
        "logout_url": logout_url,
    }


def generate_wifi_qr_code(ssid: str, passphrase: str) -> str:
    """Generate a QR code for WiFi connection.

    Args:
        ssid: WiFi network name
        passphrase: WiFi password

    Returns:
        Base64-encoded PNG image data URL
    """
    # WiFi QR code format
    wifi_string = f"WIFI:T:WPA;S:{ssid};P:{passphrase};;"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def sanitize_name_for_ipsk(name: str) -> str:
    """Sanitize a name for use in IPSK identifier.

    Args:
        name: User's full name

    Returns:
        Sanitized name suitable for IPSK naming
    """
    # Take first name and remove special characters
    first_name = name.split()[0] if name else "User"
    sanitized = "".join(c for c in first_name if c.isalnum())
    return sanitized[:20]  # Limit length


@router.post("/register", response_model=RegistrationResponse)
async def register_for_wifi(
    request: Request,
    data: RegistrationRequest,
    db: DbSession,
    ha_client: HAClient,
) -> RegistrationResponse:
    """Register for WiFi access and receive credentials.

    This endpoint creates a new IPSK for the registrant and returns
    their WiFi credentials including a QR code for easy connection.

    Args:
        request: FastAPI request object
        data: Registration request data
        db: Database session
        ha_client: Home Assistant client

    Returns:
        Registration response with WiFi credentials

    Raises:
        HTTPException: If registration fails
    """
    settings = get_settings()

    # Check if self-registration is enabled
    if not settings.auth_self_registration:
        if not data.invite_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Self-registration is disabled. An invite code is required.",
            )

    # Validate invite code if provided or required
    if data.invite_code or settings.auth_invite_codes:
        if data.invite_code:
            invite_manager = InviteCodeManager(db)
            is_valid, error = invite_manager.validate_code(data.invite_code)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error,
                )

    # Check if email already registered - return existing credentials instead of error
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user and existing_user.ipsk_id:
        logger.info(f"User {data.email} already registered, returning existing credentials")

        # Try to get the stored passphrase from our database
        passphrase = ""
        if existing_user.ipsk_passphrase_encrypted:
            try:
                passphrase = decrypt_passphrase(existing_user.ipsk_passphrase_encrypted)
            except Exception as e:
                logger.warning(f"Could not decrypt passphrase for {data.email}: {e}")

        if passphrase:
            ssid_name = existing_user.ssid_name or settings.standalone_ssid_name or "WiFi"

            # Generate QR code for existing credentials
            qr_code = generate_wifi_qr_code(ssid_name, passphrase)
            wifi_config_string = f"WIFI:T:WPA;S:{ssid_name};P:{passphrase};;"

            return RegistrationResponse(
                success=True,
                ipsk_id=existing_user.ipsk_id,
                ipsk_name=existing_user.ipsk_name or "",
                ssid_name=ssid_name,
                passphrase=passphrase,
                qr_code=qr_code,
                wifi_config_string=wifi_config_string,
            )

        # If we couldn't decrypt, direct to My Network page
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered. Use 'My Network' to retrieve your credentials.",
        )

    # Validate unit if required
    unit_identifier = data.unit or data.area_id
    if settings.require_unit_number and not unit_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unit/room selection is required",
        )

    # Create registration record
    registration = Registration(
        name=data.name,
        email=data.email,
        unit=data.unit,
        area_id=data.area_id,
        invite_code=data.invite_code,
        status="pending",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
    )
    db.add(registration)
    db.commit()

    try:
        # Generate IPSK name
        sanitized_name = sanitize_name_for_ipsk(data.name)
        if data.unit:
            ipsk_name = f"Unit-{data.unit}-{sanitized_name}"
        elif data.area_id:
            ipsk_name = f"Area-{data.area_id}-{sanitized_name}"
        else:
            ipsk_name = f"User-{sanitized_name}"

        # Generate passphrase
        passphrase = generate_passphrase(settings.passphrase_length)

        # Create IPSK via Home Assistant
        ipsk_result = await ha_client.create_ipsk(
            name=ipsk_name,
            network_id=settings.default_network_id,
            ssid_number=settings.default_ssid_number,
            passphrase=passphrase,
            duration_hours=settings.default_ipsk_duration_hours or None,
            group_policy_id=settings.default_group_policy_id or None,
            associated_user=data.name,
            associated_unit=data.unit,
            associated_area_id=data.area_id,
        )

        # Get SSID name from result or use default
        ssid_name = ipsk_result.get("ssid_name", "Resident-WiFi")

        # Generate QR code
        qr_code = generate_wifi_qr_code(ssid_name, passphrase)
        wifi_config_string = f"WIFI:T:WPA;S:{ssid_name};P:{passphrase};;"

        # Update registration as completed
        registration.status = "completed"
        registration.ipsk_id = ipsk_result.get("id")
        registration.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Encrypt passphrase for storage (Meraki API doesn't return it later)
        encrypted_passphrase = encrypt_passphrase(passphrase)

        # Create or update user record
        if existing_user:
            existing_user.ipsk_id = ipsk_result.get("id")
            existing_user.ipsk_name = ipsk_name
            existing_user.ipsk_passphrase_encrypted = encrypted_passphrase
            existing_user.ssid_name = ssid_name
            existing_user.unit = data.unit
            existing_user.area_id = data.area_id
        else:
            user = User(
                name=data.name,
                email=data.email,
                unit=data.unit,
                area_id=data.area_id,
                ipsk_id=ipsk_result.get("id"),
                ipsk_name=ipsk_name,
                ipsk_passphrase_encrypted=encrypted_passphrase,
                ssid_name=ssid_name,
            )
            db.add(user)
        db.commit()

        # Mark invite code as used
        if data.invite_code:
            invite_manager = InviteCodeManager(db)
            invite_manager.use_code(data.invite_code)

        logger.info(f"Registration completed for {data.email} (IPSK: {ipsk_name})")

        return RegistrationResponse(
            success=True,
            ipsk_id=ipsk_result.get("id"),
            ipsk_name=ipsk_name,
            ssid_name=ssid_name,
            passphrase=passphrase,
            qr_code=qr_code,
            wifi_config_string=wifi_config_string,
        )

    except Exception as e:
        logger.exception(f"Registration failed for {data.email}: {e}")
        registration.status = "failed"
        registration.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again or contact support.",
        ) from e


@router.get("/my-network", response_model=MyNetworkResponse)
async def get_my_network(
    email: str,
    db: DbSession,
    ha_client: HAClient,
    verification_code: str | None = None,
) -> MyNetworkResponse:
    """Retrieve existing WiFi credentials for a registered user.

    Args:
        email: Registered email address
        db: Database session
        ha_client: Home Assistant client
        verification_code: Optional verification code for email verification

    Returns:
        Network credentials

    Raises:
        HTTPException: If user not found or verification fails
    """
    # TODO: Implement email verification flow using verification_code
    _ = verification_code  # Reserved for future email verification

    user = db.query(User).filter(User.email == email).first()

    if not user or not user.ipsk_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this email",
        )

    # Get passphrase from our stored encrypted version (Meraki doesn't return it)
    passphrase = ""
    if user.ipsk_passphrase_encrypted:
        try:
            passphrase = decrypt_passphrase(user.ipsk_passphrase_encrypted)
        except Exception as e:
            logger.warning(f"Could not decrypt passphrase for {email}: {e}")

    # Get IPSK status from Meraki
    try:
        ipsk_data = await ha_client.get_ipsk(user.ipsk_id)
        ipsk_status = ipsk_data.get("status", "active")
        connected_clients = ipsk_data.get("connected_clients", 0)
    except Exception as e:
        logger.warning(f"Could not get IPSK status from Meraki for {email}: {e}")
        ipsk_status = "unknown"
        connected_clients = 0

    ssid_name = user.ssid_name or settings.standalone_ssid_name or "Resident-WiFi"

    # Generate QR code if passphrase available
    qr_code = None
    if passphrase:
        qr_code = generate_wifi_qr_code(ssid_name, passphrase)

    return MyNetworkResponse(
        ipsk_name=user.ipsk_name or "",
        ssid_name=ssid_name,
        passphrase=passphrase,
        status=ipsk_status,
        connected_devices=connected_clients,
        qr_code=qr_code,
    )


@router.get("/areas")
async def get_public_areas(ha_client: HAClient) -> list[dict]:
    """Get available areas/units for registration dropdown.

    This endpoint returns areas from Home Assistant that can be
    used for unit selection during registration.

    Args:
        ha_client: Home Assistant client

    Returns:
        List of areas
    """
    settings = get_settings()

    if settings.unit_source == "manual_list":
        # Return manual units as area-like objects
        return [
            {"area_id": unit, "name": unit}
            for unit in settings.get_manual_units_list()
        ]

    if settings.unit_source == "ha_areas":
        try:
            areas = await ha_client.get_areas()
            return [
                {"area_id": area.get("area_id"), "name": area.get("name")}
                for area in areas
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch HA areas: {e}")
            return []

    # Free text mode - return empty list
    return []


# ============================================================================
# WiFi Configuration Endpoints
# ============================================================================


@router.get("/wifi-config/{ipsk_id}")
async def get_wifi_config(
    ipsk_id: str,
    db: DbSession,
    ha_client: HAClient,
) -> dict:
    """Get WiFi configuration options for an IPSK.

    Returns QR code, mobileconfig data, and connection instructions.

    Parameters
    ----------
    ipsk_id : str
        The IPSK ID to get configuration for
    db : DbSession
        Database session
    ha_client : HAClient
        Meraki/HA client

    Returns
    -------
    dict
        WiFi configuration options
    """
    from app.core.wifi_config import get_wifi_config_data

    settings = get_settings()

    # Find the user/registration with this IPSK
    user = db.query(User).filter(User.ipsk_id == ipsk_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IPSK not found",
        )

    # Get IPSK details from Meraki
    try:
        ipsk = await ha_client.get_ipsk(ipsk_id)
        if not ipsk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IPSK not found in Meraki Dashboard",
            )

        ssid_name = ipsk.get("ssid_name") or settings.standalone_ssid_name or "WiFi"
        passphrase = ipsk.get("passphrase", "")

        if not passphrase:
            # Try to reveal the passphrase
            reveal_result = await ha_client.get_ipsk(ipsk_id, reveal=True)
            passphrase = reveal_result.get("passphrase", "")

        config_data = get_wifi_config_data(
            ssid=ssid_name,
            passphrase=passphrase,
            ipsk_name=user.ipsk_name or ipsk.get("name", "WiFi"),
            organization=settings.property_name,
        )

        return {
            "success": True,
            "ssid": ssid_name,
            "ipsk_name": user.ipsk_name,
            "qr_code": config_data["qr_code"],
            "wifi_string": config_data["wifi_string"],
            "has_mobileconfig": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get WiFi config for IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WiFi configuration",
        ) from e


@router.get("/wifi-config/{ipsk_id}/mobileconfig")
async def download_mobileconfig(
    ipsk_id: str,
    db: DbSession,
    ha_client: HAClient,
):
    """Download Apple .mobileconfig profile for WiFi.

    This endpoint returns a .mobileconfig file that can be installed
    on iOS/iPadOS/macOS devices to automatically configure WiFi.

    Parameters
    ----------
    ipsk_id : str
        The IPSK ID
    db : DbSession
        Database session
    ha_client : HAClient
        Meraki/HA client

    Returns
    -------
    Response
        .mobileconfig file download
    """
    from fastapi.responses import Response

    from app.core.wifi_config import generate_apple_mobileconfig

    settings = get_settings()

    # Find the user with this IPSK
    user = db.query(User).filter(User.ipsk_id == ipsk_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IPSK not found",
        )

    # Get IPSK details
    try:
        ipsk = await ha_client.get_ipsk(ipsk_id, reveal=True)
        if not ipsk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IPSK not found in Meraki Dashboard",
            )

        ssid_name = ipsk.get("ssid_name") or settings.standalone_ssid_name or "WiFi"
        passphrase = ipsk.get("passphrase", "")

        mobileconfig = generate_apple_mobileconfig(
            ssid=ssid_name,
            passphrase=passphrase,
            organization=settings.property_name,
            display_name=f"{settings.property_name} WiFi",
            description=f"WiFi configuration for {user.ipsk_name or 'your network'}",
        )

        # Return as downloadable file
        filename = f"{settings.property_name.replace(' ', '-')}-WiFi.mobileconfig"
        return Response(
            content=mobileconfig,
            media_type="application/x-apple-aspen-config",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate mobileconfig for IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate WiFi profile",
        ) from e
