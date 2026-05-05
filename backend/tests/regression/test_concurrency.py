import pytest
import pytest_asyncio
import asyncio
import datetime
from httpx import AsyncClient

from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.doctor_schedule import DoctorSchedule
from app.utils.security import hash_password

import uuid

@pytest_asyncio.fixture
async def setup_concurrency_data(db_session):
    """Seed the database with a doctor, a schedule, and 3 patients."""
    unique_suffix = uuid.uuid4().hex[:6]
    doc_username = f"doc.concurrency.{unique_suffix}"
    
    doc_user = User(username=doc_username, password_hash=hash_password("pwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    doc = Doctor(user_id=doc_user.id, full_name="Doc Concurrency", specialty="Test", license_number=f"123-conc-{unique_suffix}", slot_duration_minutes=60)
    db_session.add(doc)
    await db_session.flush()

    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    day_of_week = tomorrow.weekday()
    schedule = DoctorSchedule(
        doctor_id=doc.id,
        day_of_week=day_of_week,
        start_time=datetime.time(9, 0),
        end_time=datetime.time(12, 0) # Expanded to allow 9-10 and 10-11 disjoint slots
    )
    db_session.add(schedule)
    
    patients = []
    for i in range(3):
        pat_username = f"pat{i}.{unique_suffix}"
        u = User(username=pat_username, password_hash=hash_password("pwd123"), role="patient")
        db_session.add(u)
        await db_session.flush()
        p = Patient(user_id=u.id, full_name=f"Pat {i}", email=f"p{i}.{unique_suffix}@test.com", age=20, gender="other", phone="123")
        db_session.add(p)
        patients.append(pat_username)
        
    await db_session.commit()
    return {"doctor_id": doc.id, "appointment_date": tomorrow, "patients": patients}

@pytest.mark.asyncio
async def test_appointment_concurrency(async_client: AsyncClient, setup_concurrency_data):
    """
    Test distributed concurrency:
    Simulates 5 patients trying to book the exact same time slot at the exact same time.
    Only ONE should succeed (201), the rest should get 409 Conflict.
    """
    data = setup_concurrency_data
    
    users = [
        (data["patients"][0], "pwd123"),
        (data["patients"][1], "pwd123"),
        (data["patients"][2], "pwd123"),
        (data["patients"][0], "pwd123"),  # Reuse to simulate 5 requests
        (data["patients"][1], "pwd123"),
    ]
    
    tokens = []
    for i, (username, password) in enumerate(users):
        res = await async_client.post(
            "/api/v1/auth/login", 
            json={"username": username, "password": password},
            headers={"X-Forwarded-For": f"127.0.0.{10+i}"}
        )
        assert res.status_code == 200
        tokens.append(res.json()["data"]["token"])
    
    doctor_id = data["doctor_id"]
    appointment_date = data["appointment_date"].isoformat()
    
    # CONCURRENCY TEST: 5 simultaneous requests
    async def book_slot(token):
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "doctor_id": doctor_id,
            "appointment_date": appointment_date,
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "reason": "Test de concurrencia distribuida"
        }
        return await async_client.post("/api/v1/appointments", json=payload, headers=headers)

    # Launch all requests concurrently
    tasks = [book_slot(token) for token in tokens]
    responses = await asyncio.gather(*tasks)
    
    # Assertions
    status_codes = [r.status_code for r in responses]
    
    # Only exactly ONE request should succeed (201 Created)
    successes = [code for code in status_codes if code == 201]
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}. Status codes: {status_codes}"
    
    # The rest should fail due to concurrency conflict (409 Conflict)
    conflicts = [code for code in status_codes if code == 409]
    assert len(conflicts) == 4, f"Expected 4 conflicts, got {len(conflicts)}. Status codes: {status_codes}"

@pytest.mark.asyncio
async def test_disjoint_concurrency(async_client: AsyncClient, setup_concurrency_data):
    """
    Test that booking completely distinct slots for the same doctor at the same time
    succeeds without deadlocking or false overlaps.
    """
    data = setup_concurrency_data
    
    # Login two different patients
    res1 = await async_client.post("/api/v1/auth/login", json={"username": data["patients"][0], "password": "pwd123"})
    token1 = res1.json()["data"]["token"]
    
    res2 = await async_client.post("/api/v1/auth/login", json={"username": data["patients"][1], "password": "pwd123"})
    token2 = res2.json()["data"]["token"]
    
    doctor_id = data["doctor_id"]
    appointment_date = data["appointment_date"].isoformat()
    
    async def book_slot(token, start_time, end_time):
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "doctor_id": doctor_id,
            "appointment_date": appointment_date,
            "start_time": start_time,
            "end_time": end_time,
            "reason": "Test de concurrencia separada"
        }
        return await async_client.post("/api/v1/appointments", json=payload, headers=headers)

    # Patient 1 books 09:00 - 10:00, Patient 2 books 10:00 - 11:00 simultaneously
    t1 = book_slot(token1, "09:00:00", "10:00:00")
    t2 = book_slot(token2, "10:00:00", "11:00:00")
    
    responses = await asyncio.gather(t1, t2)
    
    status_codes = [r.status_code for r in responses]
    assert status_codes == [201, 201], "Both disjoint appointments should succeed simultaneously"
