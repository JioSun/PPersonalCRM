from datetime import datetime
from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from app.models.utils import generate_ulid, get_datetime_utc
from sqlalchemy import DateTime

if TYPE_CHECKING:
    from backend.app.models.client import Client
    from backend.app.models.deal import Deal

#base
class UserBase(SQLModel):
    username: str = Field(max_length=255)
    email: EmailStr = Field(unique=True, index=True, max_length=255,  schema_extra={"example": "user.userson@example.com"})
    is_active: bool = True


#table
class User(UserBase, table=True):
    __tablename__ = "user"

    id: str | None = Field(default_factory=generate_ulid, primary_key=True)
    hashed_password: str

    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    clients: list["Client"] = Relationship(back_populates="user")
    deals: list["Deal"] = Relationship(back_populates="user")

#create
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)

#update
class UserUpdate(UserBase):
    username: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)

class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

#read
class UserRead(UserBase):
    id: str
    created_at: datetime | None = None