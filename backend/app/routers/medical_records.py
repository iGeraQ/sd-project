"""Medical Records router."""

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user, only_doctor, TokenData, any_authenticated
from app.models.doctor import Doctor
from app.schemas.medical_record import CreateMedicalRecordRequest, MedicalRecordEntry, PatientHistoryResponse
from app.schemas.common import SuccessResponse
from app.services.medical_records_service import MedicalRecordsService

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])


@router.post("", response_model=SuccessResponse[MedicalRecordEntry], status_code=201)
async def create_medical_record(
    body: CreateMedicalRecordRequest,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Create a medical record (doctor only). Data will be encrypted using AES-256-GCM."""
    service = MedicalRecordsService(db)
    
    # Get doctor ID
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == user.sub))
    doctor_id = res.scalar_one()

    record = await service.create_record(doctor_id, body)
    await db.commit()
    return SuccessResponse(data=record, message="Historial clínico guardado exitosamente")


@router.get("/patient/{patient_id}", response_model=SuccessResponse[PatientHistoryResponse])
async def get_patient_history(
    patient_id: uuid.UUID,
    user: TokenData = Depends(any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Get complete decrypted history for a patient. Doctors see all, patients only theirs."""
    service = MedicalRecordsService(db)
    history = await service.get_patient_history(patient_id, current_user_id=user.sub, current_user_role=user.role)
    return SuccessResponse(data=history)
