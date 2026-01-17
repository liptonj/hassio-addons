"""Admin endpoints for email/SMTP configuration."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.api.deps import require_admin
from app.core.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter()


class SendTestEmailRequest(BaseModel):
    """Request to send a test email."""

    recipient: EmailStr


class SendTestEmailResponse(BaseModel):
    """Response after sending test email."""

    success: bool
    message: str


@router.post("/admin/email/test", response_model=SendTestEmailResponse)
async def send_test_email(
    data: SendTestEmailRequest,
    admin_user: dict = Depends(require_admin),
) -> SendTestEmailResponse:
    """Send a test email to verify SMTP configuration.

    Args:
        data: Test email request with recipient
        admin_user: Current admin user

    Returns:
        Success response

    Raises:
        HTTPException: If email sending fails
    """
    logger.info(f"Test email requested by {admin_user.get('sub')} to {data.recipient}")

    try:
        success = await email_service.send_test_email(data.recipient)

        if success:
            return SendTestEmailResponse(
                success=True,
                message=f"Test email sent successfully to {data.recipient}"
            )
        else:
            return SendTestEmailResponse(
                success=False,
                message="Failed to send test email. Check SMTP configuration and logs."
            )

    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}"
        ) from e
