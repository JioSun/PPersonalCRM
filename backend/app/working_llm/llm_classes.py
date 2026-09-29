from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ExtractedDealInfo(BaseModel):
    name: str
    amount: Decimal | None = None
    deadline: datetime | None = None
    matched_index: int | None = None
