import pytest
import pytest_asyncio
import datetime
from httpx import AsyncClient

from app.models.user import User
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.utils.security import hash_password

@pytest_asyncio.fixture
async def setup_doctor_with_schedule(db_session):
    """Fixture to create a doctor and a schedule so the patient can book it."""
    # Create doctor user
    doc_user = User(username="doctor.smith", password_hash=hash_password("docpwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    # Create doctor profile
    doc = Doctor(user_id=doc_user.id, full_name="Dr. Smith", specialty="General Practice", license_number="LIC-12345", slot_duration_minutes=60)
    db_session.add(doc)
    await db_session.flush()
    
    # Create schedule
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    day_of_week = tomorrow.weekday()
    schedule = DoctorSchedule(
        doctor_id=doc.id,
        day_of_week=day_of_week,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(17, 0)
    )
    db_session.add(schedule)
    await db_session.commit()
    
    return {"doctor_id": doc.id, "appointment_date": tomorrow}

@pytest.mark.asyncio
async def test_normal_patient_flow(async_client: AsyncClient, setup_doctor_with_schedule):
    """
    E2E Test for a normal patient flow:
    1. Register
    2. Login
    3. View available slots
    4. Book an appointment
    5. List appointments
    """
    doc_data = setup_doctor_with_schedule

    # 1. Register Patient
    register_payload = {
        "username": "patient.john",
        "password": "SecurePassword123!",
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "555-0100",
        "age": 35,
        "gender": "male"
    }
    
    register_res = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert register_res.status_code == 201
    
    # 2. Login
    login_payload = {
        "username": "patient.john",
        "password": "SecurePassword123!"
    }
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. View available slots
    start = datetime.date.today().isoformat()
    end = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
    slots_res = await async_client.get(
        f"/api/v1/appointments/slots?doctor_id={doc_data['doctor_id']}&start_date={start}&end_date={end}",
        headers=headers
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()["data"]
    assert len(slots) >= 1
    
    target_slot = slots[0]

    # 4. Book an appointment
    book_payload = {
        "doctor_id": doc_data["doctor_id"],
        "appointment_date": target_slot["slot_date"],
        "start_time": target_slot["start_time"],
        "end_time": target_slot["end_time"],
        "reason": "Annual physical checkup"
    }
    book_res = await async_client.post("/api/v1/appointments", json=book_payload, headers=headers)
    assert book_res.status_code == 201
    appointment_id = book_res.json()["data"]["id"]
    
    # 5. List appointments
    list_res = await async_client.get("/api/v1/appointments", headers=headers)
    assert list_res.status_code == 200
    appointments = list_res.json()["data"]
    assert len(appointments) == 1
    assert appointments[0]["id"] == appointment_id
    assert appointments[0]["status"] == "scheduled"
