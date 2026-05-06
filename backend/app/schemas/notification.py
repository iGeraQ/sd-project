"""Notification schemas."""

import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    message: str
    is_read: bool
    reference: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
