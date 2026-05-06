"""Notifications service — manage user notifications."""

import uuid
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.notification import Notification
from app.schemas.notification import NotificationResponse


class NotificationsService:
    """Encapsulates notification business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_notifications(self, user_id: uuid.UUID, unread_only: bool = False) -> list[NotificationResponse]:
        """Get notifications for a user."""
        query = select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc())
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        return [NotificationResponse.model_validate(n) for n in notifications]

    async def create_notification(self, user_id: uuid.UUID, type: str, message: str, reference: dict | None = None) -> Notification:
        """Create a new notification."""
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            reference=reference,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def mark_as_read(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> NotificationResponse:
        """Mark a notification as read."""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
        )
        notification = result.scalar_one_or_none()
        if not notification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada")
        
        notification.is_read = True
        await self.db.flush()
        return NotificationResponse.model_validate(notification)
