"""Appointments service — handles booking with rules-based concurrency control."""

import datetime
from fastapi import HTTPException, status
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.doctor_schedule import DoctorSchedule
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.appointment import CreateAppointmentRequest, AppointmentResponse, ComputedSlotResponse, AppointmentUpdate
from app.services.notifications_service import NotificationsService
from app.services.email_service import EmailService
from app.config import settings


class AppointmentsService:
    """Encapsulates appointments business logic using Rules-Based Availability."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifications_service = NotificationsService(db)

    async def get_available_slots(self, doctor_id: int, start_date: datetime.date, end_date: datetime.date) -> list[ComputedSlotResponse]:
        """Calculate available slots on the fly based on rules and existing appointments."""
        # Get doctor and their schedules
        doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.schedules)))
        doctor = doctor_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor not found")
        
        # Build schedule dict by day_of_week
        schedules = {s.day_of_week: s for s in doctor.schedules}

        # Get existing appointments in range
        appointments_query = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date >= start_date,
            Appointment.appointment_date <= end_date,
            Appointment.status == "scheduled"
        )
        appointments_res = await self.db.execute(appointments_query)
        existing_appointments = appointments_res.scalars().all()
        
        # Organize existing appointments by date
        booked_times_by_date = {}
        for appt in existing_appointments:
            if appt.appointment_date not in booked_times_by_date:
                booked_times_by_date[appt.appointment_date] = []
            booked_times_by_date[appt.appointment_date].append((appt.start_time, appt.end_time))

        available_slots = []
        
        # Iterate over dates
        current_date = start_date
        duration_delta = datetime.timedelta(minutes=doctor.slot_duration_minutes)

        while current_date <= end_date:
            day_of_week = current_date.weekday()
            schedule = schedules.get(day_of_week)
            
            if schedule:
                # Generate slots based on schedule and slot_duration_minutes
                current_dt = datetime.datetime.combine(current_date, schedule.start_time)
                end_dt = datetime.datetime.combine(current_date, schedule.end_time)
                
                booked_ranges = booked_times_by_date.get(current_date, [])
                
                while current_dt + duration_delta <= end_dt:
                    slot_start = current_dt.time()
                    slot_end = (current_dt + duration_delta).time()
                    
                    # Check for overlap with booked times
                    overlap = False
                    for b_start, b_end in booked_ranges:
                        if slot_start < b_end and slot_end > b_start:
                            overlap = True
                            break
                    
                    if not overlap:
                        available_slots.append(ComputedSlotResponse(
                            doctor_id=doctor_id,
                            slot_date=current_date,
                            start_time=slot_start,
                            end_time=slot_end
                        ))
                        
                    current_dt += duration_delta
                    
            current_date += datetime.timedelta(days=1)
            
        return available_slots

    async def create_appointment(self, data: CreateAppointmentRequest, current_user_id: int, current_user_role: str) -> AppointmentResponse:
        """Creates an appointment with overlap validation."""
        patient_id = data.patient_id
        if current_user_role == "patient":
            result = await self.db.execute(select(Patient.id).where(Patient.user_id == current_user_id))
            patient_id = result.scalar_one_or_none()
            if not patient_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No patient profile found")
        elif current_user_role == "doctor" and not patient_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id is required")
        
        # Validate doctor exists
        doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == data.doctor_id))
        doctor = doctor_res.scalar_one_or_none()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        # Pessimistic locking on doctor to serialize bookings
        await self.db.execute(select(Doctor.id).where(Doctor.id == data.doctor_id).with_for_update())

        # Check overlap
        overlap_query = select(Appointment).where(
            Appointment.doctor_id == data.doctor_id,
            Appointment.appointment_date == data.appointment_date,
            Appointment.status == "scheduled",
            Appointment.start_time < data.end_time,
            Appointment.end_time > data.start_time
        )
        overlap_res = await self.db.execute(overlap_query)
        if overlap_res.first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "SLOT_UNAVAILABLE", "message": "Este horario ya no está disponible"}
            )
            
        # Create appointment
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=data.doctor_id,
            appointment_date=data.appointment_date,
            start_time=data.start_time,
            end_time=data.end_time,
            status="scheduled",
            created_by=current_user_role,
            reason=data.reason
        )
        self.db.add(appointment)
        await self.db.flush()

        # Notifications
        if current_user_role == "patient":
            await self.notifications_service.create_notification(
                user_id=doctor.user_id,
                type="appointment_created",
                message=f"Nueva cita programada para el {data.appointment_date} a las {data.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )
        else:
            patient_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
            patient = patient_res.scalar_one()
            await self.notifications_service.create_notification(
                user_id=patient.user_id,
                type="appointment_created",
                message=f"Se ha programado una cita para usted el {data.appointment_date} a las {data.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )

        # Emails
        import asyncio
        patient_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient_record = patient_res.scalar_one()
        
        asyncio.create_task(
            EmailService.send_email(
                to_email=patient_record.email,
                subject="Cita Programada - MediApp",
                template_name="appointment_scheduled.html",
                context={
                    "patient_name": patient_record.full_name,
                    "doctor_name": doctor.full_name,
                    "date": str(data.appointment_date),
                    "time": str(data.start_time),
                    "reason": data.reason
                }
            )
        )

        return AppointmentResponse.model_validate(appointment)

    async def get_appointments(self, user_id: int, user_role: str) -> list[AppointmentResponse]:
        """Get appointments for the current user."""
        query = select(Appointment)
        
        if user_role == "patient":
            res = await self.db.execute(select(Patient.id).where(Patient.user_id == user_id))
            patient_id = res.scalar_one()
            query = query.where(Appointment.patient_id == patient_id)
        elif user_role == "doctor":
            res = await self.db.execute(select(Doctor.id).where(Doctor.user_id == user_id))
            doctor_id = res.scalar_one()
            query = query.where(Appointment.doctor_id == doctor_id)
            
        query = query.order_by(Appointment.created_at.desc())
        result = await self.db.execute(query)
        appointments = result.scalars().all()
        return [AppointmentResponse.model_validate(a) for a in appointments]

    async def cancel_appointment(self, appointment_id: int, user_id: int, user_role: str) -> AppointmentResponse:
        """Cancel an appointment."""
        query = select(Appointment).where(Appointment.id == appointment_id).with_for_update()
        result = await self.db.execute(query)
        appointment = result.scalar_one_or_none()

        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")

        if appointment.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cita ya está cancelada")

        if user_role == "patient":
            res = await self.db.execute(select(Patient.id).where(Patient.user_id == user_id))
            patient_id = res.scalar_one()
            if appointment.patient_id != patient_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos")
        elif user_role == "doctor":
            res = await self.db.execute(select(Doctor.id).where(Doctor.user_id == user_id))
            doctor_id = res.scalar_one()
            if appointment.doctor_id != doctor_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permisos")

        appointment.status = "cancelled"
        await self.db.flush()

        doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == appointment.doctor_id))
        doctor = doctor_res.scalar_one()
        patient_res = await self.db.execute(select(Patient).where(Patient.id == appointment.patient_id))
        patient = patient_res.scalar_one()

        if user_role == "patient":
            await self.notifications_service.create_notification(
                user_id=doctor.user_id,
                type="appointment_cancelled",
                message=f"El paciente ha cancelado la cita del {appointment.appointment_date} a las {appointment.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )
        elif user_role == "doctor":
            await self.notifications_service.create_notification(
                user_id=patient.user_id,
                type="appointment_cancelled",
                message=f"El médico ha cancelado su cita del {appointment.appointment_date} a las {appointment.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )

        import asyncio
        asyncio.create_task(
            EmailService.send_email(
                to_email=patient.email,
                subject="Cita Cancelada - MediApp",
                template_name="appointment_cancelled.html",
                context={
                    "recipient_name": patient.full_name,
                    "patient_name": patient.full_name,
                    "doctor_name": doctor.full_name,
                    "date": str(appointment.appointment_date),
                    "time": str(appointment.start_time),
                    "cancelled_by_role": "Paciente" if user_role == "patient" else "Médico",
                    "frontend_url": settings.frontend_url,
                    "is_patient": True
                }
            )
        )

        return AppointmentResponse.model_validate(appointment)
