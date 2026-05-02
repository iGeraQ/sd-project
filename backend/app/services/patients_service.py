"""Patients service — CRUD operations for patient records."""

import math

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import PatientResponse, PatientUpdate
from app.schemas.common import PaginationMeta


class PatientsService:
    """Encapsulates patient CRUD business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
    ) -> tuple[list[PatientResponse], PaginationMeta]:
        """Get a paginated list of patients with optional name search."""
        query = select(Patient)

        if search:
            query = query.where(Patient.full_name.ilike(f"%{search}%"))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Patient.id)
        result = await self.db.execute(query)
        patients = result.scalars().all()

        pagination = PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=math.ceil(total / limit) if limit > 0 else 0,
        )

        return [PatientResponse.model_validate(p) for p in patients], pagination

    async def get_by_id(self, patient_id: int) -> PatientResponse:
        """Get a single patient by ID."""
        patient = await self._find_or_404(patient_id)
        return PatientResponse.model_validate(patient)

    async def get_patient_id_for_user(self, user_id: int) -> int | None:
        """Resolve the patient.id for a given user_id. Returns None if not found."""
        result = await self.db.execute(
            select(Patient.id).where(Patient.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update(self, patient_id: int, data: PatientUpdate) -> PatientResponse:
        """Update a patient's information (partial update)."""
        patient = await self._find_or_404(patient_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(patient, field, value)

        await self.db.flush()
        return PatientResponse.model_validate(patient)

    async def delete(self, patient_id: int) -> None:
        """Delete a patient and their associated user account (cascade)."""
        patient = await self._find_or_404(patient_id)

        user_result = await self.db.execute(
            select(User).where(User.id == patient.user_id)
        )
        user = user_result.scalar_one()
        await self.db.delete(user)
        await self.db.flush()

    # --- Private helpers ---

    async def _find_or_404(self, patient_id: int) -> Patient:
        """Fetch a patient or raise 404."""
        result = await self.db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PATIENT_NOT_FOUND", "message": "Paciente no encontrado"},
            )
        return patient
