"""SQL module sync API endpoints.

Syncs PSK data from portal database to FreeRADIUS radcheck/radreply tables
for dynamic SQL-based authentication.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from radius_app.api.deps import AdminUser, DbSession
from radius_app.core.sql_config_generator import SqlConfigGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sql", tags=["sql"])


@router.post("/sync-psk", status_code=status.HTTP_200_OK)
async def sync_psk_to_sql(
    admin: AdminUser,
    db: DbSession,
    portal_db_url: Optional[str] = None,
) -> dict:
    """Sync PSK data from portal database to radcheck/radreply tables.
    
    Per FreeRADIUS SQL documentation:
    - radcheck: Stores Cleartext-Password for authentication
    - radreply: Stores reply attributes (Cisco-AVPair with UDN, etc.)
    
    This allows FreeRADIUS to query PSK data directly from SQL at runtime.
    
    Args:
        admin: Admin user
        db: Database session
        portal_db_url: Portal database URL (optional, uses configured DB if not provided)
        
    Returns:
        Sync statistics
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} syncing PSK to SQL tables")
    
    try:
        generator = SqlConfigGenerator()
        stats = generator.sync_psk_to_radcheck(db, portal_db_url)
        
        if stats["errors"]:
            logger.warning(f"PSK sync completed with {len(stats['errors'])} errors")
        
        return {
            "success": True,
            "users_synced": stats["users_synced"],
            "radcheck_entries": stats["radcheck_entries"],
            "radreply_entries": stats["radreply_entries"],
            "errors": stats["errors"],
            "message": f"Synced {stats['users_synced']} users to radcheck/radreply tables",
        }
    except Exception as e:
        logger.error(f"Failed to sync PSK to SQL: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync PSK data: {str(e)}"
        )


@router.get("/config", status_code=status.HTTP_200_OK)
async def get_sql_config(
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get SQL module configuration.
    
    Returns the generated SQL module configuration that would be written to
    mods-enabled/sql.
    
    Args:
        admin: Admin user
        db: Database session
        
    Returns:
        SQL module configuration
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} requesting SQL config")
    
    try:
        generator = SqlConfigGenerator()
        config = generator.generate_sql_module_config(db)
        
        return {
            "config": config,
            "message": "SQL module configuration generated",
        }
    except Exception as e:
        logger.error(f"Failed to generate SQL config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL config: {str(e)}"
        )


@router.get("/schema", status_code=status.HTTP_200_OK)
async def get_sql_schema(
    admin: AdminUser,
) -> dict:
    """Get SQL schema creation script.
    
    Returns the SQL schema script for creating radcheck/radreply tables
    per FreeRADIUS SQL documentation.
    
    Args:
        admin: Admin user
        
    Returns:
        SQL schema script
    """
    logger.info(f"Admin {admin.get('sub', 'unknown')} requesting SQL schema")
    
    try:
        generator = SqlConfigGenerator()
        schema = generator.generate_sql_schema_script()
        
        return {
            "schema": schema,
            "message": "SQL schema script generated",
        }
    except Exception as e:
        logger.error(f"Failed to generate SQL schema: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL schema: {str(e)}"
        )
