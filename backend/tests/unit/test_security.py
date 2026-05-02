import pytest
from app.utils.security import hash_password, verify_password, create_access_token, decode_access_token
from app.config import settings
from jose import JWTError
import time

def test_password_hashing():
    """Test that hashing and verification works correctly."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    
    # Hashes should be different due to salting even for the same password
    hashed2 = hash_password(password)
    assert hashed != hashed2
    
    # Verification should succeed
    assert verify_password(password, hashed) is True
    assert verify_password(password, hashed2) is True
    
    # Verification should fail for wrong password
    assert verify_password("wrongpassword", hashed) is False

def test_jwt_token_creation_and_decoding():
    """Test JWT token lifecycle."""
    payload = {"sub": "1", "username": "testuser", "role": "patient"}
    
    token = create_access_token(payload)
    assert isinstance(token, str)
    assert len(token) > 0
    
    decoded = decode_access_token(token)
    assert decoded["sub"] == payload["sub"]
    assert decoded["username"] == payload["username"]
    assert decoded["role"] == payload["role"]
    assert "exp" in decoded
    assert "iat" in decoded

def test_jwt_invalid_token():
    """Test that decoding an invalid token raises JWTError."""
    with pytest.raises(JWTError):
        decode_access_token("this.is.not.a.valid.token")
