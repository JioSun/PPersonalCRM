from enum import Enum

from pydantic import BaseModel
from datetime import date
from decimal import Decimal

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"

class ExtractedDealInfo(BaseModel):
    name: str | None = None
    amount: Decimal | None = None
    deadline: date | None = None
    currency: Currency | None = None
    matched_index: int | None = None