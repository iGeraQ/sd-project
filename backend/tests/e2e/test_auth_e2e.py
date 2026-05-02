import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_and_login_patient(async_client: AsyncClient):
    """Test full flow: register a new patient and login."""
    
    # 1. Register
    register_payload = {
        "username": "test.patient",
        "password": "SecurePassword123!",
        "full_name": "Test Patient",
        "email": "test@example.com",
        "phone": "1234567890",
        "age": 30,
        "gender": "other"
    }
    
    response = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert "token" in data
    assert data["user"]["username"] == "test.patient"
    assert data["user"]["role"] == "patient"
    
    # 2. Try registering the same username again (should fail)
    response2 = await async_client.post("/api/v1/auth/register", json=register_payload)
    assert response2.status_code == 409
    
    # 3. Login
    login_payload = {
        "username": "test.patient",
        "password": "SecurePassword123!"
    }
    
    login_response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert login_response.status_code == 200
    login_data = login_response.json()["data"]
    assert "token" in login_data
    
    # 4. Login with wrong password
    wrong_login = {
        "username": "test.patient",
        "password": "WrongPassword!"
    }
    wrong_res = await async_client.post("/api/v1/auth/login", json=wrong_login)
    assert wrong_res.status_code == 401
