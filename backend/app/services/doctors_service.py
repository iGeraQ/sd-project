"""Doctors service — handles doctor profiles and schedule configuration."""

from fastapi import HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.schemas.doctor import DoctorProfileUpdate, DoctorScheduleUpdateRequest, DoctorProfileResponse
from app.schemas.appointment import DoctorScheduleResponse


class DoctorsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_my_profile(self, user_id: int) -> DoctorProfileResponse:
        """Get the current doctor's profile."""
        query = select(Doctor).where(Doctor.user_id == user_id)
        result = await self.db.execute(query)
        doctor = result.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")
        return DoctorProfileResponse.model_validate(doctor)

    async def update_my_profile(self, user_id: int, data: DoctorProfileUpdate) -> DoctorProfileResponse:
        """Update the doctor's profile, including slot_duration_minutes."""
        query = select(Doctor).where(Doctor.user_id == user_id).with_for_update()
        result = await self.db.execute(query)
        doctor = result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(doctor, key, value)
            
        await self.db.flush()
        return DoctorProfileResponse.model_validate(doctor)

    async def get_my_schedules(self, user_id: int) -> list[DoctorScheduleResponse]:
        """Get the doctor's weekly schedules."""
        query = select(Doctor).where(Doctor.user_id == user_id).options(selectinload(Doctor.schedules))
        result = await self.db.execute(query)
        doctor = result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")

        return [DoctorScheduleResponse.model_validate(s) for s in doctor.schedules]

    async def set_my_schedules(self, user_id: int, data: DoctorScheduleUpdateRequest) -> list[DoctorScheduleResponse]:
        """Overwrite the doctor's weekly schedule."""
        query = select(Doctor).where(Doctor.user_id == user_id)
        result = await self.db.execute(query)
        doctor = result.scalar_one_or_none()
        
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")

        # Delete existing schedules
        await self.db.execute(delete(DoctorSchedule).where(DoctorSchedule.doctor_id == doctor.id))
        
        # Insert new schedules
        new_schedules = []
        for item in data.schedules:
            if item.start_time >= item.end_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_time must be before end_time")
                
            schedule = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=item.day_of_week,
                start_time=item.start_time,
                end_time=item.end_time
            )
            self.db.add(schedule)
            new_schedules.append(schedule)
            
        await self.db.flush()
        
        # Load the inserted schedules with their DB assigned IDs
        return [DoctorScheduleResponse.model_validate(s) for s in new_schedules]
