from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.constants import Currency, DealStatus


class DealValidation:
    pass


class DealFields(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    amount: Decimal = Field(
        default=Decimal('0.00'), max_digits=12, decimal_places=2, ge=0
    )
    status: DealStatus = DealStatus.NEW
    currency: Currency = Currency.USD
    deadline: datetime | None = None
    closed_at: datetime | None = Field(default=None)
    notes: str | None = Field(default=None, max_length=5000)


class DealBase(DealValidation, DealFields):
    pass


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    currency: Currency | None = None
    status: DealStatus | None = None
    deadline: datetime | None = None
    notes: str | None = None


class DealRead(DealFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
