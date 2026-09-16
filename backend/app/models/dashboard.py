import decimal
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ClientSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    client_id: str = Field(validation_alias='id')
    client_name: str = Field(validation_alias='client_name')
    total_amount: decimal.Decimal = Field(validation_alias='total_spent')


class OverdueInvoice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    invoice_id: str = Field(validation_alias='id')
    deal_id: str = Field(validation_alias='deal_id')
    amount: decimal.Decimal = Field(validation_alias='mid_amount')
    due_date: date = Field(validation_alias='due_date')


class DashboardResponse(BaseModel):
    clients_summary: list[ClientSummary]
    overdue_invoice: list[OverdueInvoice]
