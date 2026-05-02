"""Notifications router."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user, TokenData
from app.schemas.notification import NotificationResponse
from app.schemas.common import SuccessResponse
from app.services.notifications_service import NotificationsService


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=SuccessResponse[list[NotificationResponse]])
async def list_notifications(
    unread_only: bool = Query(False),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user."""
    service = NotificationsService(db)
    notifications = await service.get_user_notifications(user.sub, unread_only)
    return SuccessResponse(data=notifications)


@router.patch("/{notification_id}/read", response_model=SuccessResponse[NotificationResponse])
async def mark_notification_read(
    notification_id: int,
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a specific notification as read."""
    service = NotificationsService(db)
    notification = await service.mark_as_read(notification_id, user.sub)
    await db.commit()
    return SuccessResponse(data=notification)
