from pydantic import BaseModel, Field, ConfigDict
from datetime import date
import decimal

class ClientSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(validation_alias='id')
    client_name: str = Field(validation_alias='username')
    total_amount: decimal.Decimal = Field(validation_alias='sum')

class OverdueInvoice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: str = Field(validation_alias='id')
    deal_id: str = Field(validation_alias='deal_id')
    amount: decimal.Decimal = Field(validation_alias='mid_amount')
    due_date: date = Field(validation_alias='due_date')

class DashboardResponce(BaseModel):
    clients_summary: list[ClientSummary]
    overdue_invoice: list[OverdueInvoice]
