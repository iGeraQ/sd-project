"""Reports router."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.dependencies import get_db, only_doctor, TokenData
from app.schemas.report import CalendarReportResponse, HistoryReportResponse
from app.schemas.patient import PatientResponse
from app.schemas.common import SuccessResponse
from app.services.reports_service import ReportsService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/calendar", response_model=SuccessResponse[CalendarReportResponse])
async def get_calendar_report(
    year: int = Query(default_factory=lambda: datetime.date.today().year),
    month: int = Query(default_factory=lambda: datetime.date.today().month, ge=1, le=12),
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get a calendar view of appointments for a specific month (doctor only)."""
    service = ReportsService(db)
    report = await service.get_calendar_report(user.sub, year, month)
    return SuccessResponse(data=report)


@router.get("/patients", response_model=SuccessResponse[list[PatientResponse]])
async def get_patients_report(
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get all patients assigned to a doctor (doctor only)."""
    service = ReportsService(db)
    # We need to resolve the doctor_id from the user.sub
    from app.models.doctor import Doctor
    from sqlalchemy import select
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == user.sub))
    doctor_id = res.scalar_one()
    
    patients = await service.get_patients_report(doctor_id)
    return SuccessResponse(data=patients)


@router.get("/history/{patient_id}", response_model=SuccessResponse[HistoryReportResponse])
async def get_history_report(
    patient_id: int,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get full medical history for a patient (doctor only)."""
    service = ReportsService(db)
    # Resolve the doctor_id from the user.sub
    from app.models.doctor import Doctor
    from sqlalchemy import select
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == user.sub))
    doctor_id = res.scalar_one()
    
    report = await service.get_history_report(doctor_id, patient_id)
    return SuccessResponse(data=report)
