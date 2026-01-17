"""Email service for sending notifications."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP."""

    def __init__(self):
        """Initialize email service."""
        self.settings = get_settings()

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> bool:
        """Send an email via SMTP.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            body_text: Plain text email body
            body_html: Optional HTML email body

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.settings.smtp_enabled:
            logger.warning("SMTP is disabled, email not sent")
            return False

        if not self.settings.smtp_host:
            logger.error("SMTP host not configured")
            return False

        # Convert single recipient to list
        recipients = [to] if isinstance(to, str) else to

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            msg["To"] = ", ".join(recipients)

            # Attach plain text and HTML parts
            msg.attach(MIMEText(body_text, "plain"))
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            # Connect to SMTP server
            if self.settings.smtp_use_ssl:
                # SSL connection (port 465)
                server = smtplib.SMTP_SSL(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout,
                )
            else:
                # Plain or TLS connection (port 587 or 25)
                server = smtplib.SMTP(
                    self.settings.smtp_host,
                    self.settings.smtp_port,
                    timeout=self.settings.smtp_timeout,
                )

                if self.settings.smtp_use_tls:
                    server.starttls()

            # Authenticate if credentials provided
            if self.settings.smtp_username and self.settings.smtp_password:
                server.login(self.settings.smtp_username, self.settings.smtp_password)

            # Send email
            server.sendmail(
                self.settings.smtp_from_email,
                recipients,
                msg.as_string(),
            )
            server.quit()

            logger.info(f"Email sent successfully to {recipients}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False

    async def send_ipsk_expiration_warning(
        self,
        user_email: str,
        user_name: str,
        days_remaining: int,
        expiration_date: str,
    ) -> bool:
        """Send iPSK expiration warning email.

        Args:
            user_email: User's email address
            user_name: User's name
            days_remaining: Days until expiration
            expiration_date: Formatted expiration date

        Returns:
            True if email sent successfully
        """
        subject = f"⚠️ WiFi Access Expiring in {days_remaining} Days"

        body_text = f"""
Hello {user_name},

Your WiFi access is set to expire soon.

Days Remaining: {days_remaining}
Expiration Date: {expiration_date}

Please contact your administrator to renew your access before it expires.

Thank you,
{self.settings.property_name} IT Team
"""

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px; }}
        .alert-box {{ background: #fff3cd; border-left: 4px solid #ff9800; padding: 15px; margin: 20px 0; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .info-table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        .info-table td:first-child {{ font-weight: bold; width: 40%; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ WiFi Access Expiring Soon</h1>
        </div>
        <div class="content">
            <p>Hello {user_name},</p>
            <div class="alert-box">
                <strong>Your WiFi access is set to expire soon.</strong>
            </div>
            <table class="info-table">
                <tr>
                    <td>Days Remaining:</td>
                    <td><strong>{days_remaining} days</strong></td>
                </tr>
                <tr>
                    <td>Expiration Date:</td>
                    <td><strong>{expiration_date}</strong></td>
                </tr>
            </table>
            <p>Please contact your administrator to renew your access before it expires.</p>
            <div class="footer">
                <p>Thank you,<br>{self.settings.property_name} IT Team</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(user_email, subject, body_text, body_html)

    async def send_test_email(self, recipient: str) -> bool:
        """Send a test email to verify SMTP configuration.

        Args:
            recipient: Email address to send test email to

        Returns:
            True if email sent successfully
        """
        subject = "✅ SMTP Configuration Test - WiFi Portal"

        body_text = f"""
This is a test email from {self.settings.property_name} WiFi Portal.

If you're seeing this message, your SMTP configuration is working correctly!

SMTP Configuration:
- Host: {self.settings.smtp_host}
- Port: {self.settings.smtp_port}
- TLS: {'Enabled' if self.settings.smtp_use_tls else 'Disabled'}
- SSL: {'Enabled' if self.settings.smtp_use_ssl else 'Disabled'}

You can now use email notifications for:
- iPSK expiration warnings
- Admin notifications
- User welcome emails

---
{self.settings.property_name} WiFi Portal
"""

        body_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 30px; border: 1px solid #ddd; border-radius: 0 0 8px 8px; }}
        .success-box {{ background: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; }}
        .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; background: white; }}
        .info-table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        .info-table td:first-child {{ font-weight: bold; width: 40%; background: #f5f5f5; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>✅ SMTP Configuration Test</h1>
        </div>
        <div class="content">
            <div class="success-box">
                <strong>Success!</strong> If you're seeing this message, your SMTP configuration is working correctly!
            </div>
            <p>This is a test email from <strong>{self.settings.property_name}</strong> WiFi Portal.</p>
            <table class="info-table">
                <tr>
                    <td>SMTP Host:</td>
                    <td>{self.settings.smtp_host}</td>
                </tr>
                <tr>
                    <td>SMTP Port:</td>
                    <td>{self.settings.smtp_port}</td>
                </tr>
                <tr>
                    <td>TLS:</td>
                    <td>{'Enabled' if self.settings.smtp_use_tls else 'Disabled'}</td>
                </tr>
                <tr>
                    <td>SSL:</td>
                    <td>{'Enabled' if self.settings.smtp_use_ssl else 'Disabled'}</td>
                </tr>
            </table>
            <p>You can now use email notifications for:</p>
            <ul>
                <li>iPSK expiration warnings</li>
                <li>Admin notifications</li>
                <li>User welcome emails</li>
            </ul>
            <div class="footer">
                <p>{self.settings.property_name} WiFi Portal</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

        return await self.send_email(recipient, subject, body_text, body_html)


# Global instance
email_service = EmailService()
