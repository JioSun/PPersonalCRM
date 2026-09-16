from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class Currency(str, Enum):
    USD = 'USD'
    EUR = 'EUR'
    RUB = 'RUB'


class ExtractedDealInfo(BaseModel):
    name: str
    amount: Decimal | None = None
    deadline: datetime | None = None
    currency: Currency | None = None
    matched_index: int | None = None
