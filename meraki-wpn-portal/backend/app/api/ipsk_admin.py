"""Admin endpoints for iPSK lifecycle management."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import DbSession, require_admin
from app.db.models import IPSKExpirationLog, User

logger = logging.getLogger(__name__)

router = APIRouter()


class ExpiringIPSKResponse(BaseModel):
    """Response model for expiring iPSK."""

    user_id: int
    email: str
    name: str
    ipsk_id: str
    expires_at: str
    days_remaining: int


class ExtendIPSKRequest(BaseModel):
    """Request to extend iPSK expiration."""

    additional_hours: int


class BulkExtendRequest(BaseModel):
    """Request to bulk extend iPSK expirations."""

    ipsk_ids: list[str]
    additional_hours: int


class IPSKExpirationStatsResponse(BaseModel):
    """Response with expiration statistics."""

    expired_count: int
    expiring_7d_count: int
    expiring_3d_count: int
    expiring_1d_count: int
    total_active: int


@router.post("/admin/ipsk/check-expired")
async def manually_check_expired(
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> dict:
    """Manually trigger expiration check.
    
    Args:
        db: Database session
        admin_user: Current admin user dict
        
    Returns:
        Success response
    """
    logger.info(f"Manual expiration check triggered by {admin_user.get('sub')}")
    
    from app.core.ipsk_monitor import ipsk_monitor

    await ipsk_monitor.check_expirations()

    return {"success": True, "message": "Expiration check completed"}


@router.get("/admin/ipsk/stats", response_model=IPSKExpirationStatsResponse)
async def get_ipsk_stats(
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> IPSKExpirationStatsResponse:
    """Get iPSK expiration statistics.
    
    Args:
        db: Database session
        admin_user: Current admin user
        
    Returns:
        Statistics about iPSK expirations
    """
    now = datetime.now(timezone.utc)

    # Count expired
    expired_count = (
        db.query(User)
        .filter(
            User.ipsk_status == "expired",
        )
        .count()
    )

    # Count expiring in 1, 3, 7 days
    expiring_1d = (
        db.query(User)
        .filter(
            User.ipsk_status == "active",
            User.ipsk_expires_at.isnot(None),
            User.ipsk_expires_at <= now + timedelta(days=1),
            User.ipsk_expires_at > now,
        )
        .count()
    )

    expiring_3d = (
        db.query(User)
        .filter(
            User.ipsk_status == "active",
            User.ipsk_expires_at.isnot(None),
            User.ipsk_expires_at <= now + timedelta(days=3),
            User.ipsk_expires_at > now,
        )
        .count()
    )

    expiring_7d = (
        db.query(User)
        .filter(
            User.ipsk_status == "active",
            User.ipsk_expires_at.isnot(None),
            User.ipsk_expires_at <= now + timedelta(days=7),
            User.ipsk_expires_at > now,
        )
        .count()
    )

    # Total active
    total_active = (
        db.query(User).filter(User.ipsk_status == "active", User.ipsk_id.isnot(None)).count()
    )

    return IPSKExpirationStatsResponse(
        expired_count=expired_count,
        expiring_1d_count=expiring_1d,
        expiring_3d_count=expiring_3d,
        expiring_7d_count=expiring_7d,
        total_active=total_active,
    )


@router.get("/admin/ipsk/expiring", response_model=list[ExpiringIPSKResponse])
async def get_expiring_ipsks(
    days: int = 7,
    *,
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> list[ExpiringIPSKResponse]:
    """Get list of iPSKs expiring within X days.
    
    Args:
        days: Number of days to look ahead
        db: Database session
        admin_user: Current admin user
        
    Returns:
        List of expiring iPSKs
    """
    now = datetime.now(timezone.utc)
    threshold = now + timedelta(days=days)

    users = (
        db.query(User)
        .filter(
            User.ipsk_status == "active",
            User.ipsk_expires_at.isnot(None),
            User.ipsk_expires_at <= threshold,
            User.ipsk_expires_at > now,
        )
        .all()
    )

    return [
        ExpiringIPSKResponse(
            user_id=u.id,
            email=u.email,
            name=u.name or "",
            ipsk_id=u.ipsk_id or "",
            expires_at=u.ipsk_expires_at.isoformat() if u.ipsk_expires_at else "",
            days_remaining=(
                (u.ipsk_expires_at - now).days if u.ipsk_expires_at else 0
            ),
        )
        for u in users
    ]


@router.post("/admin/ipsk/{ipsk_id}/extend")
async def extend_ipsk_expiration(
    ipsk_id: str,
    data: ExtendIPSKRequest,
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> dict:
    """Extend expiration date for an iPSK.
    
    Args:
        ipsk_id: iPSK identifier
        data: Extension request data
        db: Database session
        admin_user: Current admin user dict
        
    Returns:
        Success response with new expiration
        
    Raises:
        HTTPException: If iPSK not found
    """
    user = db.query(User).filter(User.ipsk_id == ipsk_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="iPSK not found"
        )

    # Extend expiration
    if user.ipsk_expires_at:
        user.ipsk_expires_at += timedelta(hours=data.additional_hours)
    else:
        user.ipsk_expires_at = datetime.now(timezone.utc) + timedelta(
            hours=data.additional_hours
        )

    # If was expired, reactivate
    if user.ipsk_status == "expired":
        user.ipsk_status = "active"
        user.expired_at = None

    # Log the action
    log_entry = IPSKExpirationLog(
        user_id=user.id,
        ipsk_id=ipsk_id,
        action="extended",
        details=f'{{"additional_hours": {data.additional_hours}}}',
        performed_by=admin_user.get("sub", "unknown"),
        performed_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()

    logger.info(
        f"iPSK {ipsk_id} extended by {data.additional_hours}h by {admin_user.get('sub')}"
    )

    return {
        "success": True,
        "new_expiration": (
            user.ipsk_expires_at.isoformat() if user.ipsk_expires_at else None
        ),
    }


@router.post("/admin/ipsk/bulk-extend")
async def bulk_extend_ipsks(
    data: BulkExtendRequest,
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> dict:
    """Bulk extend expiration for multiple iPSKs.
    
    Args:
        data: Bulk extension request
        db: Database session
        admin_user: Current admin user dict
        
    Returns:
        Success response with count of extended iPSKs
    """
    extended_count = 0
    now = datetime.now(timezone.utc)

    for ipsk_id in data.ipsk_ids:
        user = db.query(User).filter(User.ipsk_id == ipsk_id).first()
        if user:
            if user.ipsk_expires_at:
                user.ipsk_expires_at += timedelta(hours=data.additional_hours)
            else:
                user.ipsk_expires_at = now + timedelta(hours=data.additional_hours)

            # If was expired, reactivate
            if user.ipsk_status == "expired":
                user.ipsk_status = "active"
                user.expired_at = None

            # Log the action
            log_entry = IPSKExpirationLog(
                user_id=user.id,
                ipsk_id=ipsk_id,
                action="bulk_extended",
                details=f'{{"additional_hours": {data.additional_hours}}}',
                performed_by=admin_user.get("sub", "unknown"),
                performed_at=now,
            )
            db.add(log_entry)
            extended_count += 1

    db.commit()

    logger.info(
        f"Bulk extended {extended_count} iPSKs by {data.additional_hours}h "
        f"by {admin_user.get('sub')}"
    )

    return {
        "success": True,
        "extended_count": extended_count,
        "total_requested": len(data.ipsk_ids),
    }


@router.get("/admin/ipsk/expiration-log")
async def get_expiration_log(
    limit: int = 100,
    *,
    db: DbSession,
    admin_user: dict = Depends(require_admin),
) -> list[dict]:
    """Get recent iPSK expiration log entries.
    
    Args:
        limit: Maximum number of entries to return
        db: Database session
        admin_user: Current admin user
        
    Returns:
        List of log entries
    """
    logs = (
        db.query(IPSKExpirationLog)
        .order_by(IPSKExpirationLog.performed_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "ipsk_id": log.ipsk_id,
            "action": log.action,
            "details": log.details,
            "performed_by": log.performed_by,
            "performed_at": log.performed_at.isoformat() if log.performed_at else None,
        }
        for log in logs
    ]
