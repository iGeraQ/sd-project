"""Appointments router — endpoints for booking and managing appointments."""

import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_user, TokenData, any_authenticated
from app.schemas.appointment import CreateAppointmentRequest, AppointmentResponse, SlotResponse
from app.schemas.common import SuccessResponse
from app.services.appointments_service import AppointmentsService


router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/slots", response_model=SuccessResponse[list[SlotResponse]])
async def list_available_slots(
    doctor_id: int = Query(...),
    start_date: datetime.date = Query(...),
    end_date: datetime.date = Query(...),
    user: TokenData = Depends(any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """List available slots for a specific doctor in a date range."""
    service = AppointmentsService(db)
    slots = await service.get_available_slots(doctor_id, start_date, end_date)
    return SuccessResponse(data=slots)


@router.post("", response_model=SuccessResponse[AppointmentResponse], status_code=201)
async def create_appointment(
    body: CreateAppointmentRequest,
    user: TokenData = Depends(any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Book a new appointment with concurrency control."""
    service = AppointmentsService(db)
    appointment = await service.create_appointment(body, current_user_id=user.sub, current_user_role=user.role)
    await db.commit()
    return SuccessResponse(data=appointment, message="Cita programada con éxito")


@router.get("", response_model=SuccessResponse[list[AppointmentResponse]])
async def list_appointments(
    user: TokenData = Depends(any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """List all appointments for the current user (doctor or patient)."""
    service = AppointmentsService(db)
    appointments = await service.get_appointments(user.sub, user.role)
    return SuccessResponse(data=appointments)


@router.delete("/{appointment_id}", response_model=SuccessResponse[AppointmentResponse])
async def cancel_appointment(
    appointment_id: int,
    user: TokenData = Depends(any_authenticated),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an appointment."""
    service = AppointmentsService(db)
    appointment = await service.cancel_appointment(appointment_id, user.sub, user.role)
    await db.commit()
    return SuccessResponse(data=appointment, message="Cita cancelada con éxito")
