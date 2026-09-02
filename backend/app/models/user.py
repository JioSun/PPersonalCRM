from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.utils import generate_ulid, get_datetime_utc

if TYPE_CHECKING:
    from backend.app.models.client import Client
    from backend.app.models.deal import Deal


# base
class UserBase(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(
        unique=True,
        index=True,
        max_length=255,
        schema_extra={"example": "userson@example.com"},
    )
    is_active: bool = True


# table

# create
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


# update
class UserUpdate(SQLModel):
    username: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# read
class UserRead(UserBase):
    id: str
    created_at: datetime | None = None
