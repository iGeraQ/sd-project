import pytest
import pytest_asyncio
import datetime
import uuid
from httpx import AsyncClient

from app.models.user import User
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.utils.security import hash_password

@pytest_asyncio.fixture
async def setup_schedule_edge_data(db_session):
    unique_suffix = uuid.uuid4().hex[:6]
    
    doc_username = f"doc.sched.{unique_suffix}"
    doc_user = User(username=doc_username, password_hash=hash_password("pwd123"), role="doctor")
    db_session.add(doc_user)
    await db_session.flush()
    
    # We set a slot duration of 120 minutes
    doc = Doctor(user_id=doc_user.id, full_name="Doc Schedule", specialty="Test", license_number=f"LIC-SCH-{unique_suffix}", slot_duration_minutes=120)
    db_session.add(doc)
    await db_session.flush()

    pat_username = f"pat.sched.{unique_suffix}"
    pat_user = User(username=pat_username, password_hash=hash_password("pwd123"), role="patient")
    db_session.add(pat_user)
    await db_session.flush()
    
    pat = Patient(user_id=pat_user.id, full_name="Pat Schedule", email=f"pat.sch{unique_suffix}@test.com", age=30, gender="male", phone="123")
    db_session.add(pat)
    await db_session.commit()
    
    return {
        "doctor_id": str(doc.id),
        "doctor_username": doc_username,
        "patient_username": pat_username,
    }

@pytest.mark.asyncio
async def test_schedule_edge_cases(async_client: AsyncClient, setup_schedule_edge_data):
    data = setup_schedule_edge_data
    
    # Login as doctor to manage schedule
    res_doc = await async_client.post(
        "/api/v1/auth/login", 
        json={"username": data["doctor_username"], "password": "pwd123"}
    )
    doc_token = res_doc.json()["data"]["token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    
    # Login as patient to view slots
    res_pat = await async_client.post(
        "/api/v1/auth/login", 
        json={"username": data["patient_username"], "password": "pwd123"}
    )
    pat_token = res_pat.json()["data"]["token"]
    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    
    # 1. Doctor without schedule -> Patient searches slots
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    slots_res = await async_client.get(
        f"/api/v1/appointments/slots?doctor_id={data['doctor_id']}&start_date={tomorrow}&end_date={tomorrow}",
        headers=pat_headers
    )
    assert slots_res.status_code == 200
    assert len(slots_res.json()["data"]) == 0, "No slots should be returned if doctor has no schedule"
    
    # 2. Doctor attempts to set inverted schedule (start > end)
    inv_payload = {
        "schedules": [
            {"day_of_week": 0, "start_time": "17:00:00", "end_time": "09:00:00"}
        ]
    }
    inv_res = await async_client.put("/api/v1/doctors/me/schedules", json=inv_payload, headers=doc_headers)
    assert inv_res.status_code == 400, "Inverted schedule should be rejected"
    
    # 3. Doctor sets schedule smaller than slot_duration_minutes
    # slot_duration_minutes is 120 (2 hours), but schedule is 1 hour (09:00 to 10:00)
    # The system should accept the schedule but yield 0 available slots because no 2-hour slot fits in 1 hour.
    small_sched_payload = {
        "schedules": [
            {"day_of_week": 0, "start_time": "09:00:00", "end_time": "10:00:00"}
        ]
    }
    # find next monday
    today = datetime.date.today()
    next_monday = today + datetime.timedelta(days=(7 - today.weekday()) % 7)
    if next_monday == today:
         next_monday += datetime.timedelta(days=7)
         
    small_sched_res = await async_client.put("/api/v1/doctors/me/schedules", json=small_sched_payload, headers=doc_headers)
    assert small_sched_res.status_code == 200
    
    # Patient queries slots for that monday
    monday_iso = next_monday.isoformat()
    slots_res_2 = await async_client.get(
        f"/api/v1/appointments/slots?doctor_id={data['doctor_id']}&start_date={monday_iso}&end_date={monday_iso}",
        headers=pat_headers
    )
    assert slots_res_2.status_code == 200
    assert len(slots_res_2.json()["data"]) == 0, "Should return 0 slots because 120min slot doesn't fit in 60min schedule"
    
    # 4. Search in the past (yesterday)
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    past_res = await async_client.get(
        f"/api/v1/appointments/slots?doctor_id={data['doctor_id']}&start_date={yesterday}&end_date={yesterday}",
        headers=pat_headers
    )
    # The API might allow past search but yield 0, or just yield what the math says.
    # Currently the math might just calculate it regardless of "today".
    assert past_res.status_code == 200
