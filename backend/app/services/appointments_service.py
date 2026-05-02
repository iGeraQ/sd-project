"""Appointments service — handles booking with concurrency control."""

from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.available_slot import AvailableSlot
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.user import User
from app.schemas.appointment import CreateAppointmentRequest, AppointmentResponse, SlotResponse, AppointmentUpdate
from app.services.notifications_service import NotificationsService
from app.services.email_service import EmailService
from app.config import settings


class AppointmentsService:
    """Encapsulates appointments business logic, including concurrency management."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifications_service = NotificationsService(db)

    async def get_available_slots(self, doctor_id: int, start_date: datetime.date, end_date: datetime.date) -> list[SlotResponse]:
        """Fetch available slots for a specific doctor within a date range."""
        query = select(AvailableSlot).where(
            AvailableSlot.doctor_id == doctor_id,
            AvailableSlot.slot_date >= start_date,
            AvailableSlot.slot_date <= end_date,
            AvailableSlot.is_available == True
        ).order_by(AvailableSlot.slot_date, AvailableSlot.start_time)
        
        result = await self.db.execute(query)
        slots = result.scalars().all()
        return [SlotResponse.model_validate(slot) for slot in slots]

    async def create_appointment(self, data: CreateAppointmentRequest, current_user_id: int, current_user_role: str) -> AppointmentResponse:
        """
        Creates an appointment using optimistic AND pessimistic locking.
        1. SELECT FOR UPDATE to acquire pessimistic lock on the slot.
        2. Verify version (optimistic lock).
        3. Create appointment and update slot.
        """
        # Resolve patient_id based on who is creating the appointment
        patient_id = data.patient_id
        if current_user_role == "patient":
            result = await self.db.execute(select(Patient.id).where(Patient.user_id == current_user_id))
            patient_id = result.scalar_one_or_none()
            if not patient_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No patient profile found for current user")
        elif current_user_role == "doctor" and not patient_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="patient_id is required when a doctor creates an appointment")
        
        # 1. PESSIMISTIC LOCK: Lock the slot row
        slot_query = select(AvailableSlot).where(AvailableSlot.id == data.slot_id).with_for_update()
        result = await self.db.execute(slot_query)
        slot = result.scalar_one_or_none()

        if not slot:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Horario no encontrado")

        # 2. OPTIMISTIC LOCK: Check version
        if slot.version != data.slot_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "VERSION_MISMATCH", "message": "El horario fue modificado por otro usuario, por favor actualice e intente de nuevo"}
            )
        
        if not slot.is_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "SLOT_UNAVAILABLE", "message": "Este horario ya no está disponible"}
            )

        # 3. Create appointment & update slot
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot.id,
            status="scheduled",
            created_by=current_user_role,
            reason=data.reason
        )
        self.db.add(appointment)
        
        # Update slot
        slot.is_available = False
        slot.version += 1
        
        await self.db.flush()
        
        # Reload with relationships
        res = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.slot))
            .where(Appointment.id == appointment.id)
        )
        appointment_loaded = res.scalar_one()

        # Send notification to doctor if patient created it
        if current_user_role == "patient":
            doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == slot.doctor_id))
            doctor = doctor_res.scalar_one()
            await self.notifications_service.create_notification(
                user_id=doctor.user_id,
                type="appointment_created",
                message=f"Nueva cita programada para el {slot.slot_date} a las {slot.start_time}",
                reference={"type": "appointment", "id": appointment_loaded.id}
            )
        else:
            # Doctor created it for patient
            patient_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
            patient = patient_res.scalar_one()
            await self.notifications_service.create_notification(
                user_id=patient.user_id,
                type="appointment_created",
                message=f"Se ha programado una cita para usted el {slot.slot_date} a las {slot.start_time}",
                reference={"type": "appointment", "id": appointment_loaded.id}
            )

        # Send Emails
        import asyncio
        patient_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient_record = patient_res.scalar_one()
        doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == slot.doctor_id))
        doctor_record = doctor_res.scalar_one()
        
        asyncio.create_task(
            EmailService.send_email(
                to_email=patient_record.email,
                subject="Cita Programada - MediApp",
                template_name="appointment_scheduled.html",
                context={
                    "patient_name": patient_record.full_name,
                    "doctor_name": doctor_record.full_name,
                    "date": str(slot.slot_date),
                    "time": str(slot.start_time),
                    "reason": data.reason
                }
            )
        )

        return AppointmentResponse.model_validate(appointment_loaded)

    async def get_appointments(self, user_id: int, user_role: str) -> list[AppointmentResponse]:
        """Get appointments for the current user (doctor or patient)."""
        query = select(Appointment).options(selectinload(Appointment.slot))
        
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
        """Cancel an appointment and free the slot."""
        # Get appointment with pessimistic locking to safely update the slot
        query = select(Appointment).options(
            selectinload(Appointment.slot)
        ).where(Appointment.id == appointment_id).with_for_update()
        result = await self.db.execute(query)
        appointment = result.scalar_one_or_none()

        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")

        if appointment.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La cita ya está cancelada")

        # RBAC Check
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

        # Update status and free slot
        appointment.status = "cancelled"
        
        # Free up the slot and update version
        slot = appointment.slot
        slot.is_available = True
        slot.version += 1
        
        await self.db.flush()

        # Send notification
        if user_role == "patient":
            doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == appointment.doctor_id))
            doctor = doctor_res.scalar_one()
            await self.notifications_service.create_notification(
                user_id=doctor.user_id,
                type="appointment_cancelled",
                message=f"El paciente ha cancelado la cita del {slot.slot_date} a las {slot.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )
        elif user_role == "doctor":
            patient_res = await self.db.execute(select(Patient).where(Patient.id == appointment.patient_id))
            patient = patient_res.scalar_one()
            await self.notifications_service.create_notification(
                user_id=patient.user_id,
                type="appointment_cancelled",
                message=f"El médico ha cancelado su cita del {slot.slot_date} a las {slot.start_time}",
                reference={"type": "appointment", "id": appointment.id}
            )

        # Send Cancellation Email
        import asyncio
        patient_res = await self.db.execute(select(Patient).where(Patient.id == appointment.patient_id))
        patient_record = patient_res.scalar_one()
        doctor_res = await self.db.execute(select(Doctor).where(Doctor.id == appointment.doctor_id))
        doctor_record = doctor_res.scalar_one()

        asyncio.create_task(
            EmailService.send_email(
                to_email=patient_record.email,
                subject="Cita Cancelada - MediApp",
                template_name="appointment_cancelled.html",
                context={
                    "recipient_name": patient_record.full_name,
                    "patient_name": patient_record.full_name,
                    "doctor_name": doctor_record.full_name,
                    "date": str(slot.slot_date),
                    "time": str(slot.start_time),
                    "cancelled_by_role": "Paciente" if user_role == "patient" else "Médico",
                    "frontend_url": settings.frontend_url,
                    "is_patient": True
                }
            )
        )

        return AppointmentResponse.model_validate(appointment)
