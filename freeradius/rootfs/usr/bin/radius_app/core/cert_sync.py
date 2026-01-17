"""Certificate synchronization service.

Syncs user certificates from Portal database to FreeRADIUS for EAP-TLS validation.
Watches for changes and automatically updates FreeRADIUS configuration.
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from radius_app.config import get_settings
from radius_app.core.eap_config_generator import EapConfigGenerator
from radius_app.db.database import get_engine, get_session_local
from radius_app.db.models import RadiusUserCertificate

logger = logging.getLogger(__name__)


class CertificateSyncService:
    """Synchronize user certificates from portal to FreeRADIUS.
    
    This service watches the portal database for new/updated/revoked certificates
    and automatically syncs them to FreeRADIUS, regenerating configuration as needed.
    """

    def __init__(
        self,
        poll_interval: int = 30,
        certs_path: Path | None = None
    ):
        """Initialize the certificate sync service.
        
        Args:
            poll_interval: Seconds between sync checks (default 30)
            certs_path: Path to store user certificates (defaults to settings)
        """
        from radius_app.config import get_settings
        self.poll_interval = poll_interval
        if certs_path is None:
            settings = get_settings()
            certs_path = Path(settings.radius_config_path) / "certs" / "users"
        self.certs_path = certs_path
        self.running = False
        self._last_sync: datetime | None = None
        
        # Ensure certs directory exists
        self.certs_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Certificate sync service initialized (interval: {poll_interval}s)")

    async def start(self):
        """Start the certificate sync service."""
        logger.info("Starting certificate sync service...")
        self.running = True
        
        # Run initial sync
        await self.sync_certificates()
        
        # Start background loop
        asyncio.create_task(self._sync_loop())

    async def stop(self):
        """Stop the certificate sync service."""
        logger.info("Stopping certificate sync service...")
        self.running = False

    async def _sync_loop(self):
        """Background loop that periodically syncs certificates."""
        while self.running:
            try:
                await asyncio.sleep(self.poll_interval)
                await self.sync_certificates()
            except asyncio.CancelledError:
                logger.info("Certificate sync loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}", exc_info=True)
                # Continue running despite errors

    async def sync_certificates(self) -> dict:
        """Synchronize certificates from portal database.
        
        Returns:
            Dictionary with sync statistics
        """
        logger.info("Starting certificate synchronization...")
        
        try:
            SessionLocal = get_session_local()
            db = SessionLocal()
            
            # Get portal database connection string
            settings = get_settings()
            portal_db_url = settings.database_url
            
            # Connect to portal database
            portal_engine = create_engine(portal_db_url)
            
            with Session(portal_engine) as portal_db:
                # Query portal for active user certificates
                # Note: We need to import UserCertificate from portal models
                # For now, use raw SQL to avoid circular dependencies
                
                result = portal_db.execute("""
                    SELECT 
                        id as portal_certificate_id,
                        user_id,
                        (SELECT email FROM users WHERE id = user_certificates.user_id) as user_email,
                        subject_common_name,
                        subject_distinguished_name,
                        certificate_fingerprint,
                        serial_number,
                        valid_from,
                        valid_until,
                        status,
                        certificate
                    FROM user_certificates
                    WHERE status IN ('active', 'revoked')
                    ORDER BY user_email
                """)
                
                portal_certs = result.fetchall()
                
                logger.info(f"Found {len(portal_certs)} certificates in portal database")
                
                # Sync each certificate
                added = 0
                updated = 0
                revoked = 0
                
                for portal_cert in portal_certs:
                    try:
                        # Check if certificate exists in RADIUS database
                        radius_cert = db.query(RadiusUserCertificate).filter_by(
                            portal_certificate_id=portal_cert.portal_certificate_id
                        ).first()
                        
                        if radius_cert:
                            # Update existing certificate
                            if radius_cert.status != portal_cert.status:
                                radius_cert.status = portal_cert.status
                                radius_cert.last_updated_at = datetime.now(timezone.utc)
                                
                                if portal_cert.status == "revoked":
                                    revoked += 1
                                    logger.info(
                                        f"Revoked certificate: {portal_cert.user_email} "
                                        f"(serial: {portal_cert.serial_number})"
                                    )
                                else:
                                    updated += 1
                        else:
                            # Add new certificate
                            radius_cert = RadiusUserCertificate(
                                portal_certificate_id=portal_cert.portal_certificate_id,
                                user_email=portal_cert.user_email,
                                subject_common_name=portal_cert.subject_common_name,
                                subject_distinguished_name=portal_cert.subject_distinguished_name,
                                certificate_fingerprint=portal_cert.certificate_fingerprint,
                                serial_number=portal_cert.serial_number,
                                valid_from=portal_cert.valid_from,
                                valid_until=portal_cert.valid_until,
                                status=portal_cert.status,
                                synced_at=datetime.now(timezone.utc)
                            )
                            db.add(radius_cert)
                            added += 1
                            
                            logger.info(
                                f"Added certificate: {portal_cert.user_email} "
                                f"(serial: {portal_cert.serial_number})"
                            )
                            
                            # Write certificate file to disk
                            await self._write_certificate_file(
                                portal_cert.user_email,
                                portal_cert.certificate
                            )
                    
                    except Exception as e:
                        logger.error(
                            f"Failed to sync certificate {portal_cert.portal_certificate_id}: {e}"
                        )
                        continue
                
                # Commit all changes
                db.commit()
                
                # Regenerate FreeRADIUS configuration
                if added > 0 or updated > 0 or revoked > 0:
                    logger.info("Regenerating FreeRADIUS configuration...")
                    await self._regenerate_config(db)
                
                self._last_sync = datetime.now(timezone.utc)
                
                stats = {
                    "success": True,
                    "certificates_added": added,
                    "certificates_updated": updated,
                    "certificates_revoked": revoked,
                    "total_synced": len(portal_certs),
                    "last_sync": self._last_sync.isoformat()
                }
                
                logger.info(
                    f"✅ Certificate sync complete: "
                    f"+{added} ~{updated} -{revoked} (total: {len(portal_certs)})"
                )
                
                return stats
                
        except Exception as e:
            logger.error(f"Certificate sync failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "last_sync": self._last_sync.isoformat() if self._last_sync else None
            }
        finally:
            db.close()

    async def _write_certificate_file(self, user_email: str, certificate_pem: str):
        """Write certificate to disk for FreeRADIUS.
        
        Args:
            user_email: User's email address
            certificate_pem: Certificate in PEM format
        """
        try:
            # Sanitize filename
            safe_filename = user_email.replace("@", "_at_").replace(".", "_")
            cert_file = self.certs_path / f"{safe_filename}.pem"
            
            # Write certificate
            cert_file.write_text(certificate_pem)
            
            logger.debug(f"Wrote certificate file: {cert_file}")
            
        except Exception as e:
            logger.error(f"Failed to write certificate file: {e}")

    async def _regenerate_config(self, db: Session):
        """Regenerate FreeRADIUS configuration files.
        
        Args:
            db: Database session
        """
        try:
            # Generate EAP configuration
            config_gen = EapConfigGenerator()
            
            # Regenerate users file with certificate users
            users_config = config_gen.generate_users_file(db)
            from radius_app.config import get_settings
            settings = get_settings()
            users_file = Path(settings.radius_config_path) / "users"
            users_file.write_text(users_config)
            
            logger.info("✅ Regenerated FreeRADIUS users file")
            
            # Signal FreeRADIUS to reload configuration
            await self._reload_freeradius()
            
        except Exception as e:
            logger.error(f"Failed to regenerate config: {e}", exc_info=True)

    async def _reload_freeradius(self):
        """Signal FreeRADIUS to reload configuration.
        
        Sends HUP signal to FreeRADIUS daemon to reload without dropping connections.
        """
        try:
            import subprocess
            
            # Try to reload via systemd first
            result = subprocess.run(
                ["systemctl", "reload", "freeradius"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("✅ FreeRADIUS reloaded via systemctl")
                return
            
            # Fall back to direct signal
            result = subprocess.run(
                ["killall", "-HUP", "radiusd"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("✅ FreeRADIUS reloaded via HUP signal")
            else:
                logger.warning(f"Failed to reload FreeRADIUS: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("FreeRADIUS reload timeout")
        except Exception as e:
            logger.error(f"Failed to reload FreeRADIUS: {e}")

    async def get_sync_status(self) -> dict:
        """Get current synchronization status.
        
        Returns:
            Dictionary with sync status information
        """
        SessionLocal = get_session_local()
        db = SessionLocal()
        
        try:
            # Count certificates by status
            from sqlalchemy import func
            
            stats = db.query(
                RadiusUserCertificate.status,
                func.count(RadiusUserCertificate.id)
            ).group_by(RadiusUserCertificate.status).all()
            
            status_counts = {status: count for status, count in stats}
            
            return {
                "running": self.running,
                "last_sync": self._last_sync.isoformat() if self._last_sync else None,
                "poll_interval": self.poll_interval,
                "certificates": {
                    "active": status_counts.get("active", 0),
                    "revoked": status_counts.get("revoked", 0),
                    "expired": status_counts.get("expired", 0),
                    "total": sum(status_counts.values())
                }
            }
            
        finally:
            db.close()

    async def force_sync(self) -> dict:
        """Force an immediate certificate synchronization.
        
        Returns:
            Sync statistics
        """
        logger.info("Manual certificate sync requested")
        return await self.sync_certificates()


# Lazy-initialized global instance to avoid directory creation at import time
_cert_sync_service: CertificateSyncService | None = None


def get_cert_sync_service() -> CertificateSyncService:
    """Get or create the certificate sync service singleton.
    
    Uses lazy initialization to avoid creating directories at import time,
    which is important for testing environments.
    """
    global _cert_sync_service
    if _cert_sync_service is None:
        _cert_sync_service = CertificateSyncService()
    return _cert_sync_service


# Backward compatibility - lazy property
class _CertSyncServiceProxy:
    """Proxy class to provide lazy initialization for backward compatibility."""
    
    def __getattr__(self, name):
        return getattr(get_cert_sync_service(), name)


cert_sync_service = _CertSyncServiceProxy()
