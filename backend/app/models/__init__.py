"""
Models package — imports all ORM models so Alembic can detect them.
"""

from app.models.base import Base, TimestampMixin
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.doctor_schedule import DoctorSchedule
from app.models.appointment import Appointment
from app.models.medical_record import MedicalRecord
from app.models.notification import Notification

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Patient",
    "Doctor",
    "DoctorSchedule",
    "Appointment",
    "MedicalRecord",
    "Notification",
]
