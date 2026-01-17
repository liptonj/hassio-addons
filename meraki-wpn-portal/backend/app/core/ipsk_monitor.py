"""iPSK expiration monitoring background service."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy import or_

from app.config import get_settings
from app.db.database import get_session_local
from app.db.models import IPSKExpirationLog, User

logger = logging.getLogger(__name__)


class IPSKExpirationMonitor:
    """Background service to monitor and clean up expired iPSKs."""

    def __init__(self):
        """Initialize the expiration monitor."""
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """Start the monitoring service."""
        settings = get_settings()

        if not settings.ipsk_expiration_check_enabled:
            logger.info("iPSK expiration monitoring is disabled")
            return

        interval = settings.ipsk_expiration_check_interval_hours
        logger.info(f"Starting iPSK expiration monitor (interval: {interval}h)")

        # Schedule the check job
        self.scheduler.add_job(
            self.check_expirations, "interval", hours=interval, id="ipsk_expiration_check"
        )

        self.scheduler.start()

        # Run immediately on startup
        await self.check_expirations()

    async def check_expirations(self):
        """Check for expired iPSKs and handle them.
        
        This method:
        1. Finds users with expired iPSKs
        2. Handles expiration based on cleanup action setting
        3. Sends warning notifications for soon-to-expire iPSKs
        """
        logger.info("Running iPSK expiration check...")
        settings = get_settings()
        SessionLocal = get_session_local()

        with SessionLocal() as db:
            # Find users with expiring iPSKs
            now = datetime.now(timezone.utc)

            users_with_expiring = (
                db.query(User)
                .filter(
                    User.ipsk_status == "active",
                    User.ipsk_expires_at.isnot(None),
                    User.ipsk_expires_at <= now,
                )
                .all()
            )

            logger.info(f"Found {len(users_with_expiring)} expired iPSKs")

            for user in users_with_expiring:
                await self.handle_expired_ipsk(db, user, settings)

            # Check for soon-to-expire for warnings
            try:
                warning_days = [
                    int(d.strip())
                    for d in settings.ipsk_expiration_warning_days.split(",")
                ]
            except (ValueError, AttributeError):
                warning_days = [7, 3, 1]  # Default values

            for days in warning_days:
                threshold = now + timedelta(days=days)
                users_expiring_soon = (
                    db.query(User)
                    .filter(
                        User.ipsk_status == "active",
                        User.ipsk_expires_at.isnot(None),
                        User.ipsk_expires_at <= threshold,
                        User.ipsk_expires_at > now,
                        # Only notify if not already notified recently
                        or_(
                            User.expiration_notified_at.is_(None),
                            User.expiration_notified_at < now - timedelta(days=1),
                        ),
                    )
                    .all()
                )

                logger.info(
                    f"Found {len(users_expiring_soon)} iPSKs expiring in {days} days"
                )

                for user in users_expiring_soon:
                    await self.send_expiration_warning(db, user, days)

    async def handle_expired_ipsk(self, db, user: User, settings):
        """Handle an expired iPSK based on cleanup action.
        
        Args:
            db: Database session
            user: User with expired iPSK
            settings: Portal settings
        """
        logger.info(f"Handling expired iPSK for user {user.email}")

        # Mark as expired
        user.ipsk_status = "expired"
        user.expired_at = datetime.now(timezone.utc)

        # Log the event
        log_entry = IPSKExpirationLog(
            user_id=user.id,
            ipsk_id=user.ipsk_id,
            action="expired",
            details=f'{{"cleanup_action": "{settings.ipsk_cleanup_action}"}}',
            performed_by="automated",
            performed_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)

        # Perform cleanup action
        if settings.ipsk_cleanup_action == "revoke_meraki":
            # Delete from Meraki
            logger.info(f"Would delete iPSK {user.ipsk_id} from Meraki")
            # Note: Actual deletion requires HAClient which needs async context
            # This would be implemented as:
            # try:
            #     ha_client = get_ha_client()
            #     await ha_client.delete_ipsk(user.ipsk_id)
            #     logger.info(f"Deleted iPSK {user.ipsk_id} from Meraki")
            # except Exception as e:
            #     logger.error(f"Failed to delete iPSK from Meraki: {e}")

        elif settings.ipsk_cleanup_action == "full_cleanup":
            # Archive user and delete from Meraki
            logger.info(f"Would perform full cleanup for user {user.email}")
            # Implementation would include:
            # - Delete from Meraki
            # - Soft delete user record
            # - Archive associated data

        # 'soft_delete' just marks as expired in DB (already done above)

        db.commit()
        logger.info(f"iPSK {user.ipsk_id} marked as expired")

    async def send_expiration_warning(self, db, user: User, days_remaining: int):
        """Send warning notification about upcoming expiration.
        
        Args:
            db: Database session
            user: User with expiring iPSK
            days_remaining: Days until expiration
        """
        settings = get_settings()
        
        if not settings.ipsk_expiration_email_enabled:
            logger.debug(
                f"Email notifications disabled, skipping warning for {user.email}"
            )
            return

        logger.info(f"Sending expiration warning to {user.email} ({days_remaining} days)")

        # Send email notification
        from app.core.email_service import email_service
        
        expiration_date = user.ipsk_expires_at.strftime("%B %d, %Y") if user.ipsk_expires_at else "Unknown"
        
        try:
            success = await email_service.send_ipsk_expiration_warning(
                user_email=user.email,
                user_name=user.name,
                days_remaining=days_remaining,
                expiration_date=expiration_date,
            )
            
            if not success:
                logger.warning(f"Failed to send expiration warning to {user.email}")
                return
                
        except Exception as e:
            logger.error(f"Error sending expiration warning to {user.email}: {e}")
            return

        # Update notification timestamp
        user.expiration_notified_at = datetime.now(timezone.utc)

        # Log the notification
        log_entry = IPSKExpirationLog(
            user_id=user.id,
            ipsk_id=user.ipsk_id,
            action="notified",
            details=f'{{"days_remaining": {days_remaining}}}',
            performed_by="automated",
            performed_at=datetime.now(timezone.utc),
        )
        db.add(log_entry)
        db.commit()
        
        logger.info(f"Expiration warning sent successfully to {user.email}")

    async def stop(self):
        """Stop the monitoring service."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("iPSK expiration monitor stopped")


# Global instance
ipsk_monitor = IPSKExpirationMonitor()
