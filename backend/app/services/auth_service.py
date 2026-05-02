"""Authentication service — register and login business logic."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.patient import Patient
from app.schemas.auth import RegisterRequest, TokenResponse, UserInfo
from app.utils.security import hash_password, verify_password, create_access_token
from app.services.email_service import EmailService


class AuthService:
    """Encapsulates authentication business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_patient(self, data: RegisterRequest) -> TokenResponse:
        """
        Register a new patient: creates a User + Patient record.
        Returns a JWT token with user info.
        """
        # Check uniqueness
        existing = await self.db.execute(
            select(User).where(User.username == data.username)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "USERNAME_EXISTS", "message": "El nombre de usuario ya está registrado"},
            )

        # Create user
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role="patient",
        )
        self.db.add(user)
        await self.db.flush()

        # Create patient profile
        patient = Patient(
            user_id=user.id,
            full_name=data.full_name,
            address=data.address,
            email=data.email,
            phone=data.phone,
            age=data.age,
            gender=data.gender,
        )
        self.db.add(patient)
        await self.db.flush()

        # Send Welcome Email
        import asyncio
        asyncio.create_task(
            EmailService.send_email(
                to_email=patient.email,
                subject="¡Bienvenido a MediApp!",
                template_name="welcome.html",
                context={
                    "full_name": patient.full_name,
                    "frontend_url": settings.frontend_url
                }
            )
        )

        # Generate token
        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        })

        return TokenResponse(
            token=token,
            user=UserInfo(
                id=user.id,
                username=user.username,
                role=user.role,
                full_name=patient.full_name,
            ),
            expires_in=settings.jwt_expire_hours * 3600,
        )

    async def login(self, username: str, password: str) -> TokenResponse:
        """
        Authenticate a user by credentials.
        Returns a JWT token with user info.
        """
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.patient), selectinload(User.doctor))
            .where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CREDENTIALS", "message": "Usuario o contraseña incorrectos"},
            )

        if not user.active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "USER_INACTIVE", "message": "La cuenta está desactivada"},
            )

        # Resolve display name by role
        full_name = user.username
        if user.role == "patient" and user.patient:
            full_name = user.patient.full_name
        elif user.role == "doctor" and user.doctor:
            full_name = user.doctor.full_name

        token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        })

        return TokenResponse(
            token=token,
            user=UserInfo(
                id=user.id,
                username=user.username,
                role=user.role,
                full_name=full_name,
            ),
            expires_in=settings.jwt_expire_hours * 3600,
        )
