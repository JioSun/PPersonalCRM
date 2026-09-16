from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from backend.app.models.constants import Currency


class ExtractedDealInfo(BaseModel):
    name: str
    amount: Decimal | None = None
    deadline: datetime | None = None
    currency: Currency | None = None
    matched_index: int | None = None
