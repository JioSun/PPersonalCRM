import decimal
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Relationship, DateTime

from backend.app.models.utils import generate_ulid, get_datetime_utc

if TYPE_CHECKING:
    from backend.app.models.deal import Deal

#base
class InvoiceBase(SQLModel):
    is_paid: bool = Field(default=False)
    label: str = Field(max_length=255, index=True)
    mid_amount: decimal.Decimal = Field(max_digits=8, decimal_places=2, default=decimal.Decimal(0))
    due_date: datetime | None = None


#table
class Invoice(InvoiceBase, table=True):
    __tablename__ = "invoice"

    id: str | None = Field(default_factory=generate_ulid, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    deal_id: str = Field(foreign_key="deal.id", index=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    deal: Optional["Deal"] = Relationship(back_populates="invoices")

#create
class InvoiceCreate(InvoiceBase):
    pass

#update
class InvoiceUpdate(InvoiceBase):
    is_paid: bool | None = Field(default=None)
    label: str | None = Field(default=None)
    mid_amount: decimal.Decimal | None = Field(default=None)
    due_date: datetime | None = Field(default=None)

#read
class InvoiceRead(InvoiceBase):
    id: str
    created_at: datetime | None = None

class InvoiceList(BaseModel):
    invoices: List[InvoiceRead] | None = None
    total_sum: decimal.Decimal | None = None
