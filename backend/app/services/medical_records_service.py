"""Medical Records service — handles AES-256-GCM encrypted clinical data."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.schemas.medical_record import CreateMedicalRecordRequest, MedicalRecordEntry, PatientHistoryResponse, PatientHeader, VitalSigns
from app.utils.encryption import encrypt_data, decrypt_data


class MedicalRecordsService:
    """Encapsulates medical records logic, including transparent encryption."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_record(self, doctor_id: int, data: CreateMedicalRecordRequest) -> MedicalRecordEntry:
        """Create a new medical record (encrypts data before saving)."""
        # Validate appointment and permissions
        res = await self.db.execute(
            select(Appointment)
            .options(selectinload(Appointment.patient))
            .where(Appointment.id == data.appointment_id)
        )
        appointment = res.scalar_one_or_none()

        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada")

        if appointment.doctor_id != doctor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el médico asignado a la cita puede crear el historial")

        if appointment.status != "completed":
            appointment.status = "completed"
            await self.db.flush()

        # Check if record already exists
        existing = await self.db.execute(select(MedicalRecord).where(MedicalRecord.appointment_id == data.appointment_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un historial para esta cita")

        # Prepare payload to encrypt
        payload = {
            "vital_signs": data.vital_signs.model_dump(),
            "diagnosis": data.diagnosis,
            "lab_results": data.lab_results,
            "prescriptions": data.prescriptions,
            "notes": data.notes,
        }

        # Encrypt the payload
        encrypted_data, iv = encrypt_data(payload)

        # Create record
        record = MedicalRecord(
            appointment_id=appointment.id,
            patient_id=appointment.patient_id,
            doctor_id=doctor_id,
            encrypted_data=encrypted_data,
            iv=iv,
        )
        self.db.add(record)
        await self.db.flush()

        # We also need the doctor's name for the response
        doc_res = await self.db.execute(select(Doctor.full_name).where(Doctor.id == doctor_id))
        doc_name = doc_res.scalar_one()

        return MedicalRecordEntry(
            id=record.id,
            appointment_id=record.appointment_id,
            date=record.created_at,
            doctor_name=doc_name,
            vital_signs=data.vital_signs,
            diagnosis=data.diagnosis,
            lab_results=data.lab_results,
            prescriptions=data.prescriptions,
            notes=data.notes,
        )

    async def get_patient_history(self, patient_id: int, current_user_id: int, current_user_role: str) -> PatientHistoryResponse:
        """Fetch and decrypt the entire history for a patient."""
        # RBAC Check
        if current_user_role == "patient":
            res = await self.db.execute(select(Patient.id).where(Patient.user_id == current_user_id))
            own_id = res.scalar_one()
            if own_id != patient_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puede ver su propio historial")

        # Load patient info
        p_res = await self.db.execute(select(Patient).where(Patient.id == patient_id))
        patient = p_res.scalar_one_or_none()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")

        header = PatientHeader(
            id=patient.id,
            full_name=patient.full_name,
            age=patient.age,
            gender=patient.gender,
            email=patient.email,
            phone=patient.phone,
            address=patient.address,
        )

        # Load encrypted records with doctor info
        records_query = select(MedicalRecord).options(
            selectinload(MedicalRecord.doctor)
        ).where(
            MedicalRecord.patient_id == patient_id
        ).order_by(MedicalRecord.created_at.desc())
        
        r_res = await self.db.execute(records_query)
        db_records = r_res.scalars().all()

        decrypted_entries = []
        for rec in db_records:
            # Decrypt payload
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
            except Exception as e:
                # Log error in real app, return generic message
                print(f"Decryption failed for record {rec.id}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error de integridad de datos en el historial clínico")

        return PatientHistoryResponse(patient=header, records=decrypted_entries)
