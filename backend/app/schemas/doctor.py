"""Doctor schemas."""

import datetime
from pydantic import BaseModel, Field


class DoctorProfileUpdate(BaseModel):
    full_name: str | None = None
    specialty: str | None = None
    license_number: str | None = None
    slot_duration_minutes: int | None = Field(None, ge=5, le=480, description="Duration of each appointment in minutes")


class DoctorScheduleItem(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: datetime.time
    end_time: datetime.time


class DoctorScheduleUpdateRequest(BaseModel):
    schedules: list[DoctorScheduleItem]


class DoctorProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    specialty: str | None
    license_number: str | None
    slot_duration_minutes: int

    model_config = {"from_attributes": True}
