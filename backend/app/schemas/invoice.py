from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.constants import Currency, InvoiceStatus


class InvoiceFields(BaseModel):
    amount: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=12,
        decimal_places=2,
        ge=0
    )
    currency: Currency = Currency.USD
    status: InvoiceStatus = InvoiceStatus.DRAFT
    due_date: date
    is_paid: bool = False

class InvoiceBase(InvoiceFields):
    pass

class InvoiceCreate(InvoiceBase):
    label: str
    client_id: str
    deal_id: str | None = None



class InvoiceUpdate(BaseModel):
    amount: Decimal | None = None
    status: InvoiceStatus | None = None
    due_date: date | None = None
    paid_at: datetime | None = None

class InvoiceRead(InvoiceFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    deal_id: str | None
    number: str
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime