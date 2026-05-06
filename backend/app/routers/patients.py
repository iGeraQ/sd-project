"""Patients router — CRUD endpoints for patient management."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user, only_doctor, TokenData
from app.schemas.patient import PatientResponse, PatientUpdate
from app.schemas.common import SuccessResponse
from app.services.patients_service import PatientsService

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=SuccessResponse[list[PatientResponse]])
async def list_patients(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """List all patients (doctor only). Supports pagination and search."""
    service = PatientsService(db)
    patients, pagination = await service.get_all(page, limit, search)
    return SuccessResponse(data=patients, pagination=pagination)


@router.get("/{patient_id}", response_model=SuccessResponse[PatientResponse])
async def get_patient_detail(
    patient_id: uuid.UUID,
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get patient details. Doctors see any; patients only themselves."""
    service = PatientsService(db)

    if user.role == "patient":
        own_id = await service.get_patient_id_for_user(user.sub)
        if own_id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos")

    patient = await service.get_by_id(patient_id)
    return SuccessResponse(data=patient)


@router.put("/{patient_id}", response_model=SuccessResponse[PatientResponse])
async def update_patient_endpoint(
    patient_id: uuid.UUID,
    body: PatientUpdate,
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update patient info. Doctors can update any; patients only themselves."""
    service = PatientsService(db)

    if user.role == "patient":
        own_id = await service.get_patient_id_for_user(user.sub)
        if own_id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos")

    patient = await service.update(patient_id, body)
    await db.commit()
    return SuccessResponse(data=patient, message="Paciente actualizado")


@router.delete("/{patient_id}", response_model=SuccessResponse[None])
async def delete_patient_endpoint(
    patient_id: uuid.UUID,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Delete a patient (doctor only)."""
    service = PatientsService(db)
    await service.delete(patient_id)
    await db.commit()
    return SuccessResponse(data=None, message="Paciente eliminado")
