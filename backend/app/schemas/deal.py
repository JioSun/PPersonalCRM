from datetime import datetime, date
from decimal import Decimal
from pydantic import StringConstraints, field_validator
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

from ..models.constants import DealStatus


DealName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
    ),
]

class DealValidation:
    pass


class DealFields(BaseModel):
    name: DealName
    amount: Decimal = Field(
        default=Decimal('0.00'), max_digits=12, decimal_places=2, ge=0
    )

    deadline: date | None = None

    notes: str | None = Field(default=None, max_length=5000)
    client_id: str

class DealBase(DealValidation, DealFields):
    pass


class DealCreate(DealBase):
    model_config = ConfigDict(extra='forbid')
    pass


class DealUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: DealName | None = None
    amount: Decimal | None = Field(
        default=None, max_digits=12, decimal_places=2, ge=0
    )
    status: DealStatus | None = None
    deadline: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("amount", "name", "status", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError('Передавать Null в тело запроса для обновления нельзя')
        return value


class DealRead(DealFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    amount: Decimal
    currency: Literal['USD']
    deadline: date | None
    status: DealStatus
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
