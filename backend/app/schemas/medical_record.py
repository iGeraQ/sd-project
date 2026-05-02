"""Medical record schemas — encrypted clinical history."""

from datetime import datetime
from pydantic import BaseModel, Field


class VitalSigns(BaseModel):
    body_temperature: float = Field(ge=30.0, le=45.0)
    weight_kg: float = Field(gt=0)
    height_cm: float = Field(gt=0)
    blood_pressure: str  # e.g. "120/80"


class CreateMedicalRecordRequest(BaseModel):
    appointment_id: int
    vital_signs: VitalSigns
    diagnosis: str
    lab_results: str | None = None
    prescriptions: str | None = None
    notes: str | None = None


class MedicalRecordEntry(BaseModel):
    id: int
    appointment_id: int
    date: datetime
    doctor_name: str
    vital_signs: VitalSigns
    diagnosis: str
    lab_results: str | None
    prescriptions: str | None
    notes: str | None


class PatientHeader(BaseModel):
    id: int
    full_name: str
    age: int | None
    gender: str | None
    email: str
    phone: str | None
    address: str | None


class PatientHistoryResponse(BaseModel):
    patient: PatientHeader
    records: list[MedicalRecordEntry]
