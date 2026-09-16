from datetime import datetime
from decimal import Decimal
from backend.app.models.constants import Currency
from pydantic import BaseModel

class ExtractedDealInfo(BaseModel):
    name: str
    amount: Decimal | None = None
    deadline: datetime | None = None
    currency: Currency | None = None
    matched_index: int | None = None
