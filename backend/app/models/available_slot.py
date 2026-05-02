"""AvailableSlot model — time slots for doctor appointments with concurrency control."""

import datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AvailableSlot(Base):
    __tablename__ = "available_slots"
    __table_args__ = (
        UniqueConstraint("doctor_id", "slot_date", "start_time", name="uq_slot_doctor_date_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False)
    slot_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # Optimistic locking

    # Relationships
    doctor: Mapped["Doctor"] = relationship(back_populates="available_slots")
    appointment: Mapped["Appointment"] = relationship(back_populates="slot", uselist=False)
