"""Certificate renewal monitoring background service.

This service automatically renews user certificates that are expiring soon,
sends expiration notifications, and handles certificate lifecycle management.
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from app.config import get_settings
from app.core.certificate_manager import CertificateManager, CertificateManagerError
from app.db.database import get_session_local
from app.db.models import UserCertificate, User

logger = logging.getLogger(__name__)


class CertificateRenewalMonitor:
    """Background service to monitor and renew expiring certificates."""

    def __init__(self):
        """Initialize the renewal monitor."""
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """Start the monitoring service."""
        settings = get_settings()

        if not settings.cert_auto_renewal_enabled:
            logger.info("Certificate auto-renewal monitoring is disabled")
            return

        # Check every hour (configurable in future)
        interval_hours = 1
        logger.info(f"Starting certificate renewal monitor (interval: {interval_hours}h)")

        # Schedule the check job
        self.scheduler.add_job(
            self.check_expiring_certificates,
            "interval",
            hours=interval_hours,
            id="cert_renewal_check"
        )

        self.scheduler.start()

        # Run immediately on startup
        await self.check_expiring_certificates()

    async def stop(self):
        """Stop the monitoring service."""
        logger.info("Stopping certificate renewal monitor...")
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("Certificate renewal monitor stopped")

    async def check_expiring_certificates(self):
        """Check for expiring certificates and handle them.
        
        This method:
        1. Finds certificates expiring within threshold
        2. Automatically renews if auto_renew is enabled
        3. Sends warning notifications for soon-to-expire certificates
        4. Marks expired certificates as expired
        """
        logger.info("Running certificate expiration check...")
        settings = get_settings()
        SessionLocal = get_session_local()

        with SessionLocal() as db:
            # Get renewal threshold from settings
            renewal_threshold_days = int(settings.cert_renewal_threshold_days or 30)
            threshold_date = datetime.now(timezone.utc) + timedelta(days=renewal_threshold_days)
            now = datetime.now(timezone.utc)

            # Find certificates expiring within threshold
            expiring_certs = (
                db.query(UserCertificate)
                .filter(
                    UserCertificate.status == "active",
                    UserCertificate.valid_until <= threshold_date,
                    UserCertificate.valid_until > now,
                    UserCertificate.auto_renew == True
                )
                .all()
            )

            logger.info(f"Found {len(expiring_certs)} certificates to renew")

            # Process each expiring certificate
            renewal_count = 0
            for cert in expiring_certs:
                try:
                    await self.renew_certificate_auto(db, cert)
                    renewal_count += 1
                except Exception as e:
                    logger.error(f"Failed to renew certificate {cert.id}: {e}")

            logger.info(f"✅ Renewed {renewal_count} certificates")

            # Find expired certificates that need status update
            expired_certs = (
                db.query(UserCertificate)
                .filter(
                    UserCertificate.status == "active",
                    UserCertificate.valid_until <= now
                )
                .all()
            )

            logger.info(f"Found {len(expired_certs)} expired certificates")

            # Mark as expired
            for cert in expired_certs:
                try:
                    cert.status = "expired"
                    logger.info(f"Marked certificate {cert.id} as expired (serial: {cert.serial_number})")
                except Exception as e:
                    logger.error(f"Failed to mark certificate {cert.id} as expired: {e}")

            if expired_certs:
                db.commit()

            # Send warning notifications for certificates expiring soon (without auto-renewal)
            await self.send_expiration_warnings(db, settings)

            db.commit()

    async def renew_certificate_auto(self, db, cert: UserCertificate):
        """Automatically renew a certificate.
        
        Args:
            db: Database session
            cert: UserCertificate to renew
        """
        logger.info(f"Auto-renewing certificate {cert.id} for user {cert.user_id}")

        try:
            # Initialize certificate manager
            cert_manager = CertificateManager(db)

            # Renew certificate
            new_cert = cert_manager.renew_certificate(
                certificate_id=cert.id,
                validity_days=None  # Use CA default
            )

            logger.info(
                f"✅ Certificate auto-renewed: "
                f"Old ID: {cert.id} (expires {cert.valid_until.date()}), "
                f"New ID: {new_cert.id} (expires {new_cert.valid_until.date()})"
            )

            # TODO: Send notification email to user about renewal
            # await self.send_renewal_notification(cert, new_cert)

        except CertificateManagerError as e:
            logger.error(f"Failed to auto-renew certificate {cert.id}: {e}")
            raise

    async def send_expiration_warnings(self, db, settings):
        """Send warning notifications for certificates expiring soon.
        
        Args:
            db: Database session
            settings: Application settings
        """
        # Parse warning thresholds (e.g., "30,14,7" days)
        try:
            warning_days = [30, 14, 7]  # Default thresholds
            # In future, make this configurable via settings
        except (ValueError, AttributeError):
            warning_days = [30, 14, 7]

        now = datetime.now(timezone.utc)

        for days in warning_days:
            warning_date = now + timedelta(days=days)
            # Find certificates expiring around this date
            certs_near_expiry = (
                db.query(UserCertificate)
                .join(User)
                .filter(
                    UserCertificate.status == "active",
                    UserCertificate.auto_renew == False,  # Only warn for non-auto-renewing
                    UserCertificate.valid_until >= warning_date,
                    UserCertificate.valid_until <= warning_date + timedelta(days=1)
                )
                .all()
            )

            for cert in certs_near_expiry:
                try:
                    await self.send_warning_notification(cert, days)
                except Exception as e:
                    logger.error(f"Failed to send warning for certificate {cert.id}: {e}")

    async def send_warning_notification(self, cert: UserCertificate, days_until_expiry: int):
        """Send expiration warning notification to user.
        
        Args:
            cert: Certificate expiring soon
            days_until_expiry: Number of days until expiration
        """
        logger.info(
            f"⚠️ Certificate {cert.id} expires in {days_until_expiry} days "
            f"(user_id={cert.user_id})"
        )

        # TODO: Implement email/notification system
        # For now, just log the warning
        # In production:
        # - Send email to user.email
        # - Include download link for renewed certificate
        # - Show in user portal dashboard

        # Example:
        # await email_service.send_certificate_expiration_warning(
        #     user=cert.user,
        #     certificate=cert,
        #     days_until_expiry=days_until_expiry
        # )

    async def send_renewal_notification(self, old_cert: UserCertificate, new_cert: UserCertificate):
        """Send notification about automatic certificate renewal.
        
        Args:
            old_cert: Old certificate that was renewed
            new_cert: New certificate that was issued
        """
        logger.info(
            f"📧 Sending renewal notification for user {new_cert.user_id}: "
            f"Old cert {old_cert.id} → New cert {new_cert.id}"
        )

        # TODO: Implement email/notification system
        # For now, just log
        # In production:
        # - Send email to user
        # - Include download link for new certificate
        # - Show banner in user portal
        # - Send push notification if enabled

        # Example:
        # await email_service.send_certificate_renewed_notification(
        #     user=new_cert.user,
        #     old_certificate=old_cert,
        #     new_certificate=new_cert
        # )


# Global instance
cert_renewal_monitor = CertificateRenewalMonitor()
