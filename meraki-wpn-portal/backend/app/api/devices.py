"""Device and area management endpoints (admin only)."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, HAClient
from app.schemas.device import AreaResponse, DeviceAssociationRequest, DeviceResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ha/devices", response_model=list[DeviceResponse])
async def list_ha_devices(
    admin: AdminUser,
    ha_client: HAClient,
) -> list[DeviceResponse]:
    """List all Home Assistant devices.

    Args:
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        List of HA devices
    """
    try:
        devices = await ha_client.get_devices()

        return [
            DeviceResponse(
                id=device.get("id", ""),
                name=device.get("name", "Unknown"),
                name_by_user=device.get("name_by_user"),
                manufacturer=device.get("manufacturer"),
                model=device.get("model"),
                area_id=device.get("area_id"),
            )
            for device in devices
        ]

    except Exception as e:
        logger.exception(f"Failed to list HA devices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve devices from Home Assistant",
        ) from e


@router.get("/ha/areas", response_model=list[AreaResponse])
async def list_ha_areas(
    admin: AdminUser,
    ha_client: HAClient,
) -> list[AreaResponse]:
    """List all Home Assistant areas.

    Args:
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        List of HA areas
    """
    try:
        areas = await ha_client.get_areas()

        return [
            AreaResponse(
                area_id=area.get("area_id", ""),
                name=area.get("name", "Unknown"),
                aliases=area.get("aliases", []),
                picture=area.get("picture"),
            )
            for area in areas
        ]

    except Exception as e:
        logger.exception(f"Failed to list HA areas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve areas from Home Assistant",
        ) from e


@router.post("/ipsks/{ipsk_id}/associate", status_code=status.HTTP_200_OK)
async def associate_ipsk(
    ipsk_id: str,
    data: DeviceAssociationRequest,
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Associate an IPSK with a Home Assistant device or area.

    Args:
        ipsk_id: IPSK identifier
        data: Association data (device_id or area_id)
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        Updated IPSK information
    """
    if not data.device_id and not data.area_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either device_id or area_id must be provided",
        )

    try:
        result = await ha_client.update_ipsk(
            ipsk_id=ipsk_id,
            associated_device_id=data.device_id,
            associated_area_id=data.area_id,
        )

        logger.info(f"Associated IPSK {ipsk_id} with device={data.device_id} area={data.area_id}")

        return {
            "success": True,
            "ipsk_id": ipsk_id,
            "associated_device_id": data.device_id,
            "associated_area_id": data.area_id,
        }

    except Exception as e:
        logger.exception(f"Failed to associate IPSK {ipsk_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to associate IPSK",
        ) from e


@router.get("/ipsk-options")
async def get_ipsk_options(
    admin: AdminUser,
    ha_client: HAClient,
) -> dict:
    """Get available options for IPSK creation.

    This includes networks, SSIDs, group policies, and areas.

    Args:
        admin: Authenticated admin user
        ha_client: Home Assistant client

    Returns:
        Available options for IPSK creation
    """
    try:
        options = await ha_client.get_ipsk_options()
        return options

    except Exception as e:
        logger.exception(f"Failed to get IPSK options: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve IPSK options",
        ) from e
