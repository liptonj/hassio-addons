"""SQL Counter API endpoints.

Manages session time limits via FreeRADIUS SQL Counter module.
Per FreeRADIUS SQL Counter documentation:
https://www.freeradius.org/documentation/freeradius-server/4.0~alpha1/howto/modules/sqlcounter/index.html
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from radius_app.api.deps import AdminUser, DbSession
from radius_app.core.sql_counter_generator import SqlCounterGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql-counter", tags=["sql-counter"])


class SessionLimitsRequest(BaseModel):
    """Request schema for setting session time limits."""
    username: str = Field(..., description="Username (PSK ID or email)")
    max_all_session: Optional[int] = Field(None, ge=0, description="Total session time limit (seconds)")
    max_daily_session: Optional[int] = Field(None, ge=0, description="Daily session time limit (seconds)")
    max_monthly_session: Optional[int] = Field(None, ge=0, description="Monthly session time limit (seconds)")


@router.post("/set-limits", status_code=status.HTTP_200_OK)
async def set_session_limits(
    limits: SessionLimitsRequest,
    admin: AdminUser,
    db: DbSession,
    portal_db_url: Optional[str] = None,
) -> dict:
    """Set session time limits for a user.
    
    Per FreeRADIUS SQL Counter documentation:
    - Max-All-Session: Total session time limit (never resets)
    - Max-Daily-Session: Daily session time limit (resets daily)
    - Max-Monthly-Session: Monthly session time limit (resets monthly)
    
    Limits are stored in radcheck table and enforced by SQL Counter module.
    
    Args:
        limits: Session limit request
        admin: Admin user
        db: Database session
        portal_db_url: Portal database URL (optional)
        
    Returns:
        Sync statistics
    """
    logger.info(
        f"Admin {admin.get('sub', 'unknown')} setting session limits for {limits.username}: "
        f"total={limits.max_all_session}, daily={limits.max_daily_session}, monthly={limits.max_monthly_session}"
    )
    
    try:
        generator = SqlCounterGenerator()
        stats = generator.sync_session_limits_to_radcheck(
            db=db,
            username=limits.username,
            max_all_session=limits.max_all_session,
            max_daily_session=limits.max_daily_session,
            max_monthly_session=limits.max_monthly_session,
            portal_db_url=portal_db_url,
        )
        
        if stats["errors"]:
            logger.warning(f"Session limit sync completed with {len(stats['errors'])} errors")
        
        return {
            "success": True,
            "username": limits.username,
            "radcheck_entries": stats["radcheck_entries"],
            "errors": stats["errors"],
            "message": f"Set {stats['radcheck_entries']} session limits for {limits.username}",
        }
    except Exception as e:
        logger.error(f"Failed to set session limits: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set session limits: {str(e)}"
        )


@router.get("/config", status_code=status.HTTP_200_OK)
async def get_sql_counter_config(
    admin: AdminUser,
    db: DbSession,
    sql_module_instance: str = "sql",
) -> dict:
    """Get SQL Counter module configuration.
    
    Returns the generated SQL Counter configuration that would be written to
    mods-enabled/sqlcounter.conf.
    
    Args:
        admin: Admin user
        db: Database session
        sql_module_instance: Name of SQL module instance to use
        
    Returns:
        SQL Counter configuration
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} requesting SQL Counter config")
    
    try:
        generator = SqlCounterGenerator()
        config = generator.generate_sql_counter_config(db, sql_module_instance)
        
        return {
            "config": config,
            "sql_module_instance": sql_module_instance,
            "message": "SQL Counter configuration generated",
        }
    except Exception as e:
        logger.error(f"Failed to generate SQL Counter config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL Counter config: {str(e)}"
        )
