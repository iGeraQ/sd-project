import pytest
import pytest_asyncio
import datetime
from httpx import AsyncClient

from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.utils.security import hash_password

@pytest_asyncio.fixture
async def setup_doctor_and_patient(db_session):
    """Seed the database directly with a doctor and patient for e2e tests."""
    doc_user = User(username="test.doctor", password_hash=hash_password("pwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    doc = Doctor(user_id=doc_user.id, full_name="Test Doctor", specialty="Test", license_number="123-e2e", slot_duration_minutes=60)
    db_session.add(doc)
    await db_session.flush()
    
    pat_user = User(username="test.pat", password_hash=hash_password("pwd123"), role="patient")
    db_session.add(pat_user)
    await db_session.flush()
    
    pat = Patient(user_id=pat_user.id, full_name="Test Pat", email="p@p.com", age=20, gender="male", phone="123")
    db_session.add(pat)
    await db_session.flush()
    
    # Create schedule tomorrow
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    day_of_week = tomorrow.weekday()
    schedule = DoctorSchedule(
        doctor_id=doc.id,
        day_of_week=day_of_week,
        start_time=datetime.time(10, 0),
        end_time=datetime.time(12, 0)
    )
    db_session.add(schedule)
    await db_session.commit()
    
    return {"doctor_id": str(doc.id), "patient_id": str(pat.id), "appointment_date": tomorrow}

@pytest.mark.asyncio
async def test_appointment_crud_e2e(async_client: AsyncClient, setup_doctor_and_patient):
    """Test searching slots, booking an appointment, listing it, and cancelling it."""
    data = setup_doctor_and_patient
    
    # 1. Login as patient
    login_res = await async_client.post("/api/v1/auth/login", json={"username": "test.pat", "password": "pwd123"})
    token = login_res.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Get available slots
    start = datetime.date.today().isoformat()
    end = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
    slots_res = await async_client.get(
        f"/api/v1/appointments/slots?doctor_id={data['doctor_id']}&start_date={start}&end_date={end}",
        headers=headers
    )
    assert slots_res.status_code == 200
    slots = slots_res.json()["data"]
    assert len(slots) >= 1
    
    # 3. Create appointment
    create_payload = {
        "doctor_id": str(data["doctor_id"]),
        "appointment_date": slots[0]["slot_date"],
        "start_time": slots[0]["start_time"],
        "end_time": slots[0]["end_time"],
        "reason": "Routine checkup"
    }
    create_res = await async_client.post("/api/v1/appointments", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    appointment = create_res.json()["data"]
    assert appointment["status"] == "scheduled"
    
    # 4. List appointments
    list_res = await async_client.get("/api/v1/appointments", headers=headers)
    assert list_res.status_code == 200
    appts = list_res.json()["data"]
    assert len(appts) == 1
    assert appts[0]["id"] == appointment["id"]
    
    # 5. Cancel appointment
    cancel_res = await async_client.delete(f"/api/v1/appointments/{appointment['id']}", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "cancelled"
