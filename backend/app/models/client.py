from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import DateTime, Field, Index, Relationship, SQLModel

from backend.app.models.utils import generate_ulid, get_datetime_utc

if TYPE_CHECKING:
    from backend.app.models.deal import Deal
    from backend.app.models.user import User


# base
class ClientBase(SQLModel):
    username: str = Field(min_length=2, max_length=255)
    first_name: str | None = Field(max_length=255)
    last_name: str | None = Field(max_length=255)


# table
class Client(ClientBase, table=True):
    __tablename__ = "client"

    id: str | None = Field(default_factory=generate_ulid, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    notes: str | None = Field(max_length=500)
    user_id: str = Field(foreign_key="user.id", index=True)

    user: Optional["User"] = Relationship(back_populates="clients")
    deals: list["Deal"] = Relationship(back_populates="client")

    __table_args__ = (
        Index("full_name_index", "first_name", "last_name"),
        UniqueConstraint("user_id", "username", name="unique_username_for_user"),
    )


# create
class ClientCreate(ClientBase):
    notes: str | None = Field(max_length=500, default=None)


# update
class ClientUpdate(SQLModel):
    username: str | None = Field(default=None, )
    notes: str | None = Field(default=None, max_length=500)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)


# read
class ClientRead(ClientBase):
    id: str
    notes: str | None = Field(max_length=500)
    created_at: datetime | None = None
