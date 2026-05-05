"""Appointment and slot schemas."""

import datetime
from pydantic import BaseModel, Field
from typing import Literal


class ComputedSlotResponse(BaseModel):
    doctor_id: int
    slot_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time


class DoctorScheduleResponse(BaseModel):
    id: int
    day_of_week: int
    start_time: datetime.time
    end_time: datetime.time

    model_config = {"from_attributes": True}


class CreateAppointmentRequest(BaseModel):
    doctor_id: int
    appointment_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    reason: str | None = None
    patient_id: int | None = None  # Only used when doctor creates for a patient


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    status: str
    created_by: str
    reason: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AppointmentUpdate(BaseModel):
    reason: str | None = None
    status: Literal["scheduled", "completed", "cancelled"] | None = None
