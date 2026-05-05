"""
Seed script to populate the database with initial development data.
Following Phase 8 requirements:
- 1 Doctor (Dr. García)
- 3 Patients
- Schedule rules for the doctor
- 5 Appointments
- 2 Medical records
"""

import asyncio
import datetime
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.models.appointment import Appointment
from app.models.medical_record import MedicalRecord
from app.utils.security import hash_password
from app.utils.encryption import encrypt_data

async def seed_data():
    async with AsyncSessionLocal() as db:
        print("Truncating tables...")
        # Truncate tables to ensure a clean state
        await db.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE;"))
        await db.commit()

        print("Seeding doctor...")
        # 1. Doctor: Dr. García
        doc_user = User(
            username="dr.garcia",
            password_hash=hash_password("admin123"),
            role="doctor"
        )
        db.add(doc_user)
        await db.flush()

        doctor = Doctor(
            user_id=doc_user.id,
            full_name="Dr. Juan García",
            specialty="Medicina General",
            license_number="MED-12345",
            slot_duration_minutes=60
        )
        db.add(doctor)
        await db.flush()

        print("Seeding patients...")
        # 2. 3 Patients
        patients = []
        patient_data = [
            ("ana.lopez", "Ana López", "ana@example.com", 28, "female"),
            ("carlos.ruiz", "Carlos Ruiz", "carlos@example.com", 45, "male"),
            ("maria.santos", "María Santos", "maria@example.com", 33, "female")
        ]

        for username, full_name, email, age, gender in patient_data:
            u = User(username=username, password_hash=hash_password("password123"), role="patient")
            db.add(u)
            await db.flush()

            p = Patient(user_id=u.id, full_name=full_name, email=email, age=age, gender=gender, phone="555-0000")
            db.add(p)
            await db.flush()
            patients.append(p)

        print("Seeding doctor schedules...")
        # 3. Schedule for Mon-Fri, 9am to 1pm
        for day in range(5):
            schedule = DoctorSchedule(
                doctor_id=doctor.id,
                day_of_week=day,
                start_time=datetime.time(9, 0),
                end_time=datetime.time(13, 0)
            )
            db.add(schedule)
        await db.flush()

        print("Seeding appointments...")
        # 4. 5 Appointments
        appointments = []
        today = datetime.date.today()
        # Find next Monday to start booking
        current_date = today + datetime.timedelta(days=(7 - today.weekday()) % 7)
        if current_date == today:
            current_date += datetime.timedelta(days=1)
            
        # Book 5 appointments
        for i in range(5):
            # Book 1 per day at 10 AM
            appt_date = current_date + datetime.timedelta(days=i)
            # Skip weekend if we cross it
            if appt_date.weekday() > 4:
                appt_date += datetime.timedelta(days=2)
                
            patient = patients[i % 3] # Assign round-robin to our 3 patients
            
            # Create appointment
            appt = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=appt_date,
                start_time=datetime.time(10, 0),
                end_time=datetime.time(11, 0),
                status="completed" if i < 2 else "scheduled", # First 2 completed, rest scheduled
                created_by="doctor",
                reason=f"Consulta general {i+1}"
            )
            db.add(appt)
            appointments.append(appt)
        await db.flush()

        print("Seeding medical records...")
        # 5. 2 Medical records for the completed appointments
        for i in range(2):
            appt = appointments[i]
            
            payload = {
                "vital_signs": {
                    "body_temperature": 36.5 + i*0.2,
                    "weight_kg": 70.0 + i*2.0,
                    "height_cm": 170.0 + i*5.0,
                    "blood_pressure": "120/80"
                },
                "diagnosis": "Chequeo de rutina sin hallazgos patológicos.",
                "lab_results": "Colesterol en límites normales.",
                "prescriptions": "Mantener buena hidratación y dieta balanceada.",
                "notes": "Paciente refiere sentirse en buen estado."
            }

            encrypted_data, iv = encrypt_data(payload)

            record = MedicalRecord(
                appointment_id=appt.id,
                patient_id=appt.patient_id,
                doctor_id=appt.doctor_id,
                encrypted_data=encrypted_data,
                iv=iv,
            )
            db.add(record)
        
        await db.commit()
        print("✅ Seed data successfully inserted!")

if __name__ == "__main__":
    asyncio.run(seed_data())
