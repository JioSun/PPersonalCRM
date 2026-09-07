import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlmodel import Field


class UserFields(BaseModel):
    email: EmailStr
    full_name: str
    username: str
    timezone: str

class UserBase(UserFields):
    pass

class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    timezone: str| None = None

class UserRead(UserFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool