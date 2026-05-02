"""
FastAPI dependencies — database sessions, authentication, and authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.utils.security import decode_access_token

# OAuth2 scheme — extracts Bearer token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class TokenData(BaseModel):
    """Decoded JWT payload data."""
    sub: int
    username: str
    role: str


# --- Database session dependency ---
async def get_db():
    """Provide an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# --- Authentication dependency ---
async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Decode JWT token and return current user data.
    Raises 401 if token is invalid or expired.
    """
    try:
        payload = decode_access_token(token)
        return TokenData(
            sub=payload["sub"],
            username=payload["username"],
            role=payload["role"],
        )
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_INVALID", "message": "Token inválido o expirado"},
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Authorization dependency (RBAC) ---
class RoleChecker:
    """
    Callable dependency that verifies the user has one of the allowed roles.

    Usage:
        only_doctor = RoleChecker(["doctor"])

        @router.get("/patients")
        async def list_patients(user: TokenData = Depends(only_doctor)):
            ...
    """

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "No tiene permisos para esta operación"},
            )
        return user


# Pre-built role checkers
only_doctor = RoleChecker(["doctor"])
only_patient = RoleChecker(["patient"])
any_authenticated = RoleChecker(["doctor", "patient"])
