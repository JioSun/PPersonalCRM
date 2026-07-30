from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Index, DateTime

from app.models.invoice import Invoice
from app.models.utils import generate_ulid, get_datetime_utc
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.deal import Deal

#base
class ClientBase(SQLModel):
    username: str = Field(min_length=2, max_length=255)
    first_name: str | None = Field(max_length=255)
    last_name: str | None = Field(max_length=255)


#table
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
        Index("full_name_index", "first_name", "last_name",unique=True),
    )

#create
class ClientCreate(ClientBase):
    notes: str = Field(max_length=500)


#update
class ClientUpdate(ClientBase):
    client_name: str | None = Field(max_length=255)
    notes: str | None = Field(max_length=500)

#read
class ClientRead(ClientBase):
    id: str
    created_at: datetime | None = None