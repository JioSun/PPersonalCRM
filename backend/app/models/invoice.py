import decimal
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel
from sqlalchemy import Column, Date
from sqlmodel import DateTime, Field, Relationship, SQLModel

from backend.app.models.utils import generate_ulid, get_datetime_utc

if TYPE_CHECKING:
    from backend.app.models.deal import Deal


# base
class InvoiceBase(SQLModel):
    is_paid: bool = Field(default=False)
    label: str = Field(max_length=255, index=True)
    mid_amount: decimal.Decimal = Field(
        max_digits=8, decimal_places=2, default=decimal.Decimal(0)
    )
    due_date: date | None = Field(default=None, sa_column=Column(Date))


# table


# create
class InvoiceCreate(InvoiceBase):
    pass


# update
class InvoiceUpdate(SQLModel):
    is_paid: bool | None = Field(default=None)
    label: str | None = Field(default=None)
    mid_amount: decimal.Decimal | None = Field(default=None)
    due_date: date | None = Field(default=None)


# read
class InvoiceRead(InvoiceBase):
    id: str
    created_at: datetime | None = None


class InvoiceList(BaseModel):
    invoices: List[InvoiceRead] | None = None
    total_sum: decimal.Decimal | None = None
