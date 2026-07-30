import decimal
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime
from sqlmodel import SQLModel, Field, Relationship

from app.models.constants import DealStatus
from app.models.invoice import InvoiceCreate
from app.models.utils import get_datetime_utc, generate_ulid

if TYPE_CHECKING:
    from backend.app.models.client import Client
    from backend.app.models.user import User
    from backend.app.models.invoice import Invoice

# base — общие поля для Create/Update/Read
class DealBase(SQLModel):
    name: str = Field(max_length=255, index=True)
    amount: decimal.Decimal = Field(max_digits=8, decimal_places=2)
    status: DealStatus = DealStatus.NEW
    deadline: datetime | None = None

# table — то, что реально в БД
class Deal(DealBase, table=True):
    __tablename__ = "deal"

    id: str = Field(default_factory=generate_ulid, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    client_id: str = Field(foreign_key="client.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    client: "Client" = Relationship(back_populates="deal")
    user: "User" = Relationship(back_populates="deal")
    invoices: list["Invoice"] = Relationship(back_populates="deal")

# create
class DealCreate(DealBase):
    client_id: str

# update
class DealUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    amount: decimal.Decimal | None = Field(default=None, max_digits=8, decimal_places=2)
    status: DealStatus | None = None
    deadline: datetime | None = None

# read
class DealRead(DealBase):
    id: str
    created_at: datetime
    client_id: str