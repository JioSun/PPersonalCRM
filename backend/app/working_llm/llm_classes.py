from datetime import date
from decimal import Decimal
from typing import Self, Any

from pydantic import BaseModel, model_validator, Field, ConfigDict, field_validator


class ExtractedDealInfo(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str | None = Field(default=None, min_length=1, max_length=50)
    amount: Decimal | None = Field(default=None, ge=Decimal('0.00'), max_digits=12, decimal_places=2)
    deadline: date | None = None
    matched_index: int | None = None

    @model_validator(mode="after")
    def validation_name(self) -> Self:
        if self.matched_index is None and self.name is None:
            raise ValueError('Поле name должно быть заполнено при занятом matched_index')

        return self

    @model_validator(mode="after")
    def validation_amount(self) -> Self:
        if self.matched_index is None and self.amount is None:
            self.amount = Decimal('0.00')

        if self.amount is not None and self.amount < Decimal('0.00'):
            raise ValueError('amount не может быть меньше нуля')

        return self

    @field_validator("name", mode="before")
    @classmethod
    def space_clean(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value