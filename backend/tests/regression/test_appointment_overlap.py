import pytest
import pytest_asyncio
import datetime
import uuid
from httpx import AsyncClient

from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.models.appointment import Appointment
from app.utils.security import hash_password

@pytest_asyncio.fixture
async def setup_overlap_data(db_session):
    """Seed the database with a doctor, a schedule, and a patient."""
    unique_suffix = uuid.uuid4().hex[:6]
    
    doc_user = User(username=f"doc.overlap.{unique_suffix}", password_hash=hash_password("pwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    doc = Doctor(user_id=doc_user.id, full_name="Doc Overlap", specialty="Test", license_number=f"LIC-OVR-{unique_suffix}", slot_duration_minutes=60)
    db_session.add(doc)
    await db_session.flush()

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    day_of_week = tomorrow.weekday()
    schedule = DoctorSchedule(
        doctor_id=doc.id,
        day_of_week=day_of_week,
        start_time=datetime.time(8, 0),
        end_time=datetime.time(12, 0)
    )
    db_session.add(schedule)
    
    pat_user = User(username=f"pat.overlap.{unique_suffix}", password_hash=hash_password("pwd123"), role="patient")
    db_session.add(pat_user)
    await db_session.flush()
    
    pat = Patient(user_id=pat_user.id, full_name="Pat Overlap", email=f"pat.ov{unique_suffix}@test.com", age=30, gender="male", phone="123")
    db_session.add(pat)
    await db_session.flush()

    # Create an initial appointment from 09:00 to 10:00
    appt = Appointment(
        patient_id=pat.id,
        doctor_id=doc.id,
        appointment_date=tomorrow,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(10, 0),
        status="scheduled",
        created_by="patient",
        reason="Base appointment"
    )
    db_session.add(appt)
    await db_session.commit()
    
    return {
        "doctor_id": doc.id, 
        "patient_username": pat_user.username,
        "appointment_date": tomorrow.isoformat()
    }

@pytest.mark.asyncio
async def test_appointment_overlap_edge_cases(async_client: AsyncClient, setup_overlap_data):
    """
    Test various overlap scenarios against an existing 09:00-10:00 appointment.
    """
    data = setup_overlap_data
    
    # Login
    res = await async_client.post(
        "/api/v1/auth/login", 
        json={"username": data["patient_username"], "password": "pwd123"}
    )
    token = res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    base_payload = {
        "doctor_id": data["doctor_id"],
        "appointment_date": data["appointment_date"],
        "reason": "Overlap test"
    }
    
    # 1. Partial overlap (start earlier, end during) -> 08:30 to 09:30
    p1 = {**base_payload, "start_time": "08:30:00", "end_time": "09:30:00"}
    r1 = await async_client.post("/api/v1/appointments", json=p1, headers=headers)
    assert r1.status_code == 409, "Partial overlap should be rejected"
    
    # 2. Partial overlap (start during, end later) -> 09:30 to 10:30
    p2 = {**base_payload, "start_time": "09:30:00", "end_time": "10:30:00"}
    r2 = await async_client.post("/api/v1/appointments", json=p2, headers=headers)
    assert r2.status_code == 409, "Partial overlap should be rejected"
    
    # 3. Engulfing (start earlier, end later) -> 08:30 to 10:30
    p3 = {**base_payload, "start_time": "08:30:00", "end_time": "10:30:00"}
    r3 = await async_client.post("/api/v1/appointments", json=p3, headers=headers)
    assert r3.status_code == 409, "Engulfing overlap should be rejected"
    
    # 4. Same exact time -> 09:00 to 10:00
    p4 = {**base_payload, "start_time": "09:00:00", "end_time": "10:00:00"}
    r4 = await async_client.post("/api/v1/appointments", json=p4, headers=headers)
    assert r4.status_code == 409, "Exact overlap should be rejected"
    
    # 5. Exact boundaries (Valid) -> 10:00 to 11:00
    p5 = {**base_payload, "start_time": "10:00:00", "end_time": "11:00:00"}
    r5 = await async_client.post("/api/v1/appointments", json=p5, headers=headers)
    assert r5.status_code == 201, "Collinear times should be accepted"
    
    # 6. Exact boundaries (Valid) -> 08:00 to 09:00
    p6 = {**base_payload, "start_time": "08:00:00", "end_time": "09:00:00"}
    r6 = await async_client.post("/api/v1/appointments", json=p6, headers=headers)
    assert r6.status_code == 201, "Collinear times should be accepted"
