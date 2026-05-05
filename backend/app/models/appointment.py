"""Appointment model — medical appointment reservations."""

import datetime

from sqlalchemy import ForeignKey, String, Text, Date, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Appointment(Base, TimestampMixin):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    appointment_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)  # scheduled, completed, cancelled
    created_by: Mapped[str] = mapped_column(String(20), nullable=False)  # patient or doctor
    reason: Mapped[str | None] = mapped_column(Text)

    # Relationships
    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship(back_populates="appointments")
    medical_record: Mapped["MedicalRecord"] = relationship(back_populates="appointment", uselist=False)
