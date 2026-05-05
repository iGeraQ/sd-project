import pytest
import pytest_asyncio
import datetime
from httpx import AsyncClient

from app.models.user import User
import uuid
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.appointment import Appointment
from app.utils.security import hash_password

@pytest_asyncio.fixture
async def setup_doctor_with_patient_and_appointment(db_session):
    """Fixture to create a doctor, a patient, and a scheduled appointment."""
    unique_suffix = uuid.uuid4().hex[:6]
    doc_username = f"doctor.strange.{unique_suffix}"
    
    # Create doctor user & profile
    doc_user = User(username=doc_username, password_hash=hash_password("magicpwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    doc = Doctor(user_id=doc_user.id, full_name="Dr. Stephen Strange", specialty="Surgery", license_number=f"LIC-STRANGE-{unique_suffix}", slot_duration_minutes=60)
    db_session.add(doc)
    await db_session.flush()
    
    # Create patient user & profile
    pat_username = f"patient.peter.{unique_suffix}"
    pat_user = User(username=pat_username, password_hash=hash_password("spideypwd123"), role="patient")
    db_session.add(pat_user)
    await db_session.flush()
    
    pat = Patient(user_id=pat_user.id, full_name="Peter Parker", email=f"peter{unique_suffix}@marvel.com", age=21, gender="male", phone="555-WEBS")
    db_session.add(pat)
    await db_session.flush()

    yesterday = datetime.date.today() - datetime.timedelta(days=1)

    # Create a scheduled appointment
    appointment = Appointment(
        patient_id=pat.id,
        doctor_id=doc.id,
        appointment_date=yesterday,
        start_time=datetime.time(14, 0),
        end_time=datetime.time(15, 0),
        status="scheduled",
        created_by="patient",
        reason="Follow up after surgery"
    )
    db_session.add(appointment)
    await db_session.commit()
    
    return {
        "doctor_user": doc_username, 
        "doctor_pwd": "magicpwd123",
        "patient_id": pat.id,
        "appointment_id": appointment.id
    }

@pytest.mark.asyncio
async def test_normal_doctor_flow(async_client: AsyncClient, setup_doctor_with_patient_and_appointment):
    """
    E2E Test for a normal doctor flow:
    1. Login (Registration is handled by admin/fixture)
    2. List appointments
    3. Create a medical record for the patient
    4. View patient's medical history
    """
    data = setup_doctor_with_patient_and_appointment

    # 1. Login
    login_payload = {
        "username": data["doctor_user"],
        "password": data["doctor_pwd"]
    }
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. List appointments
    list_res = await async_client.get("/api/v1/appointments", headers=headers)
    assert list_res.status_code == 200
    appointments = list_res.json()["data"]
    assert len(appointments) == 1
    assert appointments[0]["id"] == data["appointment_id"]
    assert appointments[0]["patient_id"] == data["patient_id"]

    # 3. Create a medical record for the patient
    record_payload = {
        "appointment_id": data["appointment_id"],
        "vital_signs": {
            "body_temperature": 36.6,
            "weight_kg": 75.0,
            "height_cm": 180.0,
            "blood_pressure": "120/80"
        },
        "diagnosis": "Healing well, minor scarring.",
        "prescriptions": "Rest and physical therapy.",
        "notes": "Patient is recovering exceptionally fast."
    }
    record_res = await async_client.post("/api/v1/medical-records", json=record_payload, headers=headers)
    assert record_res.status_code == 201
    record = record_res.json()["data"]
    assert record["diagnosis"] == record_payload["diagnosis"]
    assert record["prescriptions"] == record_payload["prescriptions"]

    # 4. View patient's medical history
    history_res = await async_client.get(f"/api/v1/medical-records/patient/{data['patient_id']}", headers=headers)
    assert history_res.status_code == 200
    history = history_res.json()["data"]
    assert history["patient"]["id"] == data["patient_id"]
    assert len(history["records"]) == 1
    
    # Verify the medical record we just added is in the history
    fetched_record = history["records"][0]
    assert fetched_record["id"] == record["id"]
    assert fetched_record["diagnosis"] == record_payload["diagnosis"]


@pytest.mark.asyncio
async def test_doctor_profile_and_schedule_update(async_client: AsyncClient, setup_doctor_with_patient_and_appointment):
    """Test that a doctor can update their profile (e.g. slot_duration) and their weekly schedule."""
    data = setup_doctor_with_patient_and_appointment
    
    # 1. Login
    login_res = await async_client.post("/api/v1/auth/login", json={
        "username": data["doctor_user"],
        "password": data["doctor_pwd"]
    })
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get profile
    profile_res = await async_client.get("/api/v1/doctors/me", headers=headers)
    assert profile_res.status_code == 200
    assert profile_res.json()["data"]["slot_duration_minutes"] == 60
    
    # 3. Update profile to 45 mins
    update_res = await async_client.put("/api/v1/doctors/me", json={"slot_duration_minutes": 45}, headers=headers)
    assert update_res.status_code == 200
    assert update_res.json()["data"]["slot_duration_minutes"] == 45
    
    # 4. Set schedule (Mon and Tue, 9 to 5)
    schedule_payload = {
        "schedules": [
            {"day_of_week": 0, "start_time": "09:00:00", "end_time": "17:00:00"},
            {"day_of_week": 1, "start_time": "09:00:00", "end_time": "17:00:00"}
        ]
    }
    sched_res = await async_client.put("/api/v1/doctors/me/schedules", json=schedule_payload, headers=headers)
    assert sched_res.status_code == 200
    schedules = sched_res.json()["data"]
    assert len(schedules) == 2
    
    # 5. Get schedules to verify
    get_sched_res = await async_client.get("/api/v1/doctors/me/schedules", headers=headers)
    assert get_sched_res.status_code == 200
    assert len(get_sched_res.json()["data"]) == 2
