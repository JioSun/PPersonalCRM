from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import StringConstraints, field_validator, model_validator

from pydantic import BaseModel, ConfigDict, Field


from ...app.models.constants import InvoiceStatus

InvoiceLabel = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
    ),
]

class InvoiceFields(BaseModel):
    amount: Decimal = Field(
        max_digits=12, decimal_places=2, gt=0
    )
    due_date: date


class InvoiceBase(InvoiceFields):
    pass


class InvoiceCreate(InvoiceBase):
    model_config = ConfigDict(extra='forbid')

    label: InvoiceLabel
    deal_id: str

class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    amount: Decimal | None = Field(default=None, max_digits=12, decimal_places=2, gt=0)
    due_date: date | None = None
    label: InvoiceLabel  | None = None

    @field_validator("amount", "due_date", "label",  mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError('Передавать Null в тело запроса для обновления нельзя')
        return value



class InvoiceRead(InvoiceFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    deal_id: str
    number: str
    status: InvoiceStatus
    label: InvoiceLabel
    currency: Literal['USD']
    paid_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: InvoiceLabel
    client_name: str
    mid_amount: str
    due_date: str
    created_at: str
    deal_name: str
    deal_amount: Decimal
    deadline: datetime




