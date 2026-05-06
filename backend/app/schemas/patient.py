"""Patient schemas — CRUD operations."""

import uuid
from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from datetime import datetime


class PatientResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    address: str | None
    email: str
    phone: str | None
    age: int | None
    gender: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    address: str | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    age: int | None = Field(default=None, gt=0, lt=150)
    gender: Literal["male", "female", "other"] | None = None
