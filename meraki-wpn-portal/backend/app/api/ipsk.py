"""IPSK management endpoints (admin only)."""

import base64
import io
import logging

import qrcode
from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, HAClient
from app.config import get_settings
from app.schemas.ipsk import (
    IPSKCreate,
    IPSKResponse,
    IPSKRevealResponse,
    IPSKStatsResponse,
    IPSKUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def generate_wifi_qr_code(ssid: str, passphrase: str) -> str:
    """Generate a QR code for WiFi connection."""
    wifi_string = f"WIFI:T:WPA;S:{ssid};P:{passphrase};;"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(wifi_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"


@router.get("/ipsks", response_model=list[IPSKResponse])
async def list_ipsks(
    admin: AdminUser,
    ha_client: HAClient,
    network_id: str | None = None,
    ssid_number: int | None = None,
    status_filter: str | None = None,
) -> list[IPSKResponse]:
    """List all IPSKs.

    Args:
        admin: Authenticated admin user
        ha_client: Home Assistant client
        network_id: Optional filter by network ID
        ssid_number: Optional filter by SSID number
        status_filter: Optional filter by status (active, expired, revoked)

    Returns:
        List of IPSKs
    """
    try:
        ipsks = await ha_client.list_ipsks(
            network_id=network_id,
            ssid_number=ssid_number,
            status=status_filter,
        )

        return [
            IPSKResponse(
                id=ipsk.get("id", ""),
                name=ipsk.get("name", ""),
                network_id=ipsk.get("network_id", ""),
                ssid_number=ipsk.get("ssid_number", 0),
                ssid_name=ipsk.get("ssid_name"),
                status=ipsk.get("status", "unknown"),
                group_policy_id=ipsk.get("group_policy_id"),
                expires_at=ipsk.get("expires_at"),
                created_at=ipsk.get("created_at"),
                associated_device_id=ipsk.get("associated_device_id"),
                associated_device_name=ipsk.get("associated_device_name"),
                associated_area_id=ipsk.get("associated_area_id"),
                associated_area_name=ipsk.get("associated_area_name"),
                associated_user=ipsk.get("associated_user"),
                associated_unit=ipsk.get("associated_unit"),
                connected_clients=ipsk.get("connected_clients"),
                last_seen=ipsk.get("last_seen"),
            )
            for ipsk in ipsks
        ]
    except Exception as e:
        logger.exception(f"Failed to list IPSKs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve IPSKs",
        ) from e


@router.post("/ipsks", response_model=IPSKResponse, status_code=status.HTTP_201_CREATED)
async def create_ipsk(
    data: IPSKCreate,
    admin: AdminUser,
    ha_client: HAClient,
) -> IPSKResponse:
    """Create a new IPSK.

    Args:
        data: IPSK creation data
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        Created IPSK
    """
    settings = get_settings()

    try:
        result = await ha_client.create_ipsk(
            name=data.name,
            network_id=data.network_id or settings.default_network_id,
            ssid_number=data.ssid_number if data.ssid_number is not None else settings.default_ssid_number,
            passphrase=data.passphrase,
            duration_hours=data.duration_hours,
            group_policy_id=data.group_policy_id or settings.default_group_policy_id,
            associated_device_id=data.associated_device_id,
            associated_area_id=data.associated_area_id,
            associated_user=data.associated_user,
            associated_unit=data.associated_unit,
        )

        logger.info(f"Created IPSK: {data.name}")

        return IPSKResponse(
            id=result.get("id", ""),
            name=result.get("name", data.name),
            network_id=result.get("network_id", settings.default_network_id),
            ssid_number=result.get("ssid_number", settings.default_ssid_number),
            ssid_name=result.get("ssid_name"),
            status=result.get("status", "active"),
            group_policy_id=result.get("group_policy_id"),
            expires_at=result.get("expires_at"),
            created_at=result.get("created_at"),
            associated_device_id=data.associated_device_id,
            associated_area_id=data.associated_area_id,
            associated_user=data.associated_user,
            associated_unit=data.associated_unit,
        )

    except Exception as e:
        logger.exception(f"Failed to create IPSK: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create IPSK: {str(e)}",
        ) from e


@router.get("/ipsks/{ipsk_id}", response_model=IPSKResponse)
async def get_ipsk(
    ipsk_id: str,
    admin: AdminUser,
    ha_client: HAClient,
) -> IPSKResponse:
    """Get IPSK details.

    Args:
        ipsk_id: IPSK identifier
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        IPSK details
    """
    try:
        ipsk = await ha_client.get_ipsk(ipsk_id, include_passphrase=False)

        return IPSKResponse(
            id=ipsk.get("id", ipsk_id),
            name=ipsk.get("name", ""),
            network_id=ipsk.get("network_id", ""),
            ssid_number=ipsk.get("ssid_number", 0),
            ssid_name=ipsk.get("ssid_name"),
            status=ipsk.get("status", "unknown"),
            group_policy_id=ipsk.get("group_policy_id"),
            expires_at=ipsk.get("expires_at"),
            created_at=ipsk.get("created_at"),
            associated_device_id=ipsk.get("associated_device_id"),
            associated_device_name=ipsk.get("associated_device_name"),
            associated_area_id=ipsk.get("associated_area_id"),
            associated_area_name=ipsk.get("associated_area_name"),
            associated_user=ipsk.get("associated_user"),
            associated_unit=ipsk.get("associated_unit"),
            connected_clients=ipsk.get("connected_clients"),
            last_seen=ipsk.get("last_seen"),
        )

    except Exception as e:
        logger.exception(f"Failed to get IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IPSK not found",
        ) from e


@router.put("/ipsks/{ipsk_id}", response_model=IPSKResponse)
async def update_ipsk(
    ipsk_id: str,
    data: IPSKUpdate,
    admin: AdminUser,
    ha_client: HAClient,
) -> IPSKResponse:
    """Update an existing IPSK.

    Args:
        ipsk_id: IPSK identifier
        data: Update data
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        Updated IPSK
    """
    try:
        result = await ha_client.update_ipsk(
            ipsk_id=ipsk_id,
            name=data.name,
            group_policy_id=data.group_policy_id,
            associated_device_id=data.associated_device_id,
            associated_area_id=data.associated_area_id,
        )

        logger.info(f"Updated IPSK: {ipsk_id}")

        return IPSKResponse(
            id=result.get("id", ipsk_id),
            name=result.get("name", ""),
            network_id=result.get("network_id", ""),
            ssid_number=result.get("ssid_number", 0),
            ssid_name=result.get("ssid_name"),
            status=result.get("status", "unknown"),
            group_policy_id=result.get("group_policy_id"),
            expires_at=result.get("expires_at"),
            created_at=result.get("created_at"),
            associated_device_id=result.get("associated_device_id"),
            associated_area_id=result.get("associated_area_id"),
        )

    except Exception as e:
        logger.exception(f"Failed to update IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update IPSK",
        ) from e


@router.delete("/ipsks/{ipsk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ipsk(
    ipsk_id: str,
    admin: AdminUser,
    ha_client: HAClient,
) -> None:
    """Delete an IPSK.

    Args:
        ipsk_id: IPSK identifier
        admin: Authenticated admin user
        ha_client: Home Assistant client
    """
    try:
        await ha_client.delete_ipsk(ipsk_id)
        logger.info(f"Deleted IPSK: {ipsk_id}")
    except Exception as e:
        logger.exception(f"Failed to delete IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete IPSK",
        ) from e


@router.post("/ipsks/{ipsk_id}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_ipsk(
    ipsk_id: str,
    admin: AdminUser,
    ha_client: HAClient,
) -> None:
    """Revoke an IPSK (mark as inactive without deleting).

    Args:
        ipsk_id: IPSK identifier
        admin: Authenticated admin user
        ha_client: Home Assistant client
    """
    try:
        await ha_client.revoke_ipsk(ipsk_id)
        logger.info(f"Revoked IPSK: {ipsk_id}")
    except Exception as e:
        logger.exception(f"Failed to revoke IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke IPSK",
        ) from e


@router.post("/ipsks/{ipsk_id}/reveal-passphrase", response_model=IPSKRevealResponse)
async def reveal_ipsk_passphrase(
    ipsk_id: str,
    admin: AdminUser,
    ha_client: HAClient,
) -> IPSKRevealResponse:
    """Reveal the passphrase for an IPSK.

    Args:
        ipsk_id: IPSK identifier
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        IPSK with revealed passphrase and QR code
    """
    try:
        ipsk = await ha_client.get_ipsk(ipsk_id, include_passphrase=True)
        passphrase = ipsk.get("passphrase", "")
        ssid_name = ipsk.get("ssid_name", "")

        # Generate QR code
        qr_code = None
        wifi_config_string = None
        if passphrase and ssid_name:
            qr_code = generate_wifi_qr_code(ssid_name, passphrase)
            wifi_config_string = f"WIFI:T:WPA;S:{ssid_name};P:{passphrase};;"

        return IPSKRevealResponse(
            id=ipsk.get("id", ipsk_id),
            name=ipsk.get("name", ""),
            passphrase=passphrase,
            ssid_name=ssid_name,
            qr_code=qr_code,
            wifi_config_string=wifi_config_string,
        )

    except Exception as e:
        logger.exception(f"Failed to reveal passphrase for IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reveal passphrase",
        ) from e


@router.get("/stats", response_model=IPSKStatsResponse)
async def get_ipsk_stats(
    admin: AdminUser,
    ha_client: HAClient,
) -> IPSKStatsResponse:
    """Get IPSK statistics.

    Args:
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        IPSK statistics
    """
    try:
        ipsks = await ha_client.list_ipsks()

        total = len(ipsks)
        active = sum(1 for i in ipsks if i.get("status") == "active")
        expired = sum(1 for i in ipsks if i.get("status") == "expired")
        revoked = sum(1 for i in ipsks if i.get("status") == "revoked")
        online = sum(1 for i in ipsks if i.get("connected_clients", 0) > 0)

        return IPSKStatsResponse(
            total_ipsks=total,
            active_ipsks=active,
            expired_ipsks=expired,
            revoked_ipsks=revoked,
            online_devices=online,
            registrations_today=0,  # Would need to query registration DB
        )

    except Exception as e:
        logger.exception(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics",
        ) from e
