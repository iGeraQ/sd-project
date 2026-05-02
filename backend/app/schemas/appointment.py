"""Appointment and slot schemas."""

import datetime
from pydantic import BaseModel, Field
from typing import Literal


class SlotResponse(BaseModel):
    id: int
    doctor_id: int
    slot_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    is_available: bool
    version: int

    model_config = {"from_attributes": True}


class CreateAppointmentRequest(BaseModel):
    slot_id: int
    reason: str | None = None
    slot_version: int  # Required for optimistic concurrency control
    patient_id: int | None = None  # Only used when doctor creates for a patient


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    slot_id: int
    status: str
    created_by: str
    reason: str | None
    created_at: datetime.datetime
    slot: SlotResponse | None = None

    model_config = {"from_attributes": True}


class AppointmentUpdate(BaseModel):
    reason: str | None = None
    status: Literal["scheduled", "completed", "cancelled"] | None = None
