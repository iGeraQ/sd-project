"""Authentication schemas — register, login, token responses."""

import uuid
from pydantic import BaseModel, EmailStr, Field
from typing import Literal


class RegisterRequest(BaseModel):
    username: str = Field(min_length=4, max_length=50, pattern=r"^[a-zA-Z0-9.]+$")
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=150)
    address: str | None = None
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    age: int = Field(gt=0, lt=150)
    gender: Literal["male", "female", "other"]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    full_name: str


class TokenResponse(BaseModel):
    token: str
    user: UserInfo
    expires_in: int  # seconds
