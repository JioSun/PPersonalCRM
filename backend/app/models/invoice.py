from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlmodel import SQLModel, Field, Relationship, DateTime
from pydantic import EmailStr
from backend.app.models.utils import generate_ulid, get_datetime_utc

if TYPE_CHECKING:
    from backend.app.models.deal import Deal

#base
class InvoiceBase(SQLModel):
    is_paid: bool = Field(default=False)


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

#read
class InvoiceRead(InvoiceBase):
    id: str
    created_at: datetime | None = None