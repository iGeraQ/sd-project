"""Report schemas."""

import datetime
from pydantic import BaseModel

from app.schemas.patient import PatientResponse
from app.schemas.medical_record import PatientHeader, MedicalRecordEntry


class CalendarDay(BaseModel):
    date: datetime.date
    appointments: list[dict]


class CalendarReportResponse(BaseModel):
    month: str
    days: list[CalendarDay]


class HistoryReportResponse(BaseModel):
    header: PatientHeader
    records: list[MedicalRecordEntry]
