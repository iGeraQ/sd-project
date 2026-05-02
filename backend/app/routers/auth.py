"""Auth router — register and login endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.dependencies import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.schemas.common import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=SuccessResponse[TokenResponse], status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new patient account."""
    service = AuthService(db)
    result = await service.register_patient(body)
    await db.commit()
    return SuccessResponse(data=result, message="Registro exitoso")


@router.post("/login", response_model=SuccessResponse[TokenResponse])
@limiter.limit("500/15minutes")
async def login_endpoint(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive a JWT token. Rate limited to 500 attempts per 15 minutes."""
    service = AuthService(db)
    result = await service.login(body.username, body.password)
    return SuccessResponse(data=result, message="Login exitoso")
