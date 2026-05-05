"""Doctors router — endpoints for managing doctor profiles and schedules."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, TokenData, only_doctor
from app.schemas.doctor import DoctorProfileUpdate, DoctorScheduleUpdateRequest, DoctorProfileResponse
from app.schemas.appointment import DoctorScheduleResponse
from app.schemas.common import SuccessResponse
from app.services.doctors_service import DoctorsService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("/me", response_model=SuccessResponse[DoctorProfileResponse])
async def get_my_profile(
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get the current doctor's profile."""
    service = DoctorsService(db)
    profile = await service.get_my_profile(user.sub)
    return SuccessResponse(data=profile)


@router.put("/me", response_model=SuccessResponse[DoctorProfileResponse])
async def update_my_profile(
    body: DoctorProfileUpdate,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Update the current doctor's profile."""
    service = DoctorsService(db)
    profile = await service.update_my_profile(user.sub, body)
    await db.commit()
    return SuccessResponse(data=profile, message="Perfil actualizado con éxito")


@router.get("/me/schedules", response_model=SuccessResponse[list[DoctorScheduleResponse]])
async def get_my_schedules(
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Get the current doctor's weekly schedule."""
    service = DoctorsService(db)
    schedules = await service.get_my_schedules(user.sub)
    return SuccessResponse(data=schedules)


@router.put("/me/schedules", response_model=SuccessResponse[list[DoctorScheduleResponse]])
async def set_my_schedules(
    body: DoctorScheduleUpdateRequest,
    user: TokenData = Depends(only_doctor),
    db: AsyncSession = Depends(get_db),
):
    """Set the current doctor's weekly schedule (overwrites existing)."""
    service = DoctorsService(db)
    schedules = await service.set_my_schedules(user.sub, body)
    await db.commit()
    return SuccessResponse(data=schedules, message="Horario actualizado con éxito")
