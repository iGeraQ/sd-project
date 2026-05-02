"""Reports service — analytics and aggregated data."""

import datetime
from collections import defaultdict
from sqlalchemy import select, extract, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.schemas.report import CalendarReportResponse, CalendarDay, HistoryReportResponse
from app.schemas.patient import PatientResponse
from app.schemas.medical_record import PatientHeader, MedicalRecordEntry, VitalSigns
from app.utils.encryption import decrypt_data


class ReportsService:
    """Encapsulates reporting business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_calendar_report(self, doctor_user_id: int, year: int, month: int) -> CalendarReportResponse:
        """Get a monthly calendar view of appointments for a doctor."""
        
        # Resolve doctor ID
        res = await self.db.execute(select(Doctor.id).where(Doctor.user_id == doctor_user_id))
        doctor_id = res.scalar_one_or_none()
        
        if not doctor_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No doctor profile found")

        # Query appointments for the given month
        query = select(Appointment).options(
            selectinload(Appointment.slot),
            selectinload(Appointment.patient)
        ).where(
            and_(
                Appointment.doctor_id == doctor_id,
                extract('year', Appointment.created_at) == year,
                extract('month', Appointment.created_at) == month
            )
        )
        
        result = await self.db.execute(query)
        appointments = result.scalars().all()

        # Group by date
        days_map = defaultdict(list)
        for appt in appointments:
            if appt.slot:
                date_key = appt.slot.slot_date
                days_map[date_key].append({
                    "id": appt.id,
                    "time": appt.slot.start_time.isoformat(),
                    "patient_name": appt.patient.full_name if appt.patient else "Unknown",
                    "status": appt.status
                })

        # Format response
        days = []
        for date_key, appts in sorted(days_map.items()):
            # Sort appointments by time within the day
            appts.sort(key=lambda x: x["time"])
            days.append(CalendarDay(date=date_key, appointments=appts))

        return CalendarReportResponse(
            month=f"{year}-{month:02d}",
            days=days
        )

    async def get_patients_report(self, doctor_id: int) -> list[PatientResponse]:
        """Get all patients assigned to a doctor (through their appointments)."""
        # Find distinct patients through appointments for this doctor
        query = select(Patient).join(Appointment, Patient.id == Appointment.patient_id).where(
            Appointment.doctor_id == doctor_id
        ).distinct()
        
        result = await self.db.execute(query)
        patients = result.scalars().all()
        return [PatientResponse.model_validate(p) for p in patients]

    async def get_history_report(self, doctor_id: int, patient_id: int) -> HistoryReportResponse:
        """Get full medical history for a patient, but only if they have seen this doctor."""
        # Verify doctor-patient relationship
        check = await self.db.execute(select(Appointment).where(
            Appointment.doctor_id == doctor_id, 
            Appointment.patient_id == patient_id
        ).limit(1))
        if not check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patient has no appointments with this doctor")
            
        p_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient = p_res.scalar_one()
        
        header = PatientHeader(
            id=patient.id,
            full_name=patient.full_name,
            age=patient.age,
            gender=patient.gender,
            email=patient.email,
            phone=patient.phone,
            address=patient.address,
        )
        
        # Load encrypted records
        records_query = select(MedicalRecord).options(
            selectinload(MedicalRecord.doctor)
        ).where(MedicalRecord.patient_id == patient_id).order_by(MedicalRecord.created_at.desc())
        
        r_res = await self.db.execute(records_query)
        db_records = r_res.scalars().all()
        
        decrypted_entries = []
        for rec in db_records:
            try:
                data = decrypt_data(rec.encrypted_data, rec.iv)
                entry = MedicalRecordEntry(
                    id=rec.id,
                    appointment_id=rec.appointment_id,
                    date=rec.created_at,
                    doctor_name=rec.doctor.full_name,
                    vital_signs=VitalSigns(**data.get("vital_signs", {})),
                    diagnosis=data.get("diagnosis", ""),
                    lab_results=data.get("lab_results"),
                    prescriptions=data.get("prescriptions"),
                    notes=data.get("notes"),
                )
                decrypted_entries.append(entry)
            except Exception:
                pass
                
        return HistoryReportResponse(header=header, records=decrypted_entries)
