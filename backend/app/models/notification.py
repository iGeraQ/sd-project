"""Notification model — user notifications for appointment events."""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import func

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    reference: Mapped[dict | None] = mapped_column(JSONB)  # {"type": "appointment", "id": 123}
    created_at: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notifications")
