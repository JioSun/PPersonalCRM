import decimal
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped
from sqlmodel import Column, Field, Relationship, SQLModel

from backend.app.models.constants import DealStatus
from backend.app.models.utils import generate_ulid, get_datetime_utc
from backend.app.working_llm.llm_classes import Currency

if TYPE_CHECKING:
    from backend.app.models.client import Client
    from backend.app.models.invoice import Invoice
    from backend.app.models.user import User


class DealBase(SQLModel):
    name: str = Field(max_length=255, index=True)
    amount: decimal.Decimal = Field(
        max_digits=8, decimal_places=2, default=decimal.Decimal(0)
    )
    status: DealStatus = DealStatus.NEW
    currency: Currency | None = Field(default=None, nullable=True)
    deadline: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )




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
